'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { startSim, stopSim, setupUE } from '@/services/api/simLoop';
import { ueSimStart, ueSimStop } from '@/services/api/ueProfile';
import { SIM_LOOP_TICK_MS, DU_BASE_URL, CU_BASE_URL, OMNIVERSE_API_URL } from '@/config';
import * as omniverseApi from '@/services/api/omniverse';
import type { UESignalData } from '@/types';

export interface ChartData {
  tick: number;
  [ueKey: string]: number | string;
}

/**
 * 沿 waypoints 內插 UE 位置。Dashboard-driven 位置權威核心：
 * 不再依賴 Omniverse Kit 的 USD time-sample 動畫，前端按 elapsed time × speed 算位置。
 * 之後把這位置同時推給 RU（給 Physics 算 channel）跟 Omniverse ingest（move_ue 顯示）。
 */
function interpolateAlongWaypoints(
  waypoints: [number, number, number][],
  speedMps: number,
  elapsedSec: number,
  loop: boolean,
): [number, number, number] {
  if (waypoints.length === 0) return [0, 0, 0];
  if (waypoints.length === 1) return waypoints[0];

  // 算每段 segment 長度
  const segs: { start: number; len: number }[] = [];
  let total = 0;
  for (let i = 0; i < waypoints.length - 1; i++) {
    const dx = waypoints[i + 1][0] - waypoints[i][0];
    const dy = waypoints[i + 1][1] - waypoints[i][1];
    const dz = waypoints[i + 1][2] - waypoints[i][2];
    const len = Math.sqrt(dx * dx + dy * dy + dz * dz);
    segs.push({ start: total, len });
    total += len;
  }
  if (total === 0) return waypoints[0];

  // 已走距離
  let target = elapsedSec * speedMps;
  if (loop) target = target % total;
  else target = Math.min(target, total);

  // 找該距離落在哪段
  for (let i = 0; i < segs.length; i++) {
    const s = segs[i];
    if (target >= s.start && target <= s.start + s.len) {
      const t = s.len > 0 ? (target - s.start) / s.len : 0;
      const a = waypoints[i];
      const b = waypoints[i + 1];
      return [
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
      ];
    }
  }
  return waypoints[waypoints.length - 1];
}

interface UseSimPageOptions {
  onUpdateUEPositions?: (positions: Record<string, [number, number, number]>) => void;
  paused?: boolean;  // ← Coverage compute 期間 set true，暫停所有 polling + RU 推送
}

