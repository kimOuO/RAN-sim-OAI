// Phase B — KPM / RIC 監控 API client (Dashboard /runs 用)
import { duClient, ueClient } from '@/services/clients/httpClient';
import { omniverseApiClient } from '@/services/api/omniverse';

export interface DuPmSnapshot {
  tick_count: number;
  wall_tick_ms: number;
  sim_dt_ms: number;
  sim_speed_x: number;
  report_every_n_ticks: number;
  ue_registry: string[];
  // Phase B — per-UE 上一 tick 瞬時值(從 RU CqiIndication 來),沒平均
  ue_latest?: Record<string, {
    serving_cell: string;
    sinr_db: number | null;
    rsrp_dbm: number | null;
    neighbors: Array<{ cell_id: string; rsrp_dbm: number; rsrq_db: number }>;
  }>;
  // Phase B — per-tick 即時 stats(throughput / delay / PRB / MCS),非累積
  last_ue_stats?: Record<string, {
    serving_cell: string;
    sinr_db: number;
    rsrp_dbm: number;
    prb_dl_this_tick: number;
    mcs_dl: number;
    bytes_dl_this_tick: number;
    throughput_dl_mbps_this_tick: number;
    rlc_delay_ms_avg_this_tick: number;
    rlc_buffer_bo_this_tick: number;
    neighbors: Array<{ cell_id: string; rsrp_dbm: number; rsrq_db: number }>;
  }>;
  last_cell_stats?: Record<string, {
    prb_used_this_tick: number;
    prb_total: number;
    prb_pct_this_tick: number;
    is_active: boolean;
    attached_ue_list?: string[];
    attached_ue_count?: number;
    scheduled_ue_count?: number;
    dl_aggregate_mbps_this_tick?: number;
    quota_cap_factor?: number;
    quota_max_prb_pct?: number;
  }>;
  gnbs: Record<string, {
    avg_sinr_db: number;
    avg_rsrp_dbm: number;
    prb_used_dl: number;
    pdcp_bytes_dl: Record<string, number>;
    mcs_dl_bins: number[];
    cqi_bins: number[];
  }>;
}

export interface ScenarioDriverStatus {
  running: boolean;
  scenario_id?: string;
  source?: string;
  started_at_ms?: number;
  sim_tick_idx?: number;
  total_ticks?: number;
  elapsed_wall_sec?: number;
  elapsed_sim_sec?: number;
  sim_speed_x: number;
  ue_count?: number;
  traffic_count?: number;
  // 劇本 _metadata.trigger_config(key 對齊 TRIGGER_THRESHOLDS),evaluator 用它覆蓋預設
  trigger_config?: Record<string, number>;
  inject_call_count?: number;
  position_push_count?: number;
  last_error?: string;
}

export interface ControlActionRow {
  id: number;
  control_style: number;
  control_action_id: number;
  action_label: string;
  ue_name: string | null;
  cell_id: string | null;
  payload_json: Record<string, unknown>;
  outcome: string;
  error: string | null;
  action_ts: string | null;
}

export const fetchDuPm = async (): Promise<DuPmSnapshot> => {
  const r = await duClient.post('/api/v0.1/DU/Tick/TickController/dump_pm', {});
  return r.data?.data;
};

export const fetchDriverStatus = async (): Promise<ScenarioDriverStatus> => {
  const r = await ueClient.post('/api/v0.1/UE/Scenario/ScenarioController/status', {});
  return r.data?.data;
};

export const fetchControlActions = async (sessionUuid: string): Promise<ControlActionRow[]> => {
  if (!sessionUuid) return [];
  try {
    const r = await omniverseApiClient.post(
      '/api/v0.1/RAN/Playback/ControlActionReader/read',
      { session_uuid: sessionUuid },
    );
    return r.data?.data?.control_actions ?? [];
  } catch {
    return [];
  }
};

