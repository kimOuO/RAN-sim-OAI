'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { setupUE } from '@/services/api/simLoop';
import { initScene } from '@/services/api/scene';
import * as omniverseApi from '@/services/api/omniverse';
import type { SceneLayout, UE, SceneAntennaConfig } from '@/types';

function toXZ(v: any): [number, number, number] {
  if (Array.isArray(v)) return [v[0] ?? 0, v[1] ?? 0, v[2] ?? 0];
  return [v?.x ?? 0, v?.y ?? 0, v?.z ?? 0];
}

export function useDrawPage() {
  const router = useRouter();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [sceneConfig, setSceneConfig] = useState<SceneLayout | null>(null);
  const [selectedUEIndex, setSelectedUEIndex] = useState(0);
  const [trajectories, setTrajectories] = useState<UE[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshScene = useCallback(async () => {
    try {
      setLoading(true);
      console.log('[useDrawPage] Starting refreshScene...');
      const layout = await omniverseApi.getSceneLayout();
      console.log('[useDrawPage] Got layout:', layout);
      setSceneConfig(layout);

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
        await omniverseApi.updateBuilding(name, {
          position: [x, 0, z],
        });
        await refreshScene();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update building position');
      }
    },
    [refreshScene]
  );

  const handleMoveGnb = useCallback(
    async (name: string, x: number, z: number) => {
      try {
        await omniverseApi.updateGnb(name, {
          position: [x, 30, z],
        });
        await refreshScene();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update gNB position');
      }
    },
    [refreshScene]
  );

  const handleMoveUE = useCallback(
    async (name: string, x: number, z: number) => {
      try {
        await omniverseApi.updateUe(name, {
          position: [x, 0, z],
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

      setError(null);
      console.log('%c【Build Scene 成功】', 'color: #00aa00; font-size: 14px; font-weight: bold');
    } catch (err) {
      console.error('%c【Build Scene 失敗】', 'color: #ff0000; font-size: 14px; font-weight: bold', err);
      setError(err instanceof Error ? err.message : 'Failed to build scene');
    } finally {
      setLoading(false);
    }
  }, [trajectories, refreshScene]);

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
