'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { stopSim, startUnifiedSim, stopUnifiedSim, fetchUEPositions } from '@/services/api/simLoop';
import { ueSimStop } from '@/services/api/ueProfile';
import { SIM_LOOP_TICK_MS, DU_BASE_URL, CU_BASE_URL, OMNIVERSE_API_URL } from '@/config';
import * as omniverseApi from '@/services/api/omniverse';
import type { UESignalData } from '@/types';

export interface ChartData {
  tick: number;
  [ueKey: string]: number | string;
}


interface UseSimPageOptions {
  onUpdateUEPositions?: (positions: Record<string, [number, number, number]>) => void;
  paused?: boolean;  // ← Coverage compute 期間 set true，暫停所有 polling + RU 推送
}

export function useSimPage(options?: UseSimPageOptions) {
  const router = useRouter();
  const positionPollRef = useRef<NodeJS.Timeout | null>(null);
  const slowPollRef = useRef<NodeJS.Timeout | null>(null);
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
        // 同步 sim_speed_x — interpolate UE 移動會用這個
        const sx = data.data?.sim_speed_x;
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


      // ── B. 單一統一呼叫 — 走 RANsim-UE SimController.start ─────────
      // Stage 5A: C.1~G 整段(scene-apply + UE attach + DU Tick.start + UE Lifecycle.start)
      // 都委派給 sim_orchestrator.start_sim(source="live_db"),它 reuse SceneApplyService /
      // UeAttachService,跟 /scenarios 走完全同一份 backend code path。Browser 不再直 call
      // RU/DU/CU 30+ 行 fetch。
      let simStartResult: any = null;
      try {
        simStartResult = await startUnifiedSim({ source: 'live_db' });
      } catch (e) {
        console.error('[Start Sim] SimController.start failed:', e);
        setError(`Start Sim failed: ${(e as Error).message || e}`);
        setLoading(false);
        return;
      }
      setSimRunning(true);

      // 回報 scene-apply / UE attach 過程的失敗(best-effort:sim 仍會跑起來)
      const applyErrors: Array<{ step: string; error: string }> = simStartResult?.apply?.errors ?? [];
      const attachFailed: Array<{ ue: string; step: string; error: string }> = simStartResult?.attach?.failed ?? [];
      if (applyErrors.length > 0 || attachFailed.length > 0) {
        const parts: string[] = [];
        if (applyErrors.length > 0) parts.push(`scene-apply: ${applyErrors.map(e => e.step).join(', ')}`);
        if (attachFailed.length > 0) parts.push(`UE attach: ${attachFailed.length} failed`);
        console.warn(`[Start Sim] partial failures —`, parts.join(' / '), simStartResult);
        setError(`${parts.join('; ')}. Sim is running but may have stale state. Re-click Start Sim to retry.`);
      }
      // 只 sync 這次 startSim 註冊的 UE
      const activeUeNames = new Set(uePayload.map(u => u.name));

      let inFlight = false;
      const unifiedLoop = async () => {
        if (options?.paused) return;     // ← Coverage 期間暫停
        if (inFlight) return;
        inFlight = true;
        try {
          // 1. 從 Kit /ues 拉位置(UE container manager._trajectory_tick 推進去的)
          //    Stage 5B: browser 不再 client-side 算位置,也不直推 RU。
          //    UeLifecycleManager 已負責把位置 batch 推給 RU + Kit。
          const positions = await fetchUEPositions();
          if (options?.onUpdateUEPositions) options.onUpdateUEPositions(positions);

          // 2. 讀 CU E2-KPM 拿最新 RSRP/SINR/throughput/MCS/PRB/rank
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
          // 從 gnbsFromDb 展開 cell_id → {gnb_id, pci} 查表（讓 Omniverse 3D viz 可用）
          const cellInfoMap: Record<string, { gnb_id: string; pci: number; cell_id: string }> = {};
          for (const g of gnbsFromDb as any[]) {
            const sectors = (g.cells && g.cells.length > 0)
              ? g.cells
              : [{ pci: g.pci ?? 1 }];
            sectors.forEach((s: any, i: number) => {
              const cid = s.cell_id || `${g.name}_c${i}`;
              cellInfoMap[cid] = { gnb_id: g.name, pci: s.pci ?? 1, cell_id: cid };
            });
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
      // 停 Kit 動畫（保險起見，雖然 Dashboard-driven 模式下沒呼 startAnimation）
      try {
        await omniverseApi.stopAnimation();
      } catch { /* ignore */ }
      // Stage 5A: 用統一 stop endpoint(內部停 DU tick + UE Lifecycle + scenario_driver)
      try { await stopUnifiedSim(); } catch (e) {
        console.warn('[Stop Sim] stopUnifiedSim failed, falling back:', e);
        try { await stopSim(); } catch { /* best effort */ }
        try { await ueSimStop(); } catch { /* best effort */ }
      }
      setSimRunning(false);
      router.push('/playback');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop simulation');
    } finally {
      setLoading(false);
    }
  }, [router]);

  // Stage 5B: simRunning 變 true 但 unifiedLoop 還沒接管(例如 refresh 重整後)時,
  // 啟動一個 fallback polling 從 Kit /ues 拉位置餵 onUpdateUEPositions,
  // 確保 2D TopDownMap 看得到動的 UE。
  useEffect(() => {
    if (!simRunning) return;
    if (!options?.onUpdateUEPositions) return;
    if (positionPollRef.current) return;

    const pollPositions = async () => {
      const positions = await fetchUEPositions();
      options.onUpdateUEPositions!(positions);
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