export interface HandoverEventRow {
  ho_uuid: string;
  ue_name: string;
  source_cell: string;
  target_cell: string;
  trigger: string;
  status: string;
  event_ts: string | null;
}

export const fetchHandovers = async (sessionUuid: string): Promise<HandoverEventRow[]> => {
  if (!sessionUuid) return [];
  try {
    const r = await omniverseApiClient.post(
      '/api/v0.1/RAN/Playback/HandoverReader/read',
      { session_uuid: sessionUuid },
    );
    return r.data?.data?.handovers ?? [];
  } catch {
    return [];
  }
};

// 取後端「真實 running session」的 uuid。HO / control action 都綁在 SimSession 的
// session_uuid（格式 sim_<ts>_<hash>）上;前端若自捏 uuid 會永遠濾不到 → 0。
// 優先比對當前 scenario,否則取最新 running。
export const fetchActiveSessionUuid = async (scenarioId?: string): Promise<string> => {
  try {
    const r = await omniverseApiClient.post(
      '/api/v0.1/RAN/SimSession/PlaybackController/list', {},
    );
    const sessions: Array<{ session_uuid: string; status: string; scenario_id?: string; scene_id?: string }> =
      r.data?.data?.sessions ?? [];
    const running = sessions.filter(s => s.status === 'running');
    const match = running.find(s => s.scenario_id === scenarioId || s.scene_id === scenarioId) ?? running[0];
    return match?.session_uuid ?? '';
  } catch {
    return '';
  }
};

// ── 三個劇本的觸發判定 ─────────────────────────────────────────────
// 跟 docs/scenarios/generate_oai_scenarios.py 的 expected_kpm 對應
export interface TriggerEval {
  scenario: 'im' | 'cco' | 'es';
  conditions: { label: string; ok: boolean; value: string }[];
  triggered: boolean;
}

// IM/ES 評估是 UE-centric 門檻 — 必須看 UE 真正的 serving cell 而非寫死 c0。
// 之前寫死 cellStats['gnbDT_c0'] 在 UE attach 到 c1 / HO 場景全錯。
function pickServingCell(pm: DuPmSnapshot) {
  const cellStats = pm.last_cell_stats ?? {};
  const ueStats = pm.last_ue_stats ?? {};
  const ue = Object.values(ueStats)[0];
  const servingId = ue?.serving_cell;
  const cell = (servingId && cellStats[servingId]) ?? Object.values(cellStats)[0];
  return { cell, ue, servingId };
}

// ── Trigger 門檻 — 單一來源(邏輯與標籤共用同一份，永不漂移) ─────────────
//   要改門檻只動這裡;下方 evaluator 的判斷式與顯示標籤都從這裡推導。
export const TRIGGER_THRESHOLDS = {
  im:  { prbPctMin: 70, thpMbpsMax: 5,    delayMsMin: 50 },
  // CCO：對齊劇本 _metadata.trigger_thresholds —— active DU 三者 AND
  // (DRB.PdcpSduVolumeDL≥2500kbit, DRB.RlcSduDelayDl≥500ms=500000μs, RRU.PrbTotDl≥6%=60000ppm)
  cco: { pdcpKbitMin: 2500, rlcUsMin: 500_000, prbPpmMin: 60_000 },
  es:  { prbPctMax: 10, thpMbpsMax: 0.1 },
};