export function useSimPage(options?: UseSimPageOptions) {
  const router = useRouter();
  const positionPollRef = useRef<NodeJS.Timeout | null>(null);
  const slowPollRef = useRef<NodeJS.Timeout | null>(null);
  // Dashboard-driven 位置權威：在 handleStartSim 抓到 trajectories 後存進 ref，
  // 每輪 polling 從 ref 讀軌跡 + 用 elapsed 內插出當前位置（不再 polling Kit /ues）
  const trajectoriesRef = useRef<Array<{
    name: string;
    waypoints: [number, number, number][];
    speed_mps: number;
    loop: boolean;
  }>>([]);
  const simStartTimeRef = useRef<number>(0);
  const [simRunning, setSimRunning] = useState(false);
  const [signalData, setSignalData] = useState<UESignalData[]>([]);
  const [chartData, setChartData] = useState<ChartData[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Sim 狀態定期跟後端對齊 — backend (DU TickRunner) 才是 source of truth。
  // 原本只在 mount 一次性 check，導致多 tab 之間狀態完全各自為政：A tab 按 Stop
  // 後，B tab 的 simRunning 仍是舊值（看到「Stop Sim」按鈕但按下去其實只會送
  // 重複 stop），pause 操作也同樣 stale。改成每 2s polling reconcile，任何 tab
  // 在 ≤2s 內會自動跟齊 backend 真實狀態。觀測台應該由後端推狀態，前端不該
  // 持有 source of truth。
  useEffect(() => {
    let cancelled = false;
    const reconcileSimStatus = async () => {
      try {
        const response = await fetch(`${DU_BASE_URL}/api/v0.1/DU/Tick/TickController/read`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: '{}',
        });
        if (!response.ok || cancelled) return;
        const data = await response.json();
        const backendRunning = !!data.data?.is_running;
        // 只在 backend 跟本地 state 不一致時才 setState，避免每 2s 觸發無謂 re-render
        setSimRunning(prev => prev === backendRunning ? prev : backendRunning);
      } catch {
        // 後端暫不可達時靜默忽略，下次 tick 再試
      }
    };
    reconcileSimStatus();  // mount 立即對齊一次，不用等 2s
    const id = setInterval(reconcileSimStatus, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const handleStartSim = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // 重置歷史 — 上次 sim 的 UE 可能已經在 Scene Editor 被刪掉，
      // 留著舊資料會在 chart 留下「鬼魂 UE」線條。
      setSignalData([]);
      setChartData([]);

      // 從 DB 讀取 UE / gNB 配置
      const [uesFromDb, gnbsFromDb] = await Promise.all([
        omniverseApi.listUes(),
        omniverseApi.listGnbs(),
      ]);

      const uePayload = uesFromDb
        .filter(ue => ue.waypoints && ue.waypoints.length >= 2)
        .map((ue) => ({
          name: ue.name,
          waypoints: ue.waypoints || [],
          speed_mps: ue.speed_mps || 1.0,
          loop: true,
          position: ue.position || [ue.x ?? 0, ue.y ?? 0, ue.z ?? 0],
        }));

      // ── A. Dashboard-driven 位置：把 trajectories 存到 ref，由 polling loop 自己內插 ──
      // (不再呼 Kit setUeTrajectory / startAnimation。Kit 變被動接收 ingest 內的 move_ue。)
      // 同時先 stop 既有 Kit USD animation，避免它跟 Dashboard ingest 競爭改 prim translate
      try {
        await omniverseApi.stopAnimation();
      } catch { /* ignore */ }

      trajectoriesRef.current = uePayload.map(u => ({
        name: u.name,
        waypoints: u.waypoints as [number, number, number][],
        speed_mps: u.speed_mps,
        loop: u.loop,
      }));
      simStartTimeRef.current = Date.now();

      // ── B. 構 cell payload — 把 gNB.cells[] 完整展開（每個 sector 一個 cell）─
      // 之前的 bug：只取每個 gNB 的第一個 cell，多餘 sector 被吃掉。
      // 命名規則：cell_id = `${gnbName}_c${index}`，標 gnb_id = gnb name。
      type CellRow = {
        cell_id: string;       // unique
        gnb_id: string;        // 標屬於哪個 gNB
        name: string;          // RU 用的 unique name（=cell_id）
        pci: number;
        azimuth_deg: number;
        position: [number, number, number];
        frequency_ghz: number;
        bandwidth_mhz: number;
        power_dbm: number;     // AK8: 同 gNB 所有 sector 共用 gNB.power_dbm
      };
      const cellPayload: CellRow[] = [];
      for (const g of gnbsFromDb as any[]) {
        const pos: [number, number, number] = g.position || [g.x ?? 0, g.y ?? 0, g.z ?? 0];
        const sectors = (g.cells && g.cells.length > 0)
          ? g.cells
          : [{ pci: g.pci ?? 1, azimuth_deg: g.azimuth_deg ?? 0 }]; // 沒設 cells[] 則退回 1 sector
        const gnbPower = g.power_dbm ?? 43.0;  // AK8: gNB 級的 TX 功率，往下傳給每個 cell
        sectors.forEach((s: any, i: number) => {
          cellPayload.push({
            cell_id: `${g.name}_c${i}`,
            gnb_id: g.name,
            name: `${g.name}_c${i}`,
            pci: s.pci ?? 1,
            azimuth_deg: s.azimuth_deg ?? 0,
            position: pos,
            frequency_ghz: g.frequency_ghz ?? 3.5,
            bandwidth_mhz: g.bandwidth_mhz ?? 100.0,
            power_dbm: gnbPower,
          });
        });
      }

      // ── C. Best-effort scene-apply chain ─────────────────────
      // 每步 try/catch，失敗不中斷後續。errors[] 收集起來最後 console.warn 列出。
      const ruBase = process.env.NEXT_PUBLIC_RU_URL || 'http://localhost:8103';
      const duBase = process.env.NEXT_PUBLIC_DU_URL || 'http://localhost:8102';
      const cuBase = process.env.NEXT_PUBLIC_CU_URL || 'http://localhost:8101';
      const sceneApplyErrors: Array<{ step: string; err: any }> = [];

      const tryStep = async (step: string, fn: () => Promise<any>) => {
        try { await fn(); }
        catch (e) { sceneApplyErrors.push({ step, err: e }); console.warn(`[scene-apply] ${step}:`, e); }
      };

      // C.1 RU update_cells（已自帶 exclude-delete 邏輯，加 gnb_id）
      if (cellPayload.length > 0) {
        await tryStep('RU update_cells', () =>
          fetch(`${ruBase}/api/v0.1/RU/Config/RuController/update_cells`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              cells: cellPayload.map(c => ({
                name: c.name, pci: c.pci, azimuth_deg: c.azimuth_deg,
                position: c.position, frequency_ghz: c.frequency_ghz,
                bandwidth_mhz: c.bandwidth_mhz, gnb_id: c.gnb_id,
                power_dbm: c.power_dbm,  // AK8: 讓 RU 在 RSRP 計算用每 gNB 自己的功率
              })),
            }),
          }).then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
        );
      }

      // C.2 RU update_ues（新加 exclude-delete）
      if (uePayload.length > 0) {
        await tryStep('RU update_ues', () =>
          fetch(`${ruBase}/api/v0.1/RU/Config/RuController/update_ues`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ues: uePayload.map(u => ({ id: u.name, position: u.position })) }),
          }).then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
        );
      }

      // C.3 DU MAC replace_cells（全量替換）
      if (cellPayload.length > 0) {
        await tryStep('DU MAC replace_cells', () =>
          fetch(`${duBase}/api/v0.1/DU/MAC/MacCellController/replace_cells`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              cells: cellPayload.map(c => ({
                cell_id: c.cell_id, pci: c.pci,
                freq_ghz: c.frequency_ghz, bw_mhz: c.bandwidth_mhz,
                gnb_id: c.gnb_id,
              })),
            }),
          }).then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
        );
      }

      // C.4 DU Tick replace_ues（unregister 舊 UE）
      if (uePayload.length > 0) {
        await tryStep('DU Tick replace_ues', () =>
          fetch(`${duBase}/api/v0.1/DU/Tick/TickController/replace_ues`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              ues: uePayload.map(u => ({ ue_id: u.name })),
            }),
          }).then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
        );
      }

      // C.5 CU release_stale（把舊 UE 標 IDLE，row 保留）
      if (uePayload.length > 0) {
        await tryStep('CU release_stale', () =>
          fetch(`${cuBase}/api/v0.1/CU/Session/SessionController/release_stale`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keep_ue_ids: uePayload.map(u => u.name), force: false }),
          }).then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
        );
      }

      // ── D. CU RRC attach（每個 UE 進 CONNECTED；已 CONNECTED 就 skip） ────
      const b64 = (msgType: string, payload: any = {}) =>
        btoa(JSON.stringify({ type: msgType, payload }));
      // 先抓 session list 看誰已經 CONNECTED
      const connectedUes = new Set<string>();
      try {
        const sessRes = await fetch(`${cuBase}/api/v0.1/CU/Session/SessionController/list`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        });
        if (sessRes.ok) {
          const sl = await sessRes.json();
          for (const s of (sl.data || [])) {
            if (s.rrc_state === 'CONNECTED') connectedUes.add(s.ue_id);
          }
        }
      } catch { /* fall through, attempt attach blindly */ }

      for (const ue of uePayload) {
        if (connectedUes.has(ue.name)) continue;  // idempotent
        try {
          await fetch(`${cuBase}/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ue_id: ue.name, rrc_msg_b64: b64('RRCSetupRequest') }),
          });
          await fetch(`${cuBase}/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ue_id: ue.name, rrc_msg_b64: b64('RRCSetupComplete', { transaction_id: 1 }) }),
          });
        } catch (err) {
          console.warn(`RRC attach failed for ${ue.name}:`, err);
        }
      }

      // ── E. DU 端：CU.update_traffic_profile 自動走 F1AP UE Context Setup ───
      // AI1: 砍掉直 call DU RlcEntityController/create + inject_sdu 的 sim hack.
      // AG2 已治本 — CU update_traffic_profile 觸發 F1AP UeCtxSetup → DU 自動建
      // MAC + RLC entity per DRB + RA + HARQ + tick UE registry. 對齊 OAI
      // 真實流程 (3GPP TS 38.473 §8.3.1).
      if (uePayload.length > 0) {
        await setupUE(uePayload);
      }

      await tryStep('DU Tick.start', async () => { await startSim(); });
      // AG15: 把 UE container 從 STANDBY → RUNNING. 沒這步 traffic_gen 不發 SDU,
      // RLC/MAC/cell PRB 全 0. Start Sim chain 原本漏掉這一步.
      await tryStep('UE Lifecycle.start', async () => { await ueSimStart(); });
      setSimRunning(true);

      // ── 報告 scene-apply 過程的失敗（best-effort：sim 仍會跑起來）──
      if (sceneApplyErrors.length > 0) {
        const summary = sceneApplyErrors.map(e => e.step).join(', ');
        console.warn(`[Start Sim] ${sceneApplyErrors.length} step(s) failed during scene apply: ${summary}. Sim will still run with partial state — re-click Start Sim to retry.`);
        setError(`Scene apply: ${sceneApplyErrors.length} step(s) failed (${summary}). Sim is running but may have stale state. Re-click Start Sim to retry.`);
      }

      // 只 sync 這次 startSim 註冊的 UE
      const activeUeNames = new Set(uePayload.map(u => u.name));

      // ── 統一 loop：每 1 秒做一輪「位置 + 信號」全鏈推送 ─────────────────
      // 同一份 (position, signal) payload 同時餵：
      //   • RU update_ues       (給 Physics 算 channel)
      //   • frontend TopDownMap (2D 顯示)
      //   • Omniverse ingest    (3D 視窗 prim 位置 + RSRP/SINR label)
      // 沒有「位置 1s 推一次給 RU、信號 8s 才到 Omniverse」的時序錯位。
      const computeCurrentPositions = (): Record<string, [number, number, number]> => {
        const elapsed = (Date.now() - simStartTimeRef.current) / 1000;
        const out: Record<string, [number, number, number]> = {};
        for (const tj of trajectoriesRef.current) {
          out[tj.name] = interpolateAlongWaypoints(tj.waypoints, tj.speed_mps, elapsed, tj.loop);
        }
        return out;
      };

      let inFlight = false;
      const unifiedLoop = async () => {
        if (options?.paused) return;     // ← Coverage 期間暫停
        if (inFlight) return;
        inFlight = true;
        try {
          // 1. 算當前位置
          const positions = computeCurrentPositions();
          if (options?.onUpdateUEPositions) options.onUpdateUEPositions(positions);

          // 2. 推給 RU（fire-and-forget；給 DU 下個 tick 用）
          const ueUpdates = Object.entries(positions)
            .filter(([name]) => activeUeNames.has(name))
            .map(([name, pos]) => ({ id: name, position: pos }));
          if (ueUpdates.length > 0) {
            fetch(`${ruBase}/api/v0.1/RU/Config/RuController/update_ues`, {
              method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ ues: ueUpdates }),
            }).catch(() => {});
          }

          // 3. 讀 CU E2-KPM 拿最新 RSRP/SINR/throughput/MCS/PRB/rank
          let ueStatus: Array<{
            ue_id: string;
            serving_cell: string;
            rsrp_dbm: number | null;
            sinr_db: number | null;
            throughput_dl_mbps: number;
            throughput_ul_mbps?: number;
            mcs_dl?: number;
            rb_width_dl?: number;
            mimo_rank?: number;
            neighbor_cells?: Array<{ cell_id: string; rsrp_dbm: number }>;
          }> = [];
          try {
            const kpmRes = await fetch(`${CU_BASE_URL}/api/v0.1/CU/E2/E2KpmReporter/read`, {
              method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
            });
            if (kpmRes.ok) {
              const kpm = await kpmRes.json();
              ueStatus = kpm.data?.ue_status || [];
            }
          } catch { /* CU 拿不到 KPI 不影響推位置 */ }

          // 4. 組單一 payload (signal + position bundled per UE) → ingest
          // 從 cellPayload 建 cell_id → {gnb_id, pci} 查表（讓 Omniverse 3D viz 可用）
          const cellInfoMap: Record<string, { gnb_id: string; pci: number; cell_id: string }> = {};
          for (const c of cellPayload) {
            cellInfoMap[c.cell_id] = { gnb_id: c.gnb_id, pci: c.pci, cell_id: c.cell_id };
          }

          const signals = ueStatus
            .filter(u => activeUeNames.has(u.ue_id) && u.rsrp_dbm !== null && u.sinr_db !== null)
            .map(u => {
              const cellInfo = u.serving_cell ? cellInfoMap[u.serving_cell] : null;
              // 把 CU KPM 的 neighbor_cells [{cell_id, rsrp_dbm, rsrq_db}] 攤平成
              // rsrp_map {cell_id: rsrp_dbm},Playback / SignalTable 展開列要用。
              const neighbors: Array<{ cell_id: string; rsrp_dbm: number }> =
                ((u as any).neighbor_cells ?? []) as Array<{ cell_id: string; rsrp_dbm: number }>;
              const rsrpMap: Record<string, number> = {};
              for (const n of neighbors) {
                if (n && n.cell_id != null && typeof n.rsrp_dbm === 'number') {
                  rsrpMap[n.cell_id] = n.rsrp_dbm;
                }
              }
              if (u.serving_cell && typeof u.rsrp_dbm === 'number' && !(u.serving_cell in rsrpMap)) {
                rsrpMap[u.serving_cell] = u.rsrp_dbm;
              }
              return {
                ue_name: u.ue_id,
                serving_cell: u.serving_cell || 'unknown',
                serving_gnb: cellInfo?.gnb_id || '',         // 給 Kit 3D 著色用
                serving_pci: cellInfo?.pci ?? null,
                serving_cell_id: cellInfo?.cell_id || '',
                rsrp_dbm: u.rsrp_dbm,
                sinr_db: u.sinr_db,
                rsrp_map: rsrpMap,
                // 2026-05-17 #2: 把 KPM 的 wireless KPI 一併帶進 ingest,
                // SignalHistory 落地後 playback 才能重現吞吐/MCS/PRB/rank
                throughput_dl_mbps: u.throughput_dl_mbps ?? null,
                throughput_ul_mbps: u.throughput_ul_mbps ?? null,
                mcs_dl: u.mcs_dl ?? null,
                prb_used_dl: u.rb_width_dl ?? null,
                mimo_rank: u.mimo_rank ?? null,
                position: positions[u.ue_id],   // ★ 跟 RU 同一份位置
              };
            })
            .filter(s => s.position);
          if (signals.length > 0) {
            fetch(`${OMNIVERSE_API_URL}/api/v0.1/RAN/Ingest/SignalIngestor/create`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ signals }),
            }).catch(() => { /* fire-and-forget */ });
            setSignalData(signals.map(s => ({
              ue_name: s.ue_name,
              serving_cell: s.serving_cell,
              serving_gnb: s.serving_gnb,
              serving_pci: s.serving_pci ?? undefined,
              serving_cell_id: s.serving_cell_id,
              rsrp_dbm: s.rsrp_dbm,
              sinr_db: s.sinr_db,
              rsrp_map: s.rsrp_map,
              throughput_dl_mbps: s.throughput_dl_mbps ?? undefined,
              throughput_ul_mbps: s.throughput_ul_mbps ?? undefined,
              mcs_dl: s.mcs_dl ?? undefined,
              prb_used_dl: s.prb_used_dl ?? undefined,
              mimo_rank: s.mimo_rank ?? undefined,
            } as UESignalData)));
            setChartData(prev => {
              const tick = (prev[prev.length - 1]?.tick as number || 0) + 1;
              const point: ChartData = { tick };
              signals.forEach(s => {
                point[`${s.ue_name}_rsrp`] = s.rsrp_dbm ?? 0;
                point[`${s.ue_name}_sinr`] = s.sinr_db ?? 0;
              });
              return [...prev, point].slice(-100);
            });
          }
        } finally {
          inFlight = false;
        }
      };

      // 清舊 polling，啟動單一 loop
      if (positionPollRef.current) {
        clearInterval(positionPollRef.current);
        positionPollRef.current = null;
      }
      if (slowPollRef.current) {
        clearInterval(slowPollRef.current);
        slowPollRef.current = null;
      }
      positionPollRef.current = setInterval(unifiedLoop, 1000);

      // 不再用 WebSocket: ws/sim/live consumer 已從 Physics 搬走 (asgi.py 註解),
      // unifiedLoop 每秒 polling 已涵蓋所有 setSignalData / setChartData 邏輯.
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start simulation');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleStopSim = useCallback(async () => {
    try {
      setLoading(true);
      // 停止輪詢位置
      if (positionPollRef.current) {
        clearInterval(positionPollRef.current);
        positionPollRef.current = null;
      }
      if (slowPollRef.current) {
        clearInterval(slowPollRef.current);
        slowPollRef.current = null;
      }
      // 清掉 trajectory state（避免下次 Start Sim 用到舊軌跡）
      trajectoriesRef.current = [];
      simStartTimeRef.current = 0;
      // 停 Kit 動畫（保險起見，雖然 Dashboard-driven 模式下沒呼 startAnimation）
      try {
        await omniverseApi.stopAnimation();
      } catch { /* ignore */ }
      await stopSim();
      // AG15: 對稱關掉 UE container traffic_gen.
      try { await ueSimStop(); } catch { /* best effort */ }
      setSimRunning(false);
      router.push('/playback');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop simulation');
    } finally {
      setLoading(false);
    }
  }, [router]);

  // 當 simRunning 變 true 但 trajectoriesRef 是空（refresh 後從後端讀到 is_running=true）時，
  // 沒辦法 reproduce 軌跡 → 維持靜止，user 按 Stop/Start 重置即可。
  // 不再走「polling Kit /ues」這條路（Dashboard 才是位置權威）。
  useEffect(() => {
    if (!simRunning) return;
    if (!options?.onUpdateUEPositions) return;
    if (positionPollRef.current) return;
    if (trajectoriesRef.current.length === 0) return;  // 沒軌跡就不啟 fallback loop

    const pollPositions = () => {
      const elapsed = (Date.now() - simStartTimeRef.current) / 1000;
      const out: Record<string, [number, number, number]> = {};
      for (const tj of trajectoriesRef.current) {
        out[tj.name] = interpolateAlongWaypoints(tj.waypoints, tj.speed_mps, elapsed, tj.loop);
      }
      options.onUpdateUEPositions!(out);
    };
    pollPositions();
    positionPollRef.current = setInterval(pollPositions, SIM_LOOP_TICK_MS);

    return () => {
      if (positionPollRef.current) {
        clearInterval(positionPollRef.current);
        positionPollRef.current = null;
      }
    };
  }, [simRunning, options?.onUpdateUEPositions]);

  useEffect(() => {
    return () => {
      // 清理前端 polling 定時器. 不呼 handleStopSim() 讓 backend tick 持續,
      // 跨頁面切換不會中斷 sim.
      if (positionPollRef.current) {
        clearInterval(positionPollRef.current);
      }
    };
  }, []);

  return {
    simRunning,
    signalData,
    chartData,
    error,
    loading,
    handleStartSim,
    handleStopSim,
  };
}
