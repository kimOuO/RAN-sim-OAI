'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  listScenarios, readScenario, uploadScenario, deleteScenario,
  triggerPrecompute, forceRuLiveMode, applyScenarioToScene,
  type ScenarioRow,
} from '@/services/api/scenario';
import {
  fetchDriverStatus, fetchDuPm, fetchControlActions, fetchHandovers,
  evaluateIm, evaluateCco, evaluateEs,
  type DuPmSnapshot, type ScenarioDriverStatus, type ControlActionRow,
  type HandoverEventRow, type TriggerEval,
} from '@/services/api/scenarioMonitor';
import {
  buildTrafficSeries, buildPositionZSeries, previewResolutionSec, previewSpanSec,
  normalizePositions, dominantAxis,
  type RawScenario,
} from '@/services/api/scenarioProfile';
import { startUnifiedSim, stopUnifiedSim } from '@/services/api/simLoop';
import { SignalChart } from '@/components/SignalChart';
import { ScenarioMap } from '@/components/ScenarioMap';
import { SimTimeChart } from '@/components/SimTimeChart';
import { DATASETS, datasetOf, displayName, SCENARIO_LABELS, ANR_CASE_NO } from '@/config/scenarioCatalog';

const STATUS_COLOR: Record<string, string> = {
  pending: '#64748b', running: '#f59e0b', ready: '#22c55e', failed: '#ef4444',
};

interface PresetMeta {
  id: string;
  label: string;
  desc: string;
  evaluator: (pm: DuPmSnapshot, cfg?: Record<string, number>) => TriggerEval;
  requires: { min_gnbs: number; min_cells_per_gnb: number; min_ues: number };
}

const PRESETS: PresetMeta[] = [
  { id: 'im_fast',  label: 'IM',  desc: 'PRB 滿 + channel 弱 → PRB quota cap',
    evaluator: evaluateIm,  requires: { min_gnbs: 1, min_cells_per_gnb: 1, min_ues: 1 } },
  { id: 'cco_fast', label: 'CCO', desc: 'cell 間 PRB 失衡 → handover',
    evaluator: evaluateCco, requires: { min_gnbs: 1, min_cells_per_gnb: 2, min_ues: 1 } },
  { id: 'es_fast',  label: 'ES',  desc: '低載 + 無流量 → HO + PRB cap',
    evaluator: evaluateEs,  requires: { min_gnbs: 1, min_cells_per_gnb: 1, min_ues: 1 } },
];

// scene_id → hardcoded cell config(2D map + Cell card 用)
const SCENE_LAYOUTS: Record<string, Array<{
  cell_id: string; x: number; y: number; z: number;
  azimuth_deg: number; pci: number;
  power_dbm: number; freq_ghz: number; bandwidth_mhz: number; total_prb: number;
  gnb_id: string;
}>> = {
  twocell_1gnb: [
    { cell_id: 'gnbDT_c0', x: 0, y: 30, z: 0, azimuth_deg: 0,   pci: 0,
      power_dbm: 23, freq_ghz: 3.5, bandwidth_mhz: 40, total_prb: 106, gnb_id: 'gnbDT' },
    { cell_id: 'gnbDT_c1', x: 0, y: 30, z: 0, azimuth_deg: 180, pci: 1,
      power_dbm: 23, freq_ghz: 3.5, bandwidth_mhz: 40, total_prb: 106, gnb_id: 'gnbDT' },
  ],
};

type CellLayout = {
  cell_id: string; x: number; y: number; z: number;
  azimuth_deg: number; pci: number;
  power_dbm: number; freq_ghz: number; bandwidth_mhz: number; total_prb: number;
  gnb_id: string;
};

// 地圖 / Cell card 的 cell 幾何來源:優先用劇本實際 gnbs[].cells[](真實位置/azimuth),
// 沒有才退回 hardcoded SCENE_LAYOUTS。修「c0/c1 疊同一點看不到」的根因。
function deriveCellLayout(scn: RawScenario | null): CellLayout[] {
  if (!scn) return [];
  const out: CellLayout[] = [];
  for (const g of scn.gnbs ?? []) {
    for (const c of g.cells ?? []) {
      const p = c.position ?? g.position ?? [0, 0, 0];
      out.push({
        cell_id: c.cell_id,
        x: p[0] ?? 0, y: p[1] ?? 0, z: p[2] ?? 0,
        azimuth_deg: c.azimuth_deg ?? 0, pci: c.pci ?? 0,
        power_dbm: g.power_dbm ?? 23, freq_ghz: g.frequency_ghz ?? 0,
        bandwidth_mhz: g.bandwidth_mhz ?? 0, total_prb: 106, gnb_id: g.name,
      });
    }
  }
  return out.length ? out : (SCENE_LAYOUTS[scn.scene_id] ?? []);
}

interface RunningState {
  scenarioId: string;
  sessionUuid: string;
  ratio: number;
  startedAtWallMs: number;
  scenarioStartHHMMSS: string;
}

interface CellSample {
  prb_pct: number;
  prb_count: number;
  rsrp: number;       // 從 ue 量到該 cell 的瞬時 RSRP (取 latest UE 看到的)
  sinr: number;
}
interface UeSample {
  throughput_mbps: number;
  delay_ms: number;
  mcs_dl: number;
  rsrp_serving: number;
  sinr_serving: number;
  serving_cell: string;
  bytes_this_tick: number;
  prb_this_tick: number;
}
interface OutHistorySample {
  tick: number;
  cells: Record<string, CellSample>;
  ues: Record<string, UeSample>;
}

