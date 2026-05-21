'use client';

import { useState, useCallback } from 'react';
import { useAsync } from '@/hooks/base/useAsync';
import * as omniverseApi from '@/services/api/omniverse';
import { initScene } from '@/services/api/scene';
import type { UsdAsset, Building, AsyncState } from '@/types';

export interface SceneEditorState {
  buildings: AsyncState<Building[]>;
  gnbs: AsyncState<any[]>;
  ues: AsyncState<any[]>;
  assets: AsyncState<UsdAsset[]>;
  createBuilding: (data: Partial<Building>) => Promise<void>;
  createGNB: (data: any) => Promise<void>;
  createUE: (data: any) => Promise<void>;
  deleteBuilding: (name: string) => Promise<void>;
  deleteGNB: (name: string) => Promise<void>;
  deleteUE: (name: string) => Promise<void>;
  applyScene: (sceneId: string) => Promise<void>;
  isCreating: boolean;
  isDeleting: boolean;
  isApplying: boolean;
}

export function useSceneEditor(): SceneEditorState {
  const [isCreating, setIsCreating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isApplying, setIsApplying] = useState(false);

  // Note: Buildings, gNBs, UEs are fetched via SceneLayoutReader in useDrawPage
  // Assets are fetched separately when needed for object creation
  const buildings = useAsync(async () => [], false);
  const gnbs = useAsync(async () => [], false);
  const ues = useAsync(async () => [], false);
  const assets = useAsync(async () => {
    try {
      return await omniverseApi.listAssets();
    } catch (e) {
      console.warn('Failed to load assets, using empty list:', e);
      return [];
    }
  }, true);

  const createBuilding = useCallback(
    async (data: Partial<Building>) => {
      try {
        setIsCreating(true);
        // 如果没有座标，设置默认位置 [0, 0, 0]
        const fullData = {
          position: [0, 0, 0] as [number, number, number],
          ...data,
        };
        await omniverseApi.createBuilding(fullData);
        await buildings.refetch();
      } finally {
        setIsCreating(false);
      }
    },
    [buildings]
  );

  const createGNB = useCallback(
    async (data: any) => {
      try {
        setIsCreating(true);
        const fullData = {
          position: [0, 30, 0],
          ...data,
        };
        await omniverseApi.createGnb(fullData);
        await gnbs.refetch();
        // AK6: auto-trigger Physics scene rebuild so Sionna sees new gNB name +
        // path_gain dict key matches what user typed (no env-var hardcoded map needed).
        try {
          await initScene({ scene_id: 'default' });
        } catch (e) {
          console.warn('[scene-rebuild] auto-init failed after createGNB:', e);
        }
      } finally {
        setIsCreating(false);
      }
    },
    [gnbs]
  );

  const createUE = useCallback(
    async (data: any) => {
      try {
        setIsCreating(true);
        const fullData = {
          position: [0, 0, 0],
          ...data,
        };
        await omniverseApi.createUe(fullData);
        await ues.refetch();
      } finally {
        setIsCreating(false);
      }
    },
    [ues]
  );

  const deleteBuilding = useCallback(
    async (name: string) => {
      try {
        setIsDeleting(true);
        await omniverseApi.deleteBuilding(name);
        await buildings.refetch();
      } finally {
        setIsDeleting(false);
      }
    },
    [buildings]
  );

  const deleteGNB = useCallback(
    async (name: string) => {
      try {
        setIsDeleting(true);
        await omniverseApi.deleteGnb(name);
        await gnbs.refetch();
        // AK6: rebuild Sionna scene so removed gNB no longer in path_gain dict
        try {
          await initScene({ scene_id: 'default' });
        } catch (e) {
          console.warn('[scene-rebuild] auto-init failed after deleteGNB:', e);
        }
      } finally {
        setIsDeleting(false);
      }
    },
    [gnbs]
  );

  const deleteUE = useCallback(
    async (name: string) => {
      try {
        setIsDeleting(true);
        await omniverseApi.deleteUe(name);
        await ues.refetch();
      } finally {
        setIsDeleting(false);
      }
    },
    [ues]
  );

  const applyScene = useCallback(
    async (sceneId: string) => {
      try {
        setIsApplying(true);
        // DB-only mode: only send scene_id; SceneGateway/init fetches buildings/gnbs from Omniver-RAN DB
        const config = {
          scene_id: sceneId,
          // Intentionally omit geometry_source and gnbs to trigger DB-only fallback
          // This ensures only existing USD assets from Omniver-RAN are used
        };
        await initScene(config);
      } finally {
        setIsApplying(false);
      }
    },
    []
  );

  return {
    buildings,
    gnbs,
    ues,
    assets,
    createBuilding,
    createGNB,
    createUE,
    deleteBuilding,
    deleteGNB,
    deleteUE,
    applyScene,
    isCreating,
    isDeleting,
    isApplying,
  };
}
