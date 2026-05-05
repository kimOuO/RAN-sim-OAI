'use client';

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { initScene } from '@/services/api/scene';
import { SCENE_CONFIG_URL } from '@/config';
import type { SceneConfig } from '@/types';

export function useScenePage() {
  const router = useRouter();
  const [sceneConfig, setSceneConfig] = useState<SceneConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadSceneConfig = async () => {
      try {
        const response = await fetch(SCENE_CONFIG_URL);
        if (!response.ok) {
          throw new Error(`Failed to load scene config: ${response.statusText}`);
        }
        const config = await response.json();
        setSceneConfig(config);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };
    loadSceneConfig();
  }, []);

  const handleInitScene = useCallback(async () => {
    if (!sceneConfig) return;

    try {
      setLoading(true);
      const response = await initScene(sceneConfig);
      localStorage.setItem('sessionUuid', response.session_uuid);
      localStorage.setItem('sceneId', response.scene_id);
      router.push('/draw');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to initialize scene');
    } finally {
      setLoading(false);
    }
  }, [sceneConfig, router]);

  return { sceneConfig, loading, error, handleInitScene };
}
