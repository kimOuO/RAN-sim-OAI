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

// 改用 per-tick stats(last_cell_stats / last_ue_stats),對齊 OAI intent 真實門檻
export function evaluateIm(pm: DuPmSnapshot): TriggerEval {
  const { cell, ue } = pickServingCell(pm);
  const prbPct = cell?.prb_pct_this_tick ?? 0;
  const thp = ue?.throughput_dl_mbps_this_tick ?? 0;
  const delay = ue?.rlc_delay_ms_avg_this_tick ?? 0;
  const prbOk = prbPct > 70;
  const thpOk = thp < 5;
  const delayOk = delay > 50;
  return {
    scenario: 'im',
    conditions: [
      { label: 'PRB% > 70 (滿載)',          ok: prbOk,   value: `${prbPct.toFixed(1)}%` },
      { label: 'DL throughput < 5 Mbps',     ok: thpOk,   value: `${thp.toFixed(2)} Mbps` },
      { label: 'RLC DL delay > 50 ms',       ok: delayOk, value: `${delay.toFixed(1)} ms` },
    ],
    triggered: prbOk && thpOk && delayOk,
  };
}

export function evaluateCco(pm: DuPmSnapshot): TriggerEval {
  const entries = Object.entries(pm.last_cell_stats ?? {}).filter(([_, c]) => c.is_active);
  const pcts = entries.map(([_, c]) => c.prb_pct_this_tick);
  const hotIdx = pcts.length > 0 ? pcts.indexOf(Math.max(...pcts)) : -1;
  const coldIdx = pcts.length > 0 ? pcts.indexOf(Math.min(...pcts)) : -1;
  const hotCell = hotIdx >= 0 ? entries[hotIdx][0] : '?';
  const coldCell = coldIdx >= 0 ? entries[coldIdx][0] : '?';
  const hotPct = hotIdx >= 0 ? pcts[hotIdx] : 0;
  const coldPct = coldIdx >= 0 ? pcts[coldIdx] : 0;
  const gap = hotPct - coldPct;
  const hotOk = hotPct > 30;
  const coldOk = coldPct < 10;
  const gapOk = gap > 20;
  return {
    scenario: 'cco',
    conditions: [
      { label: `hot PRB% > 30`,        ok: hotOk,  value: `${hotCell}=${hotPct.toFixed(1)}%` },
      { label: `cold PRB% < 10`,       ok: coldOk, value: `${coldCell}=${coldPct.toFixed(1)}%` },
      { label: 'imbalance gap > 20',   ok: gapOk,  value: `${gap.toFixed(1)}` },
    ],
    triggered: gapOk && hotOk,
  };
}

export function evaluateEs(pm: DuPmSnapshot): TriggerEval {
  const { cell, ue } = pickServingCell(pm);
  const prbPct = cell?.prb_pct_this_tick ?? 0;
  const thp = ue?.throughput_dl_mbps_this_tick ?? 0;
  const prbLow = prbPct < 10;
  const volLow = thp < 0.1;
  return {
    scenario: 'es',
    conditions: [
      { label: 'PRB% < 10 (低載)',          ok: prbLow, value: `${prbPct.toFixed(1)}%` },
      { label: 'DL throughput < 100 kbps',  ok: volLow, value: `${(thp*1000).toFixed(1)} kbps` },
    ],
    triggered: prbLow && volLow,
  };
}
