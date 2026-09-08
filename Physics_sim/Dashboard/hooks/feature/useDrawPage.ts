'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { setupUE } from '@/services/api/simLoop';
import { initScene } from '@/services/api/scene';
import * as omniverseApi from '@/services/api/omniverse';
import { fetchLiveUePositions } from '@/services/api/ueLive';
import {
  setTrajectory as ueSetTrajectory,
  updateTrafficProfile as ueUpdateTrafficProfile,
  buildWaypointsFromDraw,
  type TrafficProfile,
} from '@/services/api/ueProfile';
import type { SceneLayout, UE, SceneAntennaConfig } from '@/types';

function toXZ(v: any): [number, number, number] {
  if (Array.isArray(v)) return [v[0] ?? 0, v[1] ?? 0, v[2] ?? 0];
  return [v?.x ?? 0, v?.y ?? 0, v?.z ?? 0];
}

// 場景身分簽章 — 只看「有哪些 gNB/UE/建築」(排序後名字),不看座標。
// 換劇本 → 名字集合變 → 簽章變;同場景內拖 waypoint / 位置更新 → 簽章不變。
function sceneSig(layout: SceneLayout | null): string {
  if (!layout) return '';
  const names = (arr?: any[]) => (arr || []).map(x => x?.name).filter(Boolean).sort();
  return JSON.stringify({
    g: names(layout.gnbs), u: names(layout.ues), b: names(layout.buildings),
  });
}