export default function ScenariosPage() {
  const [scenarios, setScenarios] = useState<ScenarioRow[]>([]);
  // 劇本一多就找不到 → 用資料集分頁 + 關鍵字過濾(分類規則見 config/scenarioCatalog.ts)
  const [dataset, setDataset] = useState<string>('anr');
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [jsonText, setJsonText] = useState('');
  const [scenarioStart, setScenarioStart] = useState('10:00:00');

  const [running, setRunning] = useState<RunningState | null>(null);
  const [activeScenario, setActiveScenario] = useState<RawScenario | null>(null);
  const [driver, setDriver] = useState<ScenarioDriverStatus | null>(null);
  const [pm, setPm] = useState<DuPmSnapshot | null>(null);
  const [actions, setActions] = useState<ControlActionRow[]>([]);
  const [handovers, setHandovers] = useState<HandoverEventRow[]>([]);
  const [history, setHistory] = useState<OutHistorySample[]>([]);
  const [nowMs, setNowMs] = useState<number>(Date.now());
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // 偵測 driver 從 running → finished 的單次邊緣事件,防 race 重複清空。
  const autoStopFiredRef = useRef(false);
  const sawRunningRef = useRef(false);
  // Per-card chart 展開狀態 — 預設摺疊只顯示 header 1-2 行,避免 chart 大量 re-render
  // 卡死頁面。Stage 6 後對應減少前端負擔的設計。
  const [expandedCells, setExpandedCells] = useState<Set<string>>(new Set());
  const [expandedUes, setExpandedUes] = useState<Set<string>>(new Set());
  const toggleSet = (s: Set<string>, id: string): Set<string> => {
    const next = new Set(s);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  };

  // Map<scenario_id, { raw, updatedAt }>:用 updated_at 當 cache key,只要 DB 有改就 refetch。
  // 之前只用 `Map<id, raw>` + 「沒在 Map 才抓」的策略,DB 改完 raw_json 後前端永遠
  // 看不到變化(例如 1hr 劇本清空 buildings 後卡片仍顯示舊資料)。
  const [scenarioDetails, setScenarioDetails] = useState<
    Map<string, { raw: RawScenario; updatedAt: string }>
  >(new Map());

  const reload = async () => {
    try { setScenarios(await listScenarios()); }
    catch (e: any) { setError(e?.message ?? 'list failed'); }
  };
  // 沒在跑時清單不會變,3 秒輪詢只是白白觸發整頁 re-render → 拉長到 15 秒。
  useEffect(() => {
    reload();
    const t = setInterval(reload, running ? 3000 : 15000);
    return () => clearInterval(t);
  }, [running]);

  // 切 page 離開再回來時,本地 `running` state 會歸零,即使 driver 還在跑也只看到
  // pre-sim 列表。mount 時 query driver,若 running 就從 sessionStorage 拿 onRun 當時
  // 寫進去的 sessionUuid / scenarioStart,組回 RunningState 重啟監控視圖。
  // sessionStorage key = `scenarios:run` — onRun 寫、onStop 清。
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const d = await fetchDriverStatus().catch(() => null);
      if (cancelled || !d?.running || !d.scenario_id) return;
      // 已經有 running state(剛 onRun 完同一 mount)→ 不覆蓋
      if (running) return;
      let saved: { sessionUuid: string; scenarioStartHHMMSS: string; startedAtWallMs: number } | null = null;
      try {
        const raw = sessionStorage.getItem('scenarios:run');
        if (raw) saved = JSON.parse(raw);
      } catch { /* ignore */ }
      const ratio = Math.max(1, Math.round(d.sim_speed_x || 1));
      // Backend driver.state expose 的是 started_at_ms (wall-clock 開跑時間);
      // 沒有 elapsed_wall_sec。讀 started_at_ms 直接還原 wall-clock 起點,讓
      // dispatcher / 第三方派的 sim 也能正確顯示「已跑 X 分鐘」。
      const startedAtWallMs = saved?.startedAtWallMs
        ?? d.started_at_ms
        ?? Date.now();
      const sessionUuid = saved?.sessionUuid ?? `runs_${d.scenario_id}_${startedAtWallMs}`;
      try {
        const sc = await readScenario(d.scenario_id);
        const raw: RawScenario = sc?.raw_json || sc;
        if (cancelled) return;
        setActiveScenario(raw);
      } catch { /* scenario 抓不到也不擋 — 監控圖會少 input chart */ }
      setRunning({
        scenarioId: d.scenario_id,
        sessionUuid,
        ratio,
        startedAtWallMs,
        scenarioStartHHMMSS: saved?.scenarioStartHHMMSS ?? scenarioStart,
      });
    })();
    return () => { cancelled = true; };
  // mount only — running 變化由 onRun/onStop 自己處理
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 抓所有 scenario 的 raw_json 給 card 預覽用。
  // refetch 條件:(a) 還沒抓過,或 (b) list 回的 updated_at 比 cache 裡的新
  // 否則 DB 改完 raw_json 後 cache 永遠不更新,卡片看到的是 mount 那一刻的資料。
  useEffect(() => {
    let cancelled = false;
    (async () => {
      // 只抓「畫面上看得到的」——presets + 目前資料集。全抓是 15 份 ≈ 3MB,
      // 但同一時間只會顯示一個資料集,其餘等切過去再抓(切完才抓也只是一次 fetch)。
      const needed = new Set([
        ...PRESETS.map(p => p.id),
        ...scenarios.filter(v => datasetOf(v.scenario_id) === dataset).map(v => v.scenario_id),
      ]);
      const stale = scenarios.filter(s => {
        if (!needed.has(s.scenario_id)) return false;
        const cached = scenarioDetails.get(s.scenario_id);
        return !cached || cached.updatedAt !== s.updated_at;
      });
      if (stale.length === 0) return;
      const results = await Promise.all(
        stale.map(async (s) => {
          try {
            const d = await readScenario(s.scenario_id);
            const raw = (d?.raw_json || d) as RawScenario;
            return [s.scenario_id, { raw, updatedAt: s.updated_at }] as const;
          } catch { return [s.scenario_id, null] as const; }
        }),
      );
      if (cancelled) return;
      setScenarioDetails(prev => {
        const m = new Map(prev);
        for (const [id, entry] of results) if (entry) m.set(id, entry);
        return m;
      });
    })();
    return () => { cancelled = true; };
  }, [scenarios, dataset]);

  useEffect(() => {
    if (!running) return;
    const poll = async () => {
      const [d, p, a, ho] = await Promise.all([
        fetchDriverStatus().catch(() => null),
        fetchDuPm().catch(() => null),
        fetchControlActions(running.sessionUuid),
        fetchHandovers(running.sessionUuid),
      ]);
      if (d) setDriver(d);
      if (p) setPm(p);
      setActions(a); setHandovers(ho); setNowMs(Date.now());
      // Auto-stop:driver 從 running → false 的邊緣 → scenario 跑完(或自然中止)。
      // 用 sawRunningRef 確認真的看過 true 才算 transition,避免剛 mount 那一拍
      // 還沒有 driver state 就被誤判成已停。autoStopFiredRef 防止後續 poll 重複觸發。
      if (d) {
        if (d.running) sawRunningRef.current = true;
        else if (sawRunningRef.current && !autoStopFiredRef.current) {
          autoStopFiredRef.current = true;
          void autoStopOnFinish();
        }
      }
      // 推 history sample — 用 per-tick stats(非 cumulative)
      if (d && p) {
        const ueStats = p.last_ue_stats ?? {};
        const cellStats = p.last_cell_stats ?? {};
        const ueLatest = p.ue_latest ?? {};

        // per-cell:PRB% 用 last_cell_stats;RSRP/SINR 從 UE 看 cell 的角度抽
        const cellsOut: Record<string, CellSample> = {};
        for (const [cellId, cs] of Object.entries(cellStats)) {
          cellsOut[cellId] = {
            prb_pct: cs.prb_pct_this_tick,
            prb_count: cs.prb_used_this_tick,
            rsrp: 0, sinr: 0,
          };
        }
        // 從 UE 視角填 cell RSRP / SINR
        for (const ueData of Object.values(ueLatest)) {
          if (ueData.serving_cell && cellsOut[ueData.serving_cell]) {
            if (typeof ueData.rsrp_dbm === 'number') cellsOut[ueData.serving_cell].rsrp = ueData.rsrp_dbm;
            if (typeof ueData.sinr_db === 'number') cellsOut[ueData.serving_cell].sinr = ueData.sinr_db;
          }
          for (const nb of ueData.neighbors || []) {
            if (cellsOut[nb.cell_id] && typeof nb.rsrp_dbm === 'number') {
              cellsOut[nb.cell_id].rsrp = nb.rsrp_dbm;
            }
          }
        }

        // per-UE:從 last_ue_stats 取 per-tick throughput / delay / MCS
        const uesOut: Record<string, UeSample> = {};
        for (const [ueId, us] of Object.entries(ueStats)) {
          uesOut[ueId] = {
            throughput_mbps: us.throughput_dl_mbps_this_tick,
            delay_ms: us.rlc_delay_ms_avg_this_tick,
            mcs_dl: us.mcs_dl,
            rsrp_serving: us.rsrp_dbm,
            sinr_serving: us.sinr_db,
            serving_cell: us.serving_cell,
            bytes_this_tick: us.bytes_dl_this_tick,
            prb_this_tick: us.prb_dl_this_tick,
          };
        }

        const sample: OutHistorySample = {
          tick: Math.round(d.elapsed_sim_sec),
          cells: cellsOut,
          ues: uesOut,
        };
        setHistory((prev) => {
          const out = [...prev, sample];
          return out.length > 180 ? out.slice(-180) : out;
        });
      }
    };
    poll();
    pollRef.current = setInterval(poll, 1000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [running]);

  const addSecToHMS = (hms: string, addSec: number): string => {
    const [h, m, s] = hms.split(':').map(Number);
    const total = (h * 3600 + m * 60 + s) + Math.floor(addSec);
    const hh = Math.floor(total / 3600) % 24;
    const mm = Math.floor((total % 3600) / 60);
    const ss = total % 60;
    return `${String(hh).padStart(2,'0')}:${String(mm).padStart(2,'0')}:${String(ss).padStart(2,'0')}`;
  };
  const formatWallHMS = (ms: number) => {
    const d = new Date(ms);
    return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;
  };

  // ── handlers ──────────────────────────────────────
  const onUpload = async () => {
    setError(''); setBusy(true);
    try {
      const obj = JSON.parse(jsonText);
      const row = await uploadScenario(obj);
      await reload(); setJsonText('');
      setError(`✓ Uploaded ${row.scenario_id}`);
    } catch (e: any) { setError(`upload failed: ${e?.message ?? e}`); }
    finally { setBusy(false); }
  };

  const onPrecompute = async (id: string) => {
    setBusy(true); setError('');
    try { await triggerPrecompute(id); await reload();
          setError(`✓ Precompute started for ${id}`); }
    catch (e: any) { setError(`precompute failed: ${e?.message ?? e}`); }
    finally { setBusy(false); }
  };

  const onDelete = async (id: string) => {
    if (!confirm(`Delete scenario ${id}?`)) return;
    setBusy(true);
    try { await deleteScenario(id); await reload(); }
    catch (e: any) { setError(`delete failed: ${e?.message ?? e}`); }
    finally { setBusy(false); }
  };

  const onRun = async (s: ScenarioRow, ratio: number, forceLive: boolean = false) => {
    setBusy(true); setError('');
    // 新一輪 run:重置 auto-stop 偵測,確保下次 driver running→false 能再次觸發
    autoStopFiredRef.current = false;
    sawRunningRef.current = false;
    try {
      const wallTickMs = Math.max(10, Math.round(s.tick_ms / ratio));
      const sessionUuid = `runs_${s.scenario_id}_${Date.now()}`;
      const startedAtWallMs = Date.now();
      // 先抓 scenario raw_json 給 input chart 用
      const sc = await readScenario(s.scenario_id);
      const raw: RawScenario = sc?.raw_json || sc;
      setActiveScenario(raw);
      setHistory([]);
      // 把劇本拓樸寫進 Omniverse 場景表 → Scene Editor 的 Scene Layout / 3D 反映此劇本。
      // (start 流程原本只 readScenario 不寫場景表,所以「開劇本」後 editor 看不到對應場景)
      try { await applyScenarioToScene(s.scenario_id); }
      catch (e) { console.warn('applyScenarioToScene failed (場景未映射,不影響 sim):', e); }
      // Stage 統一架構:走 SimController.start(source=scenario),它內部建 SimSession +
      // 廣播 speed 給 DU/CU + 反向 sync scenario → DB + UE attach + lifecycle start。
      const res = await startUnifiedSim({
        source: 'scenario', scenario_id: s.scenario_id, speed_x: ratio, sim_dt_ms: 250,
      });
      // forceLive:scenario_driver 若 precompute_status==ready 會自動切 cached,
      // 在 start 完成「之後」呼 set_channel_mode=live 覆寫,繞過 cached SINR bug
      // 或單純想跑 Sionna 即時 ray tracing 對齊真實物理。
      if (forceLive) {
        try { await forceRuLiveMode(); }
        catch (e) { console.warn('forceRuLiveMode failed', e); }
      }
      const actualSession = res?.session_uuid || sessionUuid;
      setRunning({
        scenarioId: s.scenario_id, sessionUuid: actualSession, ratio,
        startedAtWallMs, scenarioStartHHMMSS: scenarioStart,
      });
      // 存到 sessionStorage,讓使用者切走又切回 /scenarios 時 mount effect 能還原監控視圖
      try {
        sessionStorage.setItem('scenarios:run', JSON.stringify({
          sessionUuid, scenarioStartHHMMSS: scenarioStart, startedAtWallMs,
        }));
      } catch { /* quota / private mode 忽略 */ }
      const modeTag = forceLive ? ' (Live)' : '';
      setError(`✓ ${s.scenario_id} @ ${ratio}x${modeTag} — session=${sessionUuid}`);
    } catch (e: any) { setError(`start failed: ${e?.message ?? e}`); }
    finally { setBusy(false); }
  };

  const onStop = async () => {
    setBusy(true);
    try {
      await stopUnifiedSim();
      setRunning(null); setActiveScenario(null);
      setDriver(null); setPm(null); setActions([]); setHandovers([]); setHistory([]);
      autoStopFiredRef.current = false; sawRunningRef.current = false;
      try { sessionStorage.removeItem('scenarios:run'); } catch { /* ignore */ }
    } catch (e: any) { setError(`stop failed: ${e?.message ?? e}`); }
    finally { setBusy(false); }
  };

  // 劇本自然跑完時的 cleanup — 等同 onStop 但不擋 UI(不 setBusy),
  // 也補送 stopUnifiedSim 確保後端 sim_orchestrator residual state 收乾淨。
  const autoStopOnFinish = async () => {
    try { await stopUnifiedSim(); } catch { /* driver 已停,呼叫失敗可忽略 */ }
    setRunning(null); setActiveScenario(null);
    setDriver(null); setPm(null); setActions([]); setHandovers([]); setHistory([]);
    try { sessionStorage.removeItem('scenarios:run'); } catch { /* ignore */ }
    setError('✓ scenario finished — reset to pre-sim view');
  };

  // ── derived ─────────────────────────────────────────
  const presetIds = new Set(PRESETS.map(p => p.id));
  // 資料集分頁:先算各集數量(空的分頁也顯示,標 0 才知道沒東西不是壞了),再過濾
  const datasetCounts = DATASETS.reduce<Record<string, number>>((acc, d) => {
    acc[d.id] = scenarios.filter(s => datasetOf(s.scenario_id) === d.id).length;
    return acc;
  }, {});
  const activeDataset = DATASETS.find(d => d.id === dataset) ?? DATASETS[0];
  const q = query.trim().toLowerCase();
  const visibleScenarios = scenarios
    .filter(s => datasetOf(s.scenario_id) === dataset)
    .filter(s => !q || s.scenario_id.toLowerCase().includes(q)
                 || (SCENARIO_LABELS[s.scenario_id]?.label ?? '').toLowerCase().includes(q)
                 || (SCENARIO_LABELS[s.scenario_id]?.desc ?? '').toLowerCase().includes(q))
    // ANR 依題號排,其他依 id
    .sort((a, b) => {
      const na = ANR_CASE_NO[a.scenario_id], nb = ANR_CASE_NO[b.scenario_id];
      if (na && nb) return na - nb;
      if (na) return -1;
      if (nb) return 1;
      return a.scenario_id.localeCompare(b.scenario_id);
    });
  // 配 PRESETS:先試 exact match,再退到 prefix(im_/cco_/es_)讓 *_1hr 變體共用 IM/CCO/ES preset
  const getPreset = (id: string) => {
    const exact = PRESETS.find(p => p.id === id);
    if (exact) return exact;
    if (!id) return undefined;
    const lower = id.toLowerCase();
    if (lower.startsWith('im_')) return PRESETS.find(p => p.id === 'im_fast');
    if (lower.startsWith('cco_')) return PRESETS.find(p => p.id === 'cco_fast');
    if (lower.startsWith('es_')) return PRESETS.find(p => p.id === 'es_fast');
    return undefined;
  };
  const trigEval = (pm && running) ? getPreset(running.scenarioId)?.evaluator(pm, driver?.trigger_config) : null;
  const driverPct = driver?.sim_tick_idx && driver?.total_ticks
    ? (driver.sim_tick_idx / Math.max(1, driver.total_ticks)) * 100
    : 0;
  // 後端新 driver state 沒 expose elapsed_sim_sec — 從 wall-clock 跑的時間 × ratio 直接推:
  // 速率 2x → wall 跑 5s = sim 跑 10s。Fallback 用 driver.elapsed_sim_sec(舊路徑)。
  const simNowSec = running
    ? ((nowMs - running.startedAtWallMs) / 1000) * running.ratio
    : (driver?.elapsed_sim_sec ?? 0);

  // Input charts(from activeScenario raw_json)
  const trafficData  = useMemo(() => activeScenario ? buildTrafficSeries(activeScenario, 1) : [], [activeScenario]);
  const positionData = useMemo(() => activeScenario ? buildPositionZSeries(activeScenario, 1) : [], [activeScenario]);

  // Output:per-cell + per-UE 分開
  const allCellIds = Array.from(new Set(history.flatMap(h => Object.keys(h.cells))));
  const allUeIds   = Array.from(new Set(history.flatMap(h => Object.keys(h.ues))));

  // Cell chart:PRB% + cell aggregate DL Mbps(dual axis)
  // dl_agg 需要從 history 重算(per-cell sum 過 UE serving)
  const cellAggDlMbps = (h: OutHistorySample, cellId: string): number => {
    let sum = 0;
    for (const u of Object.values(h.ues)) {
      if (u.serving_cell === cellId) sum += u.throughput_mbps;
    }
    return sum;
  };
  const cellChartData = (cellId: string) => history.map(h => ({
    tick: h.tick,
    prb_pct: h.cells[cellId]?.prb_pct ?? 0,
    dl_mbps: cellAggDlMbps(h, cellId),
  }));

  // UE chart:RSRP per cell(此 UE 看到的)+ SINR(serving)+ Thp + Delay
  const ueChartData = (ueId: string) => history.map(h => {
    const row: Record<string, number> = {
      tick: h.tick,
      sinr: h.ues[ueId]?.sinr_serving ?? 0,
      throughput: h.ues[ueId]?.throughput_mbps ?? 0,
      delay: h.ues[ueId]?.delay_ms ?? 0,
    };
    // per-cell RSRP(從 cells.<cellId>.rsrp,只要 cell entry 有值都算)
    for (const cellId of Object.keys(h.cells)) {
      row[`rsrp_${cellId}`] = h.cells[cellId]?.rsrp ?? 0;
    }
    return row;
  });

  // handover events → vertical reference lines(以 sim-sec offset 算)
  const hoMarkers = handovers.map(h => {
    if (!h.event_ts || !running) return null;
    const wallMs = new Date(h.event_ts).getTime();
    const wallElapsed = (wallMs - running.startedAtWallMs) / 1000;
    return { tick: Math.round(wallElapsed * running.ratio),
             color: '#ef4444', label: `HO ${h.source_cell}→${h.target_cell}` };
  }).filter(Boolean) as Array<{ tick: number; color: string; label?: string }>;

  // ScenarioMap data
  const mapUes   = activeScenario?.ues.map(u => ({ name: u.name, positions: u.positions })) ?? [];
  const mapCells = deriveCellLayout(activeScenario);

  // ── render ─────────────────────────────────────────
  return (
    <div style={{ maxWidth: 1300, margin: '0 auto', padding: 24 }}>
      <h1>Scenarios — Fast-Replay</h1>
      <p style={{ color: '#94a3b8', fontSize: 13 }}>
        上傳 / 預設劇本 + Fast Run 監控 — 一個頁面看完整 input(traffic、UE 位置)→ output(KPM、RSRP、SINR、handover)。
      </p>

      {error && (
        <div style={{
          padding: '8px 12px', margin: '12px 0', borderRadius: 4,
          background: error.startsWith('✓') ? '#064e3b' : '#7f1d1d',
          color: error.startsWith('✓') ? '#a7f3d0' : '#fecaca', fontSize: 13,
        }}>{error}</div>
      )}

      {!running && (
        <>
          {/* Upload + scenario start time */}
          <section style={{ marginTop: 8, padding: 14, background: '#0f172a', borderRadius: 8 }}>
            <h3 style={{ marginTop: 0, fontSize: 14 }}>Upload Scenario</h3>
            <textarea
              value={jsonText} onChange={(e) => setJsonText(e.target.value)}
              placeholder='{"scenario_id":"my_test","scene_id":"twocell_1gnb","duration_sec":60,"tick_ms":500,"default_serving_cell":"gnbDT_c0","ues":[...],"traffic":[...]}'
              style={{
                width: '100%', minHeight: 70, padding: 8, background: '#020617',
                border: '1px solid #334155', borderRadius: 4, color: '#e5e7eb',
                fontFamily: 'ui-monospace, monospace', fontSize: 11,
              }}
            />
            <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <button onClick={onUpload} disabled={busy || !jsonText.trim()} style={btn('#3b82f6')}>
                Upload from text
              </button>
              <label style={{ ...btn('#475569'), display: 'inline-block' }}>
                Load .json file
                <input type="file" accept=".json,application/json" style={{ display: 'none' }}
                  onChange={async (e) => {
                    const f = e.target.files?.[0]; if (!f) return;
                    const txt = await f.text(); setJsonText(txt);
                    setError(`Loaded ${f.name} — review then click Upload`);
                  }} />
              </label>
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, color: '#94a3b8' }}>劇本對應時間起點:</span>
                <input type="time" step="1" value={scenarioStart}
                  onChange={(e) => setScenarioStart(e.target.value)}
                  style={{
                    padding: '4px 8px', background: '#020617', border: '1px solid #334155',
                    borderRadius: 3, color: '#e5e7eb', fontSize: 12,
                  }} />
              </div>
            </div>
          </section>

          {/* 資料集分頁 + Preset + 劇本卡 */}
          <section style={{ marginTop: 16 }}>
            <h3 style={{ fontSize: 14 }}>Preset Scenarios</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              {PRESETS.map((p) => (
                <ScenarioCard
                  key={p.id} preset={p}
                  scenario={scenarios.find(s => s.scenario_id === p.id)}
                  rawJson={scenarioDetails.get(p.id)?.raw}
                  scenarioStart={scenarioStart}
                  busy={busy}
                  onRun={onRun} onPrecompute={onPrecompute} onDelete={onDelete}
                />
              ))}
            </div>

            {/* ── 資料集(dataset)分頁 ───────────────────────────── */}
            <div style={{ marginTop: 24, display: 'flex', alignItems: 'center',
                          gap: 8, flexWrap: 'wrap' }}>
              {DATASETS.map(d => {
                const on = d.id === dataset;
                return (
                  <button key={d.id} onClick={() => setDataset(d.id)}
                    style={{
                      padding: '6px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 13,
                      background: on ? d.color : '#0f172a',
                      color: on ? '#020617' : '#cbd5e1',
                      border: `1px solid ${on ? d.color : '#334155'}`,
                      fontWeight: on ? 700 : 400,
                    }}>
                    {d.label}
                    <span style={{ marginLeft: 6, opacity: 0.75, fontSize: 11 }}>
                      {datasetCounts[d.id] ?? 0}
                    </span>
                  </button>
                );
              })}
              <input value={query} onChange={e => setQuery(e.target.value)}
                placeholder="搜尋劇本 id / 題名…"
                style={{
                  marginLeft: 'auto', padding: '5px 10px', minWidth: 200,
                  background: '#020617', border: '1px solid #334155',
                  borderRadius: 6, color: '#e5e7eb', fontSize: 12,
                }} />
            </div>
            <p style={{ fontSize: 11, color: '#94a3b8', margin: '6px 2px 12px' }}>
              {activeDataset.desc}
            </p>

            {visibleScenarios.length === 0 ? (
              <p style={{ fontSize: 12, color: '#64748b' }}>
                此資料集沒有劇本{q ? '(或關鍵字無相符)' : ''}。
              </p>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                {visibleScenarios.map((s) => (
                  <ScenarioCard
                    key={s.scenario_id} scenario={s}
                    rawJson={scenarioDetails.get(s.scenario_id)?.raw}
                    scenarioStart={scenarioStart}
                    busy={busy}
                    onRun={onRun} onPrecompute={onPrecompute} onDelete={onDelete}
                  />
                ))}
              </div>
            )}
          </section>
        </>
      )}

      {/* Running monitor */}
      {running && (
        <section style={{ marginTop: 12 }}>
          {/* Header bar with dual clocks */}
          <div style={{
            padding: 14, background: '#0f172a', border: '1px solid #1e3a8a', borderRadius: 8,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: 14, color: '#dbeafe' }}>
                ⚡ <strong>{running.scenarioId}</strong> @ {running.ratio}x
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                session: {running.sessionUuid}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <ClockBlock label="Wall(現實)" color="#cbd5e1" main={formatWallHMS(nowMs)}
                sub={`跑了 ${((nowMs - running.startedAtWallMs) / 1000).toFixed(1)}s`} />
              <ClockBlock label="Sim(劇本)" color="#fde68a"
                main={addSecToHMS(running.scenarioStartHHMMSS, simNowSec)}
                sub={`已過 ${simNowSec.toFixed(1)}s 劇本時間`} />
              <button onClick={onStop} disabled={busy} style={{ ...btn('#ef4444'), padding: '8px 14px' }}>
                ⏹ Stop
              </button>
            </div>
          </div>

          {/* Driver progress + Trigger eval */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 10, marginTop: 10 }}>
            <Panel title="Driver Progress">
              {driver && (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#94a3b8' }}>
                    <span>tick {driver.sim_tick_idx} / {driver.total_ticks}</span>
                    <span>pushes {driver.position_push_count} · injects {driver.inject_call_count}</span>
                  </div>
                  <div style={{ marginTop: 6, height: 6, background: '#1f2937', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ width: `${driverPct}%`, height: '100%', background: '#3b82f6' }} />
                  </div>
                </>
              )}
            </Panel>
            <Panel title="KPM Trigger Eval">
              {trigEval ? (
                <>
                  <span style={{
                    display: 'inline-block', padding: '3px 8px', borderRadius: 3, fontSize: 11,
                    background: trigEval.triggered ? '#064e3b' : '#7f1d1d',
                    color: trigEval.triggered ? '#a7f3d0' : '#fecaca',
                  }}>
                    {trigEval.triggered ? '✓ TRIGGERED' : '✗ not yet'}
                  </span>
                  <ul style={{ margin: '4px 0 0', padding: 0, listStyle: 'none' }}>
                    {trigEval.conditions.map((c, i) => (
                      <li key={i} style={{ fontSize: 10, marginTop: 2, color: c.ok ? '#a7f3d0' : '#fecaca' }}>
                        {c.ok ? '✓' : '✗'} {c.label}: <strong>{c.value}</strong>
                      </li>
                    ))}
                  </ul>
                </>
              ) : <span style={{ color: '#64748b', fontSize: 12 }}>等 PM…</span>}
            </Panel>
          </div>

          {/* INPUT panel: 流量 + UE 位置 — 都帶 cursor 指當下 sim-time */}
          <Panel title="📥 INPUT(劇本灌的東西)" margin>
            {(() => {
              // 抽 traffic series keys
              const trafficKeys = trafficData.length > 0
                ? Object.keys(trafficData[trafficData.length-1]).filter(k => k !== 'tick') : [];
              const positionKeys = positionData.length > 0
                ? Object.keys(positionData[positionData.length-1]).filter(k => k !== 'tick') : [];
              const TR_COLORS = ['#22c55e', '#ec4899', '#0ea5e9', '#f59e0b'];
              const trafficLeft = trafficKeys.map((k, i) => ({
                key: k, label: k.replace('_dl', ' DL kbps'),
                color: TR_COLORS[i % TR_COLORS.length],
              }));
              const positionLeft = positionKeys.map((k, i) => ({
                key: k, label: k.replace('_z', ' z(m)'),
                color: TR_COLORS[i % TR_COLORS.length],
              }));
              return (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 12 }}>
                    <div>
                      <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
                        DL kbps per UE — 沿 sim-time 軸(紅線 = 目前 sim cursor)
                      </div>
                      <SimTimeChart
                        data={trafficData as any}
                        scenarioStart={running.scenarioStartHHMMSS}
                        leftSeries={trafficLeft}
                        leftLabel="kbps"
                        height={150}
                        cursor={Math.round(simNowSec)}
                      />
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>UE 位置(top-down map)</div>
                      {mapCells.length > 0
                        ? <ScenarioMap ues={mapUes} cells={mapCells} simT={simNowSec} />
                        : <div style={{ color: '#64748b', fontSize: 11 }}>scene "{activeScenario?.scene_id}" 無 layout 對映</div>
                      }
                    </div>
                  </div>
                </>
              );
            })()}
          </Panel>

          {/* OUTPUT panel — 精簡版:Cell card + UE card,各 1 個 chart */}
          <Panel title={`📤 OUTPUT — Cell × UE 瞬時狀態`} margin>
            <div style={{ fontSize: 10, color: '#64748b', marginBottom: 8 }}>
              所有數據 = 上一 tick(sim_dt {pm?.sim_dt_ms ?? 500}ms)瞬時值,非累積。
              X 軸 = sim-time HH:MM:SS。紅 dash 線 = handover 事件。
            </div>

            {/* Per-Cell grid */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
              <div style={{ fontSize: 11, color: '#cbd5e1', fontWeight: 600 }}>
                📡 Cell 狀態({allCellIds.length})— 點 card 展開圖表
              </div>
              <button
                onClick={() => setExpandedCells(
                  expandedCells.size === allCellIds.length ? new Set() : new Set(allCellIds),
                )}
                style={{
                  marginLeft: 'auto', padding: '2px 8px', fontSize: 10,
                  background: '#1e293b', color: '#cbd5e1',
                  border: '1px solid #334155', borderRadius: 3, cursor: 'pointer',
                }}
              >
                {expandedCells.size === allCellIds.length ? '全部摺疊' : '全部展開'}
              </button>
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${Math.min(2, allCellIds.length)}, 1fr)`,
              gap: 8, marginTop: 4,
            }}>
              {allCellIds.map((cid) => {
                const cur = pm?.last_cell_stats?.[cid];
                const cfg = mapCells.find(c => c.cell_id === cid);
                const dlAgg = cur?.dl_aggregate_mbps_this_tick ?? 0;
                const isActive = cur?.is_active ?? true;
                const isExpanded = expandedCells.has(cid);
                return (
                  <div key={cid}
                    onClick={() => setExpandedCells(s => toggleSet(s, cid))}
                    style={{
                      padding: 10, background: '#0f172a',
                      border: `1px solid ${isActive ? '#1e293b' : '#7f1d1d'}`, borderRadius: 4,
                      cursor: 'pointer', transition: 'border-color 0.15s',
                    }}>
                    {/* Static config 1 行 */}
                    <div style={{ fontSize: 11, color: '#fde68a', fontFamily: 'ui-monospace,monospace' }}>
                      <span style={{ color: '#64748b', marginRight: 4 }}>{isExpanded ? '▼' : '▶'}</span>
                      📡 <strong>{cid}</strong>
                      {cfg && (
                        <span style={{ color: '#94a3b8', fontWeight: 'normal' }}>
                          {' '}· PCI {cfg.pci} · az {cfg.azimuth_deg}° · {cfg.power_dbm}dBm ·
                          {' '}{cfg.freq_ghz}GHz/{cfg.bandwidth_mhz}MHz · {cfg.total_prb} PRB
                        </span>
                      )}
                    </div>
                    {/* Live snapshot 1 行 */}
                    <div style={{ fontSize: 11, color: isActive ? '#a7f3d0' : '#fca5a5', marginTop: 4 }}>
                      ⚡ {isActive ? '✓ active' : '⛔ disabled'}
                      {cur && (
                        <>
                          {' · '}PRB <strong>{cur.prb_used_this_tick}</strong>/{cur.prb_total} ({cur.prb_pct_this_tick.toFixed(1)}%)
                          {' · '}attached <strong>{cur.attached_ue_count ?? 0}</strong>
                          {' · '}DL <strong>{dlAgg.toFixed(2)}</strong> Mbps
                          {(cur.quota_cap_factor ?? 1.0) < 1.0 && (
                            <span style={{ color: '#fbbf24', marginLeft: 4 }}>· xApp capped {(cur.quota_max_prb_pct ?? 100).toFixed(0)}%</span>
                          )}
                        </>
                      )}
                    </div>
                    {/* Chart:展開才 render(避免大量 SVG 重畫卡 UI)*/}
                    {isExpanded && (
                      <div style={{ marginTop: 8 }} onClick={(e) => e.stopPropagation()}>
                        <SimTimeChart
                          data={cellChartData(cid)}
                          scenarioStart={running.scenarioStartHHMMSS}
                          leftSeries={[
                            { key: 'prb_pct', label: 'PRB %', color: '#f59e0b' },
                          ]}
                          rightSeries={[
                            { key: 'dl_mbps', label: 'DL aggregate (Mbps)', color: '#22c55e' },
                          ]}
                          leftLabel="%" rightLabel="Mbps"
                          height={150}
                          cursor={Math.round(simNowSec)}
                          markers={hoMarkers}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Per-UE grid */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
              <div style={{ fontSize: 11, color: '#cbd5e1', fontWeight: 600 }}>
                📱 UE 狀態({allUeIds.length})— 點 card 展開圖表
              </div>
              <button
                onClick={() => setExpandedUes(
                  expandedUes.size === allUeIds.length ? new Set() : new Set(allUeIds),
                )}
                style={{
                  marginLeft: 'auto', padding: '2px 8px', fontSize: 10,
                  background: '#1e293b', color: '#cbd5e1',
                  border: '1px solid #334155', borderRadius: 3, cursor: 'pointer',
                }}
              >
                {expandedUes.size === allUeIds.length ? '全部摺疊' : '全部展開'}
              </button>
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${Math.min(2, allUeIds.length)}, 1fr)`,
              gap: 8, marginTop: 4,
            }}>
              {allUeIds.map((uid) => {
                const cur = pm?.last_ue_stats?.[uid];
                // 從 scenario 內插當下 UE 位置(顯示給工程師)
                let curPos: [number, number, number] = [0, 0, 0];
                if (activeScenario) {
                  const ueScn = activeScenario.ues.find(u => u.name === uid);
                  if (ueScn) {
                    const t = simNowSec;
                    if (ueScn.positions.length > 0) {
                      if (t <= ueScn.positions[0][0])
                        curPos = [ueScn.positions[0][1], ueScn.positions[0][2], ueScn.positions[0][3]];
                      else if (t >= ueScn.positions[ueScn.positions.length-1][0]) {
                        const p = ueScn.positions[ueScn.positions.length-1];
                        curPos = [p[1], p[2], p[3]];
                      } else {
                        for (let i = 0; i < ueScn.positions.length-1; i++) {
                          const a = ueScn.positions[i], b = ueScn.positions[i+1];
                          if (a[0] <= t && t <= b[0]) {
                            const r = b[0] === a[0] ? 0 : (t-a[0])/(b[0]-a[0]);
                            curPos = [a[1]+(b[1]-a[1])*r, a[2]+(b[2]-a[2])*r, a[3]+(b[3]-a[3])*r];
                            break;
                          }
                        }
                      }
                    }
                  }
                }
                const rsrpSeries = allCellIds.map((cid, ci) => ({
                  key: `rsrp_${cid}`, label: `RSRP ${cid}`,
                  color: ['#0ea5e9', '#ec4899', '#a855f7', '#f97316'][ci % 4],
                }));
                const isExpanded = expandedUes.has(uid);
                return (
                  <div key={uid}
                    onClick={() => setExpandedUes(s => toggleSet(s, uid))}
                    style={{
                      padding: 10, background: '#0f172a',
                      border: '1px solid #1e293b', borderRadius: 4,
                      cursor: 'pointer', transition: 'border-color 0.15s',
                    }}>
                    {/* Static info 1 行 */}
                    <div style={{ fontSize: 11, color: '#a7f3d0', fontFamily: 'ui-monospace,monospace' }}>
                      <span style={{ color: '#64748b', marginRight: 4 }}>{isExpanded ? '▼' : '▶'}</span>
                      📱 <strong>{uid}</strong>
                      {cur && (
                        <span style={{ color: '#94a3b8', fontWeight: 'normal' }}>
                          {' '}· serving <strong>{cur.serving_cell}</strong>
                          {' '}· MCS {cur.mcs_dl}
                          {' '}· pos ({curPos[0].toFixed(0)}, {curPos[1].toFixed(1)}, {curPos[2].toFixed(0)})
                        </span>
                      )}
                    </div>
                    {/* Live snapshot 1 行 */}
                    {cur && (
                      <div style={{ fontSize: 11, color: '#cbd5e1', marginTop: 4 }}>
                        ⚡ Thp <strong>{cur.throughput_dl_mbps_this_tick.toFixed(2)}</strong> Mbps
                        {' · '}Delay <strong>{cur.rlc_delay_ms_avg_this_tick.toFixed(1)}</strong> ms
                        {' · '}buffer <strong>{(cur.rlc_buffer_bo_this_tick/1024).toFixed(1)}</strong> KB
                        {' · '}SINR <strong>{cur.sinr_db.toFixed(1)}</strong> dB
                      </div>
                    )}
                    {/* Chart:展開才 render(避免 4-line SVG × N UE 卡 UI)*/}
                    {isExpanded && (
                      <div style={{ marginTop: 8 }} onClick={(e) => e.stopPropagation()}>
                        <SimTimeChart
                          data={ueChartData(uid)}
                          scenarioStart={running.scenarioStartHHMMSS}
                          leftSeries={[
                            ...rsrpSeries,
                            { key: 'sinr', label: 'SINR (serving)', color: '#fbbf24' },
                          ]}
                          rightSeries={[
                            { key: 'throughput', label: 'Thp (Mbps)', color: '#22c55e' },
                            { key: 'delay',      label: 'Delay (ms)', color: '#ef4444' },
                          ]}
                          leftLabel="dB" rightLabel="Mbps/ms"
                          height={180}
                          cursor={Math.round(simNowSec)}
                          markers={hoMarkers}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </Panel>

          {/* KPM Threshold Log — 只顯示本場 scenario 對應 intent 的觸發門檻 */}
          <Panel title="📊 KPM 門檻檢查(xApp intent 觸發條件)" margin>
            {(() => {
              const preset = getPreset(running.scenarioId);
              if (!pm) return <span style={{ color: '#64748b', fontSize: 11 }}>等 PM…</span>;
              if (!preset) {
                return (
                  <span style={{ color: '#64748b', fontSize: 11 }}>
                    scenario_id="{running.scenarioId}" 沒對應 IM/CCO/ES preset,不顯示門檻表
                  </span>
                );
              }
              const evalRes = preset.evaluator(pm, driver?.trigger_config);
              return (
                <>
                  <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6 }}>
                    本場 intent <strong style={{ color: '#cbd5e1' }}>{preset.label}</strong> 的觸發門檻 —
                    紅燈 = 滿足條件 → xApp 應該下對應控制
                  </div>
                  <table style={{ width: '100%', fontSize: 11, color: '#cbd5e1', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ color: '#94a3b8', borderBottom: '1px solid #334155' }}>
                        <th style={{ textAlign: 'left', padding: 4 }}>Intent</th>
                        <th style={{ textAlign: 'left', padding: 4 }}>條件</th>
                        <th style={{ textAlign: 'right', padding: 4 }}>當前值</th>
                        <th style={{ textAlign: 'center', padding: 4 }}>狀態</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evalRes.conditions.map((c, i) => (
                        <tr key={i} style={{
                          borderBottom: '1px solid #1f2937',
                          background: evalRes.triggered ? '#1e3a2f' : undefined,
                        }}>
                          <td style={{ padding: 4, color: evalRes.triggered ? '#a7f3d0' : '#cbd5e1', fontWeight: evalRes.triggered ? 600 : 400 }}>
                            {i === 0 ? `${preset.label}${evalRes.triggered ? ' ▶ TRIGGERED' : ''}` : ''}
                          </td>
                          <td style={{ padding: 4 }}>{c.label}</td>
                          <td style={{ padding: 4, textAlign: 'right', fontFamily: 'ui-monospace,monospace' }}>{c.value}</td>
                          <td style={{ padding: 4, textAlign: 'center', color: c.ok ? '#22c55e' : '#94a3b8' }}>
                            {c.ok ? '✓' : '✗'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              );
            })()}
          </Panel>

          {/* Handover + RIC ControlAction */}
          <Panel title={`Handover Events (${handovers.length})`} margin>
            {handovers.length === 0
              ? <span style={{ color: '#64748b', fontSize: 11 }}>A3 還沒觸發</span>
              : <table style={{ width: '100%', fontSize: 11, color: '#cbd5e1', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ color: '#94a3b8', borderBottom: '1px solid #334155' }}>
                      <th style={{ textAlign: 'left', padding: 2 }}>sim-time</th>
                      <th style={{ textAlign: 'left', padding: 2 }}>UE</th>
                      <th style={{ textAlign: 'left', padding: 2 }}>source → target</th>
                      <th style={{ textAlign: 'left', padding: 2 }}>trigger</th>
                      <th style={{ textAlign: 'left', padding: 2 }}>status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {handovers.slice(-15).map((h) => {
                      const wallMs = h.event_ts ? new Date(h.event_ts).getTime() : 0;
                      const elapsedSec = wallMs > 0 ? (wallMs - running.startedAtWallMs) / 1000 : 0;
                      const simHMS = addSecToHMS(running.scenarioStartHHMMSS, elapsedSec * running.ratio);
                      return (
                        <tr key={h.ho_uuid} style={{ borderBottom: '1px solid #1f2937' }}>
                          <td style={{ padding: 2, fontFamily: 'ui-monospace,monospace', color: '#fde68a' }}>{simHMS}</td>
                          <td style={{ padding: 2 }}>
                            <span style={{ background: '#1e40af', padding: '1px 5px', borderRadius: 2 }}>{h.ue_name}</span>
                          </td>
                          <td style={{ padding: 2 }}>
                            <span style={{ color: '#fca5a5' }}>{h.source_cell}</span>
                            {' → '}
                            <span style={{ color: '#a7f3d0' }}>{h.target_cell}</span>
                          </td>
                          <td style={{ padding: 2 }}>{h.trigger}</td>
                          <td style={{ padding: 2, color: h.status === 'SUCC' ? '#a7f3d0' : '#fcd34d' }}>{h.status}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
            }
          </Panel>

          <Panel title={`RIC Control Actions (${actions.length})`} margin>
            {actions.length === 0
              ? <span style={{ color: '#64748b', fontSize: 11 }}>xApp 還沒下指令</span>
              : <table style={{ width: '100%', fontSize: 11, color: '#cbd5e1', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ color: '#94a3b8', borderBottom: '1px solid #334155' }}>
                      <th style={{ textAlign: 'left', padding: 2 }}>time</th>
                      <th style={{ textAlign: 'left', padding: 2 }}>action</th>
                      <th style={{ textAlign: 'left', padding: 2 }}>UE / cell</th>
                      <th style={{ textAlign: 'left', padding: 2 }}>outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    {actions.slice(-15).map((a) => (
                      <tr key={a.id} style={{ borderBottom: '1px solid #1f2937' }}>
                        <td style={{ padding: 2 }}>{a.action_ts?.slice(11, 19) ?? '-'}</td>
                        <td style={{ padding: 2 }}>
                          <strong>{a.action_label}</strong> ({a.control_style}/{a.control_action_id})
                        </td>
                        <td style={{ padding: 2 }}>
                          {a.ue_name && <span style={{ background: '#1e40af', padding: '1px 4px', borderRadius: 2, marginRight: 3 }}>{a.ue_name}</span>}
                          {a.cell_id && <span style={{ background: '#7c2d12', padding: '1px 4px', borderRadius: 2 }}>{a.cell_id}</span>}
                        </td>
                        <td style={{ padding: 2, color: a.outcome === 'OK' ? '#a7f3d0' : '#fecaca' }}>{a.outcome}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            }
          </Panel>
        </section>
      )}
    </div>
  );
}

// ── small helpers ─────────────────────────────────────
function btn(bg: string): React.CSSProperties {
  return {
    padding: '6px 12px', background: bg, color: 'white', border: 'none',
    borderRadius: 4, cursor: 'pointer', fontSize: 12,
  };
}

// hex color → 半透明 / 亮一點 — 給同色家族用(serving vs neighbor 區分)
function lighten(hex: string): string {
  // 簡單做法:抽 hex 加 80 alpha
  return hex + '99';
}

function ClockBlock({ label, main, sub, color }: { label: string; main: string; sub: string; color: string }) {
  return (
    <div style={{ textAlign: 'right' }}>
      <div style={{ fontSize: 10, color: '#64748b' }}>{label}</div>
      <div style={{ fontSize: 16, color, fontFamily: 'ui-monospace,monospace', fontWeight: 600 }}>{main}</div>
      <div style={{ fontSize: 9, color: '#64748b', marginTop: 2 }}>{sub}</div>
    </div>
  );
}

function Panel({ title, children, margin }: { title: string; children: React.ReactNode; margin?: boolean }) {
  return (
    <div style={{
      padding: 10, background: '#111827', borderRadius: 6, border: '1px solid #1f2937',
      marginTop: margin ? 10 : 0,
    }}>
      <div style={{ fontSize: 12, color: '#cbd5e1', marginBottom: 6, fontWeight: 600 }}>{title}</div>
      {children}
    </div>
  );
}

function ScenarioCard({
  preset, scenario, rawJson, scenarioStart, busy, onRun, onPrecompute, onDelete,
}: {
  preset?: PresetMeta;
  scenario?: ScenarioRow;
  rawJson?: RawScenario;
  scenarioStart: string;
  busy: boolean;
  onRun: (s: ScenarioRow, ratio: number, forceLive?: boolean) => void;
  onPrecompute: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const id    = preset?.id    || scenario?.scenario_id || '';
  const label = preset?.label || displayName(id) || '?';
  const catalogDesc = SCENARIO_LABELS[id]?.desc;
  const desc  = preset?.desc  || catalogDesc || '';
  const ready = scenario?.precompute_status === 'ready';
  const reqGNB = preset?.requires?.min_gnbs;
  const status = scenario?.precompute_status ?? 'no_upload';

  // 預覽 chart 資料(raw_json 抓得到才有)。
  // ⚠️ 必須 useMemo + 取樣:每秒一格跑 86400 格、每格再掃 2880 個位置點,
  //    ×14 張卡 ×每 3 秒 re-render = 上億次運算,這是頁面卡頓的根因。
  const span = rawJson ? previewSpanSec(rawJson) : 0;
  const res = previewResolutionSec(span);
  const trafficSeries = useMemo(
    () => (rawJson ? buildTrafficSeries(rawJson, res, span) : []), [rawJson, res, span]);
  const axis = useMemo(() => (rawJson ? dominantAxis(rawJson) : 'z'), [rawJson]);
  const positionSeries = useMemo(
    () => (rawJson ? buildPositionZSeries(rawJson, res, span, axis) : []),
    [rawJson, res, span, axis]);

  // 抽 chart series keys
  const trafficLeftKeys = trafficSeries.length > 0
    ? Object.keys(trafficSeries[trafficSeries.length - 1]).filter(k => k !== 'tick')
    : [];
  const positionLeftKeys = positionSeries.length > 0
    ? Object.keys(positionSeries[positionSeries.length - 1]).filter(k => k !== 'tick')
    : [];

  const COLORS = ['#22c55e', '#ec4899', '#0ea5e9', '#f59e0b'];
  const trafficLeft = trafficLeftKeys.map((k, i) => ({
    key: k, label: k.replace('_dl', ''), color: COLORS[i % COLORS.length],
  }));
  const positionLeft = positionLeftKeys.map((k, i) => ({
    key: k, label: k.replace(/_[xz]$/, ''), color: COLORS[i % COLORS.length],
  }));

  // 統計:DL 最大、UE 數、軌跡 z 範圍。同樣 memo —— 這裡要掃全部位置點。
  // 用迴圈取 min/max,不用 Math.min(...zs):展開上萬個引數又慢又可能爆堆疊。
  const { dlMax, zMin, zMax } = useMemo(() => {
    const ai = axis === 'x' ? 1 : 3;   // normalize 後是 [t,x,y,z]
    let dlMax = 0, zMin = 0, zMax = 0, seen = false;
    if (rawJson) {
      for (const t of rawJson.traffic || []) {
        for (const p of t.profile || []) if (p[1] > dlMax) dlMax = p[1];
      }
      for (const u of rawJson.ues || []) {
        for (const p of normalizePositions(u.positions, rawJson.duration_sec)) {
          const z = p[ai];
          if (!seen) { zMin = zMax = z; seen = true; }
          else if (z < zMin) zMin = z;
          else if (z > zMax) zMax = z;
        }
      }
    }
    return { dlMax, zMin, zMax };
  }, [rawJson, axis]);

  return (
    <div style={{
      padding: 12, background: '#1e293b',
      border: status === 'ready' ? '1px solid #22c55e' : '1px solid #334155',
      borderRadius: 8,
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <strong style={{ color: '#e5e7eb', fontSize: 15 }}>{label}</strong>
        <span style={{
          fontSize: 10, padding: '2px 8px', borderRadius: 3,
          background: STATUS_COLOR[status] ?? '#475569',
          color: '#fff', fontWeight: 600, textTransform: 'uppercase',
        }}>
          {scenario?.precompute_status ?? 'no upload'}
          {scenario?.precompute_status === 'running' && ` ${scenario.precompute_progress.toFixed(0)}%`}
        </span>
      </div>

      {/* Description */}
      {desc && (
        <div style={{ fontSize: 11, color: '#cbd5e1', lineHeight: 1.4 }}>{desc}</div>
      )}

      {/* Quick stats */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 10, color: '#94a3b8' }}>
        {scenario && (
          <>
            <Stat label="Duration" value={`${scenario.duration_sec}s`} />
            <Stat label="UE" value={`${scenario.ue_count}`} />
            <Stat label="Tick" value={`${scenario.tick_ms}ms`} />
            {dlMax > 0 && <Stat label="Max DL" value={`${dlMax} kbps`} />}
            {(zMin !== zMax) && <Stat label={`UE ${axis}`} value={`${zMin}~${zMax}`} />}
            {(zMin === zMax && rawJson) && <Stat label={`UE ${axis}`} value={`${zMin}(固定)`} />}
          </>
        )}
      </div>

      {/* Topology requirement */}
      {reqGNB !== undefined && (
        <div style={{
          fontSize: 10, color: '#94a3b8',
          padding: '4px 8px', background: '#0f172a', borderRadius: 3,
        }}>
          🌐 Needs ≥{reqGNB} gNB{reqGNB > 1 ? '⚠️' : ''} · ≥{preset?.requires?.min_cells_per_gnb} cell/gNB · ≥{preset?.requires?.min_ues} UE
        </div>
      )}

      {/* Preview charts */}
      {rawJson ? (
        <>
          <div>
            <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 3 }}>
              📈 DL kbps(劇本內各時間流量)
            </div>
            <div style={{ background: '#0f172a', borderRadius: 4, padding: 4 }}>
              <SimTimeChart
                data={trafficSeries} scenarioStart={scenarioStart}
                leftSeries={trafficLeft} height={70} compact
              />
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 3 }}>
              📉 UE {axis} 座標(劇本內各時間 UE 位置)
            </div>
            <div style={{ background: '#0f172a', borderRadius: 4, padding: 4 }}>
              <SimTimeChart
                data={positionSeries} scenarioStart={scenarioStart}
                leftSeries={positionLeft} height={70} compact
              />
            </div>
          </div>
        </>
      ) : (
        <div style={{ fontSize: 11, color: '#64748b', padding: '8px 0' }}>
          載入劇本明細中...
        </div>
      )}

      {/* Run buttons + 狀態提示 */}
      {scenario && status === 'pending' && (
        <div style={{
          padding: 8, background: '#1e1b4b', border: '1px solid #4338ca',
          borderRadius: 4, fontSize: 11, color: '#c7d2fe',
        }}>
          🔧 需要先按 <strong>[Pre]</strong> 跑 Sionna precompute。
          {scenario.duration_sec >= 600
            ? <> 1hr scenario 約需 <strong>~40 分鐘</strong>(背景跑)。</>
            : <> 短劇本約 <strong>~30 秒</strong>。</>}
          完成後才會出現 ▶ 按鈕。
        </div>
      )}
      {scenario && status === 'running' && (
        <div style={{
          padding: 8, background: '#451a03', border: '1px solid #b45309',
          borderRadius: 4, fontSize: 11, color: '#fde68a',
        }}>
          ⏳ Precompute 跑中... {scenario.precompute_progress.toFixed(1)}%
        </div>
      )}
      {scenario && status === 'failed' && (
        <div style={{
          padding: 8, background: '#7f1d1d', border: '1px solid #991b1b',
          borderRadius: 4, fontSize: 11, color: '#fecaca',
        }}>
          ❌ Precompute 失敗: {scenario.precompute_error || 'unknown'}
        </div>
      )}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 'auto', paddingTop: 4 }}>
        {scenario && (
          <button onClick={() => onPrecompute(scenario.scenario_id)}
            disabled={busy || scenario.precompute_status === 'running'}
            style={btn(status === 'pending' ? '#a78bfa' : '#8b5cf6')}>
            {status === 'pending' ? '🔧 Pre(加速用)' : 'Pre'}
          </button>
        )}
        {/* 綠色 1x/2x/3x = cached 快跑,需要 precompute ready 才有快取可讀。
            藍色 Live = Sionna 即時 ray tracing,**不需要 precompute**
            (RU 本來就預設 live;precompute 只是為了能加速重播)。
            註:2x 為安全 baseline;3x 以上會掉封包/KPM 失真,只 demo 用不當量測比較對象。 */}
        {scenario && ready && [1, 2, 3].map((r) => (
          <button key={r} onClick={() => onRun(scenario, r)}
            disabled={busy} style={btn('#22c55e')}
            title="cached 模式:讀 precompute 好的通道快取,可加速。">▶ {r}x</button>
        ))}
        {scenario && [1, 2].map((r) => (
          <button key={`live${r}`} onClick={() => onRun(scenario, r, true)}
            disabled={busy} style={btn('#3b82f6')}
            title="Live:Sionna 即時 ray tracing,不需要 precompute。物理最真實,速度受 GPU 限制。">
            ▶ Live {r}x
          </button>
        ))}
        {scenario && !preset && (
          <button onClick={() => onDelete(scenario.scenario_id)}
            disabled={busy} style={btn('#475569')}>Del</button>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <span style={{ fontSize: 9, color: '#64748b' }}>{label}</span>
      <span style={{ fontSize: 11, color: '#cbd5e1', fontWeight: 500 }}>{value}</span>
    </div>
  );
}