// 改用 per-tick stats(last_cell_stats / last_ue_stats),對齊 OAI intent 真實門檻
export function evaluateIm(pm: DuPmSnapshot, cfg?: Record<string, number>): TriggerEval {
  const t = { ...TRIGGER_THRESHOLDS.im, ...(cfg ?? {}) };
  const { cell, ue } = pickServingCell(pm);
  const prbPct = cell?.prb_pct_this_tick ?? 0;
  const thp = ue?.throughput_dl_mbps_this_tick ?? 0;
  const delay = ue?.rlc_delay_ms_avg_this_tick ?? 0;
  const prbOk = prbPct > t.prbPctMin;
  const thpOk = thp < t.thpMbpsMax;
  const delayOk = delay > t.delayMsMin;
  return {
    scenario: 'im',
    conditions: [
      { label: `PRB% > ${t.prbPctMin} (滿載)`,          ok: prbOk,   value: `${prbPct.toFixed(1)}%` },
      { label: `DL throughput < ${t.thpMbpsMax} Mbps`,   ok: thpOk,   value: `${thp.toFixed(2)} Mbps` },
      { label: `RLC DL delay > ${t.delayMsMin} ms`,      ok: delayOk, value: `${delay.toFixed(1)} ms` },
    ],
    triggered: prbOk && thpOk && delayOk,
  };
}

export function evaluateCco(pm: DuPmSnapshot, cfg?: Record<string, number>): TriggerEval {
  const t = { ...TRIGGER_THRESHOLDS.cco, ...(cfg ?? {}) };
  // active DU = UE 當前 serving cell(被 quota 限容量的 c0)。三者 AND 滿足 → 容量受限 → 該 HO。
  const { cell, ue } = pickServingCell(pm);
  // DRB.PdcpSduVolumeDL 是「報告窗(report_every_n_ticks 個 tick)累計量」,
  // 但 dump_pm 只給 per-tick 的 bytes_dl_this_tick。故 × report_every_n_ticks 還原成窗累計,
  // 對齊 CU/adapter 實際送出的值(例:937/tick × 4 = 3749 kbit),否則永遠少算 ~4 倍而卡在門檻下。
  const ren = pm.report_every_n_ticks || 4;
  const pdcpKbit = ((ue?.bytes_dl_this_tick ?? 0) * 8 / 1000) * ren;
  // DRB.RlcSduDelayDl:rlc_delay_ms → μs
  const rlcUs = (ue?.rlc_delay_ms_avg_this_tick ?? 0) * 1000;
  // RRU.PrbTotDl:prb_pct(%) → ppm(×10000;6% = 60000 ppm)
  const prbPpm = (cell?.prb_pct_this_tick ?? 0) * 10000;
  const volOk = pdcpKbit >= t.pdcpKbitMin;
  const delayOk = rlcUs >= t.rlcUsMin;
  const prbOk = prbPpm >= t.prbPpmMin;
  return {
    scenario: 'cco',
    conditions: [
      { label: `DRB.PdcpSduVolumeDL ≥ ${t.pdcpKbitMin} kbit`, ok: volOk,   value: `${pdcpKbit.toFixed(0)} kbit` },
      { label: `DRB.RlcSduDelayDl ≥ ${t.rlcUsMin} μs`,        ok: delayOk, value: `${rlcUs.toFixed(0)} μs` },
      { label: `RRU.PrbTotDl ≥ ${t.prbPpmMin} ppm`,           ok: prbOk,   value: `${prbPpm.toFixed(0)} ppm` },
    ],
    triggered: volOk && delayOk && prbOk,
  };
}

export function evaluateEs(pm: DuPmSnapshot, cfg?: Record<string, number>): TriggerEval {
  const t = { ...TRIGGER_THRESHOLDS.es, ...(cfg ?? {}) };
  const { cell, ue } = pickServingCell(pm);
  const prbPct = cell?.prb_pct_this_tick ?? 0;
  const thp = ue?.throughput_dl_mbps_this_tick ?? 0;
  const prbLow = prbPct < t.prbPctMax;
  const volLow = thp < t.thpMbpsMax;
  return {
    scenario: 'es',
    conditions: [
      { label: `PRB% < ${t.prbPctMax} (低載)`,                ok: prbLow, value: `${prbPct.toFixed(1)}%` },
      { label: `DL throughput < ${t.thpMbpsMax * 1000} kbps`, ok: volLow, value: `${(thp*1000).toFixed(1)} kbps` },
    ],
    triggered: prbLow && volLow,
  };
}