export function useDrawPage(opts?: { simRunning?: boolean }) {
  const router = useRouter();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [sceneConfig, setSceneConfig] = useState<SceneLayout | null>(null);
  const [selectedUEIndex, setSelectedUEIndex] = useState(0);
  const [trajectories, setTrajectories] = useState<UE[]>([]);
  // simRunning 透過 ref 給 polling closure 用,避免每次 simRunning 變 dep 都重起 interval
  // 目前有執行期座標的 UE —— 畫布可據此標 LIVE,一眼分得出「執行期真值」與「設定值」。
  // 兩者混在一起看不出來,正是這類 bug 難查的原因。
  const [liveUeIds, setLiveUeIds] = useState<Set<string>>(new Set());
  const simRunningRef = useRef<boolean>(false);
  simRunningRef.current = !!opts?.simRunning;

  // 場景「身分」簽章 = 排序後的 gNB/UE/建築名字集合。用來偵測 DB 場景是否真的換了
  // (例如從 /scenarios 套了別的劇本),而不是被同場景的位置更新誤判。
  const sceneSigRef = useRef<string>('');
  // 每個 UE 的 traffic profile (per-UE state, key = ue.name)
  const [trafficProfiles, setTrafficProfiles] = useState<Record<string, TrafficProfile>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const setTrafficProfile = useCallback((ueName: string, profile: TrafficProfile) => {
    setTrafficProfiles(prev => ({ ...prev, [ueName]: profile }));
  }, []);

  const refreshScene = useCallback(async () => {
    try {
      setLoading(true);
      console.log('[useDrawPage] Starting refreshScene...');
      const layout = await omniverseApi.getSceneLayout();
      console.log('[useDrawPage] Got layout:', layout);
      setSceneConfig(layout);
      sceneSigRef.current = sceneSig(layout);

      // 正規化 UE：加入預設 color、waypoints
      const normalizedUes: UE[] = (layout.ues || []).map((ue: any) => ({
        name: ue.name,
        color: [0.2, 0.6, 1.0] as [number, number, number],
        speed_mps: ue.speed_mps ?? 1.0,
        waypoints: ue.waypoints || [],
        position: toXZ(ue.position),
      }));
      console.log('[useDrawPage] Normalized UEs:', normalizedUes);
      setTrajectories(normalizedUes);
      setError(null);

      // 打印詳細的場景信息
      console.log('========== 目前場景信息 ==========');
      console.log('📍 Ground:', layout.ground);

      console.log('\n🏢 Buildings:');
      (layout.buildings || []).forEach((b, i) => {
        console.log(`  [${i}] ${b.name} at (${b.position[0]}, ${b.position[2]})`);
      });

      console.log('\n📡 gNBs:');
      (layout.gnbs || []).forEach((g, i) => {
        console.log(`  [${i}] ${g.name} at (${g.position[0]}, ${g.position[2]})`);
      });

      console.log('\n📱 UEs:');
      (layout.ues || []).forEach((u, i) => {
        console.log(`  [${i}] ${u.name} at (${u.position[0]}, ${u.position[2]})`);
      });

      console.log('==================================\n');
      console.log('[useDrawPage] refreshScene completed successfully');
    } catch (err) {
      console.error('[useDrawPage] Error in refreshScene:', err);
      setError(err instanceof Error ? err.message : 'Failed to load scene');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    console.log('%c=== useDrawPage 初始化開始 ===', 'color: #ff0000; font-size: 16px; font-weight: bold');
    console.log('時間:', new Date().toLocaleTimeString());
    console.log('調用: useDrawPage.useEffect -> refreshScene()');
    refreshScene();
  }, [refreshScene]);

  // 跑 scenario 時 scenario_driver 會把 UE 位置寫回 Omniverse DB(update_db=True),
  // 但 useDrawPage 只在 mount 抓一次,Scene Layout 不會動。
  // 這裡只 patch trajectories[].position(不動 waypoints/speed/color/UI 選取),
  // 使用者一邊看 scenario 跑、一邊還能繼續編 waypoints 不會被覆蓋。
  //
  // ⚠ simRunning=true 時跳過 polling — 那條路位置真實來源是 useSimPage 的
  // client-side waypoint interpolation(每 1s 算),DB 不會即時被寫(RU update_ues
  // 是 fire-and-forget,且 Omniverse DB 不一定同步反映)。若這時還拉 DB 蓋,
  // Scene Layout 的 UE 會週期性「跳回 DB 內舊位置」。
  //
  // 2026-08-20:sim 跑的時候改拉「執行期 live 位置」而不是什麼都不做。
  //   UeLifecycleManager 算完位置只推 RU 與 Kit(3D),**不寫回 Omniverse DB** ——
  //   所以 3D 會動、2D 不動。原本這裡在 simRunning 時直接 return,期待 useSimPage
  //   接手內插,但 Scene Layout 這條路沒有 useSimPage,畫布就一直停在出生點。
  //   改成問 UE service 拿真值:兩邊同源,也不會再有「跳回 DB 舊位置」。
  useEffect(() => {
    let cancelled = false;
    const id = setInterval(async () => {
      if (simRunningRef.current) {
        try {
          const live = await fetchLiveUePositions();
          if (cancelled || !live.simRunning) return;
          setTrajectories((prev) => {
            if (prev.length === 0) return prev;
            let changed = false;
            const next = prev.map((t) => {
              const p = live.positions[t.name];
              if (!p) return t;                     // 掉話/未 attach 的 UE 留在原地
              const np: [number, number, number] = [p[0], p[1], p[2]];
              if (np[0] !== t.position[0] || np[1] !== t.position[1] || np[2] !== t.position[2]) {
                changed = true;
                return { ...t, position: np };
              }
              return t;
            });
            return changed ? next : prev;
          });
          setLiveUeIds(new Set(Object.keys(live.positions)));
        } catch { /* UE service 拉失敗 → 畫布保持現值,下次再試 */ }
        return;
      }
      try {
        const ues = await omniverseApi.listUes();
        if (cancelled) return;
        setLiveUeIds((prev) => (prev.size === 0 ? prev : new Set()));
        setTrajectories((prev) => {
          if (prev.length === 0) return prev;
          const byName = new Map(ues.map(u => [u.name, u]));
          let changed = false;
          const next = prev.map((t) => {
            const fresh = byName.get(t.name);
            const newPos = fresh ? toXZ(fresh.position) : t.position;
            if (newPos[0] !== t.position[0] || newPos[1] !== t.position[1] || newPos[2] !== t.position[2]) {
              changed = true;
              return { ...t, position: newPos };
            }
            return t;
          });
          return changed ? next : prev;
        });
      } catch { /* 拉失敗忽略,下次再試 */ }
    }, 2000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // 自動偵測 DB 場景「換了」就重讀 — 修「從 /scenarios 套劇本後 editor 場景沒換」。
  // ★ 不綁 simRunning:安全閥是「只有名字集合(sceneSig)變了才 refresh」。跑 sim
  //   中途不會換場景 → 不會誤洗 UE 位置;但若前端 simRunning 卡住,場景仍能正常切換。
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const layout = await omniverseApi.getSceneLayout();
        if (cancelled) return;
        if (sceneSig(layout) !== sceneSigRef.current) {
          console.log('[useDrawPage] DB 場景身分變更 → 自動 refreshScene');
          await refreshScene();
        }
      } catch { /* 拉失敗忽略 */ }
    };
    const id = setInterval(check, 3000);
    // 分頁切回 / 視窗 focus 立即檢查一次(從別頁套了劇本回來不用等 3s)
    const onFocus = () => check();
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onFocus);
    return () => {
      cancelled = true;
      clearInterval(id);
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onFocus);
    };
  }, [refreshScene]);


  const handleAddWaypoint = useCallback(
    (x: number, z: number) => {
      setTrajectories((prev) => {
        const updated = [...prev];
        if (!updated[selectedUEIndex]) return prev;
        updated[selectedUEIndex] = {
          ...updated[selectedUEIndex],
          waypoints: [...(updated[selectedUEIndex].waypoints || []), [x, 0, z]],
        };
        return updated;
      });
    },
    [selectedUEIndex]
  );

  const handleMoveWaypoint = useCallback(
    (idx: number, x: number, z: number) => {
      setTrajectories((prev) => {
        const updated = [...prev];
        if (!updated[selectedUEIndex]?.waypoints) return prev;
        updated[selectedUEIndex].waypoints![idx] = [x, 0, z];
        return updated;
      });
    },
    [selectedUEIndex]
  );

  const handleRemoveWaypoint = useCallback(
    (idx: number) => {
      setTrajectories((prev) => {
        const updated = [...prev];
        if (!updated[selectedUEIndex].waypoints) return prev;
        updated[selectedUEIndex].waypoints = updated[selectedUEIndex].waypoints!.filter(
          (_, i) => i !== idx
        );
        return updated;
      });
    },
    [selectedUEIndex]
  );

  const handleMoveBuilding = useCallback(
    async (name: string, x: number, z: number) => {
      try {
        const currentY = sceneConfig?.buildings?.find((b: any) => b.name === name)?.position?.[1];
        await omniverseApi.updateBuilding(name, {
          position: [x, currentY ?? 0, z],
        });
        await refreshScene();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update building position');
      }
    },
    [sceneConfig, refreshScene]
  );

  const handleMoveGnb = useCallback(
    async (name: string, x: number, z: number) => {
      try {
        // 沿用該 gNB 目前的高度，不要寫死 30 m —— 畫布拖曳只改平面位置。
        // 寫死的話，室內場景裡掛在 2.5 m 的小基站被拖一下就飛回 30 m 高空，
        // 整組室內設定當場失效（2026-09-08 實際踩到）。
        const currentY = sceneConfig?.gnbs?.find((g: any) => g.name === name)?.position?.[1];
        await omniverseApi.updateGnb(name, {
          position: [x, currentY ?? 30, z],
        });
        await refreshScene();
        // AK6: gNB position 改了, Sionna 也要重建 (path_gain 跟距離強相關)
        try {
          await initScene({ scene_id: 'default' });
        } catch (e) {
          console.warn('[scene-rebuild] auto-init failed after handleMoveGnb:', e);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update gNB position');
      }
    },
    [sceneConfig, refreshScene]
  );

  // 分散式 cell(有自己 position)在畫布上被拖曳 → 更新該 cell 座標
  const handleMoveCell = useCallback(
    async (gnbName: string, cellIdx: number, x: number, z: number) => {
      try {
        const g = sceneConfig?.gnbs?.find((gg: any) => gg.name === gnbName);
        if (!g || !g.cells?.[cellIdx]) return;
        const cells = g.cells.map((c: any, i: number) =>
          i === cellIdx
            ? { ...c, position: [x, c.position?.[1] ?? g.position?.[1] ?? 30, z] }
            : c,
        );
        await omniverseApi.updateGnb(gnbName, { cells });
        await refreshScene();
        // cell 位置 = Sionna TX 位置 → path_gain 全變,跟 gNB 移動同樣要重建
        try {
          await initScene({ scene_id: 'default' });
        } catch (e) {
          console.warn('[scene-rebuild] auto-init failed after handleMoveCell:', e);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update cell position');
      }
    },
    [sceneConfig, refreshScene]
  );

  const handleMoveUE = useCallback(
    async (name: string, x: number, z: number) => {
      try {
        const currentY = sceneConfig?.ues?.find((u: any) => u.name === name)?.position?.[1];
        await omniverseApi.updateUe(name, {
          position: [x, currentY ?? 0, z],
        });
        await refreshScene();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update UE position');
      }
    },
    [refreshScene]
  );

  const handleClearTrajectory = useCallback(() => {
    if (!trajectories.length || selectedUEIndex >= trajectories.length) return;
    setTrajectories((prev) => {
      const updated = [...prev];
      updated[selectedUEIndex].waypoints = [];
      return updated;
    });
  }, [selectedUEIndex, trajectories]);

  const handleSpeedChange = useCallback((speed: number) => {
    if (!trajectories.length || selectedUEIndex >= trajectories.length) return;
    setTrajectories((prev) => {
      const updated = [...prev];
      updated[selectedUEIndex].speed_mps = speed;
      return updated;
    });
  }, [selectedUEIndex, trajectories]);

  const handleBuild = useCallback(async (sceneAntennaConfig?: SceneAntennaConfig) => {
    try {
      setLoading(true);
      console.log('%c【Build Scene 開始】', 'color: #0066cc; font-size: 14px; font-weight: bold');

      // 1. 先將所有 UE 軌跡存到 Omniver-RAN DB
      console.log('1️⃣ 保存 UE 軌跡到數據庫...');
      for (const ue of trajectories) {
        if (ue.waypoints && ue.waypoints.length >= 2) {
          await omniverseApi.setUeTrajectory(
            ue.name,
            ue.waypoints,
            ue.speed_mps ?? 1.0,
            true
          );
        }
      }
      console.log('✅ UE 軌跡保存完成');

      // 2. 觸發 Kit rebuild
      console.log('2️⃣ 觸發 Kit 重建場景...');
      await omniverseApi.buildScene();
      console.log('✅ 場景重建命令已發送');

      // 3. 等待 Kit 完成重建（延遲 2 秒，讓 Kit 的命令隊列執行）
      console.log('3️⃣ 等待 Kit 完成重建...');
      await new Promise(resolve => setTimeout(resolve, 2000));

      // 4. 重新加載前端的場景數據（刷新 Canvas）
      console.log('4️⃣ 刷新前端 Scene Layout...');
      await refreshScene();
      console.log('✅ 前端 Canvas 已更新');

      // 5. 初始化 Sionna（DB-only 模式 + MIMO config）
      console.log('5️⃣ 初始化 Sionna...', sceneAntennaConfig ? `(MIMO ${JSON.stringify(sceneAntennaConfig)})` : '');
      await initScene({ scene_id: 'default', scene_antenna_config: sceneAntennaConfig });
      console.log('✅ Sionna 初始化完成');

      // 6. 把同一份 antenna config 推給 RU（PMI precoder 要跟 Sionna scene 對齊）
      //    Build 時固定一次，後續 sim 中不再變動，符合 user 情境。
      if (sceneAntennaConfig) {
        const ruBase = process.env.NEXT_PUBLIC_RU_URL || 'http://localhost:8103';
        console.log('6️⃣ 同步天線設定到 RU...');
        try {
          await fetch(`${ruBase}/api/v0.1/RU/Config/RuController/update_antenna`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              rows: sceneAntennaConfig.gnb_array_rows ?? 1,
              cols: sceneAntennaConfig.gnb_array_cols ?? 1,
              polarization: sceneAntennaConfig.gnb_polarization ?? 'V',
              pattern: sceneAntennaConfig.gnb_antenna_pattern ?? 'tr38901',
            }),
          });
          console.log('✅ RU 天線設定已同步');
        } catch (err) {
          console.warn('⚠️ RU 同步天線失敗（不阻擋 build）:', err);
        }
      }

      // 7. 通知 UE container — 寫 trajectory waypoints + traffic profile
      //    UE container 每 100ms 用 waypoint+speed 算位置寫進 RU/Kit;
      //    每 N ms 依 traffic profile 注 SDU 進 DU /RLC/inject_sdu.
      console.log('7️⃣ 通知 UE container...');
      let ueOk = 0, ueFail = 0;
      for (const ue of trajectories) {
        try {
          // Trajectory: 把 [[x,0,z],...]+ speed 換成 [{x,y,z,t_ms},...]
          if (ue.waypoints && ue.waypoints.length >= 2) {
            const wpsTimed = buildWaypointsFromDraw(
              ue.waypoints as [number, number, number][],
              ue.speed_mps ?? 1.0,
            );
            await ueSetTrajectory(ue.name, wpsTimed, 'loop');
          }
          // Traffic profile: 預設 idle, 若 user 在 UI 設過則用 user 的
          const profile = trafficProfiles[ue.name] || { pattern: 'idle' as const };
          await ueUpdateTrafficProfile(ue.name, profile);
          ueOk += 1;
        } catch (err) {
          ueFail += 1;
          console.warn(`⚠️ UE container sync failed for ${ue.name}:`, err);
        }
      }
      console.log(`✅ UE container 同步: ${ueOk} ok / ${ueFail} fail`);

      setError(null);
      console.log('%c【Build Scene 成功】', 'color: #00aa00; font-size: 14px; font-weight: bold');
    } catch (err) {
      console.error('%c【Build Scene 失敗】', 'color: #ff0000; font-size: 14px; font-weight: bold', err);
      setError(err instanceof Error ? err.message : 'Failed to build scene');
    } finally {
      setLoading(false);
    }
  }, [trajectories, trafficProfiles, refreshScene]);

  const handleClear = useCallback(async () => {
    try {
      setLoading(true);
      console.log('%c【Clear Scene 開始】', 'color: #ff0000; font-size: 14px; font-weight: bold');
      console.log('時間:', new Date().toLocaleTimeString());

      console.log('1️⃣ 正在呼叫 omniverseApi.clearScene()...');
      await omniverseApi.clearScene();
      console.log('✅ clearScene() 成功');

      console.log('2️⃣ 正在呼叫 refreshScene()...');
      await refreshScene();
      console.log('✅ refreshScene() 成功');

      setError(null);
      console.log('%c【Clear Scene 完成】', 'color: #00aa00; font-size: 14px; font-weight: bold');
    } catch (err) {
      console.error('%c【Clear Scene 失敗】', 'color: #ff0000; font-size: 14px; font-weight: bold', err);
      setError(err instanceof Error ? err.message : 'Failed to clear scene');
    } finally {
      setLoading(false);
    }
  }, [refreshScene]);

  const handleSubmit = useCallback(async () => {
    try {
      setLoading(true);
      // 先存軌跡到 DB
      for (const ue of trajectories) {
        if (ue.waypoints && ue.waypoints.length >= 2) {
          await omniverseApi.setUeTrajectory(
            ue.name,
            ue.waypoints,
            ue.speed_mps ?? 1.0,
            true
          );
        }
      }
      // 再設定模擬
      const uePayload = trajectories.map((ue) => ({
        name: ue.name,
        waypoints: ue.waypoints || [],
        speed_mps: ue.speed_mps,
        loop: true,
      }));
      await setupUE(uePayload);
      localStorage.setItem('ueTrajectories', JSON.stringify(trajectories));
      router.push('/editor');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to setup trajectories');
    } finally {
      setLoading(false);
    }
  }, [trajectories, router]);

  const handleCanvasClick = useCallback(() => {
    // Canvas click handler
  }, []);

  const handleCanvasMouseDown = useCallback(() => {
    // Canvas mouse down handler
  }, []);

  const handleCanvasMouseUp = useCallback(() => {
    // Canvas mouse up handler
  }, []);

  const updateUEPositions = useCallback((positionMap: Record<string, [number, number, number]>) => {
    setTrajectories((prev) => {
      return prev.map((ue) => {
        const newPos = positionMap[ue.name];
        if (newPos) {
          return { ...ue, position: newPos };
        }
        return ue;
      });
    });
  }, []);

  return {
    canvasRef,
    sceneConfig,
    selectedUEIndex,
    setSelectedUEIndex,
    trajectories,
    setTrajectories,
    liveUeIds,   // 這些 UE 的座標是執行期真值(非 DB 設定值)
    trafficProfiles,
    setTrafficProfile,
    loading,
    error,
    handleCanvasClick,
    handleCanvasMouseDown,
    handleCanvasMouseUp,
    handleAddWaypoint,
    handleMoveWaypoint,
    handleRemoveWaypoint,
    handleMoveBuilding,
    handleMoveGnb,
    handleMoveCell,
    handleMoveUE,
    handleClearTrajectory,
    handleSpeedChange,
    handleSubmit,
    handleBuild,
    handleClear,
    refreshScene,
    updateUEPositions,
  };
}
