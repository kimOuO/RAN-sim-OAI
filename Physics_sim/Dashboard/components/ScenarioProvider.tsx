'use client';

/**
 * ScenarioProvider — scenario driver polling + history 移到 layout 層級。
 *
 * 跟 SimProvider 一樣的設計理念:把長壽 state 放 layout,切 page 不會 unmount。
 * 跑劇本時切 /scenarios → /logs → /editor,polling/history 都不會中斷。
 *
 * 任何 page 用 useScenarioContext() 拿 driver/pm/actions/handovers/history。
 */
import { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react';
import {
  fetchDriverStatus, fetchDuPm, fetchControlActions, fetchHandovers,
  fetchActiveSessionUuid,
  type DuPmSnapshot, type ScenarioDriverStatus, type ControlActionRow,
  type HandoverEventRow,
} from '@/services/api/scenarioMonitor';

export interface HistoryRow {
  tick: number;
  // per-cell: prb_<cell>
  // per-ue:  rsrp_<ue>, sinr_<ue>, thp_<ue>
  [key: string]: number;
}

interface ScenarioContextValue {
  driver: ScenarioDriverStatus | null;
  pm: DuPmSnapshot | null;
  actions: ControlActionRow[];
  handovers: HandoverEventRow[];
  history: HistoryRow[];
  sessionUuid: string;
  /** scenario 真正起跑時刻(用 driver.elapsed_wall_sec 推算)*/
  sessionStartedAtMs: number | null;
}

const ScenarioContext = createContext<ScenarioContextValue | null>(null);


export function ScenarioProvider({ children }: { children: ReactNode }) {
  const [driver, setDriver] = useState<ScenarioDriverStatus | null>(null);
  const [pm, setPm] = useState<DuPmSnapshot | null>(null);
  const [actions, setActions] = useState<ControlActionRow[]>([]);
  const [handovers, setHandovers] = useState<HandoverEventRow[]>([]);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [sessionUuid, setSessionUuid] = useState<string>('');
  const [sessionStartedAtMs, setSessionStartedAtMs] = useState<number | null>(null);

  const prevRunningRef = useRef<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const d = await fetchDriverStatus().catch(() => null);
      if (cancelled) return;
      setDriver(d);

      // driver state transition
      const running = !!d?.running;
      if (running && !prevRunningRef.current) {
        // session 開始:從 elapsed_wall_sec 推算真正起跑時刻
        const elapsedMs = (d?.elapsed_wall_sec ?? 0) * 1000;
        setSessionStartedAtMs(Date.now() - elapsedMs);
        // 用後端真實 running SimSession 的 uuid(HO/control 都綁這個);對不到才退回佔位
        const realUuid = await fetchActiveSessionUuid(d?.scenario_id);
        if (cancelled) return;
        setSessionUuid(realUuid || `runs_${d?.scenario_id ?? 'unknown'}_${Date.now()}`);
        // 重置 history,避免上一輪混進來
        setHistory([]);
        setActions([]);
        setHandovers([]);
      } else if (!running && prevRunningRef.current) {
        // session 結束:保留資料(playback 用),但停推新 row
      }
      prevRunningRef.current = running;

      if (!running) {
        return;  // 沒在跑就不抓 PM/actions/handovers
      }

      const [p, a, ho] = await Promise.all([
        fetchDuPm().catch(() => null),
        fetchControlActions(sessionUuid),
        fetchHandovers(sessionUuid),
      ]);
      if (cancelled) return;
      if (p) setPm(p);
      setActions(a);
      setHandovers(ho);

      if (d && p) {
        const cellStats = p.last_cell_stats ?? {};
        const ueStats = p.last_ue_stats ?? {};
        const row: HistoryRow = { tick: Math.round(d.elapsed_sim_sec) };
        for (const [cid, cs] of Object.entries(cellStats)) {
          row[`prb_${cid}`] = cs.prb_pct_this_tick;
        }
        for (const [uid, us] of Object.entries(ueStats)) {
          row[`rsrp_${uid}`] = us.rsrp_dbm;
          row[`sinr_${uid}`] = us.sinr_db;
          row[`thp_${uid}`] = us.throughput_dl_mbps_this_tick;
        }
        setHistory(prev => {
          const out = [...prev, row];
          return out.length > 600 ? out.slice(-600) : out;  // ~10 分鐘 sim @ 1 Hz poll
        });
      }
    };
    poll();
    const t = setInterval(poll, 1000);
    return () => { cancelled = true; clearInterval(t); };
  }, [sessionUuid]);

  return (
    <ScenarioContext.Provider value={{
      driver, pm, actions, handovers, history, sessionUuid, sessionStartedAtMs,
    }}>
      {children}
    </ScenarioContext.Provider>
  );
}


export function useScenarioContext(): ScenarioContextValue {
  const ctx = useContext(ScenarioContext);
  if (!ctx) throw new Error('useScenarioContext must be used inside <ScenarioProvider>');
  return ctx;
}
