'use client';
import { ORCHESTRATOR_API } from '@/config';
import { useAsync } from '@/hooks/base/useAsync';
import { usePolling } from '@/hooks/base/usePolling';
import { getRun, listScenes } from '@/services/api/runs';
import { post } from '@/services/clients/apiClient';
import type { O1Observation } from '@/types/o1';

export function useRunO1Page(id: string) {
  const run = useAsync(() => getRun(id), [id]);
  const scenes = useAsync(listScenes, []);
  const observation = useAsync(() => post<O1Observation>(`${ORCHESTRATOR_API}/Run_lifecycle/O1ObservationReader/read`, { scene_run_uuid: id }, { timeoutMs: 20000 }), [id]);
  usePolling(run.refetch, 10000, true);
  // Keep polling after stop: the final snapshot and archived logs arrive during teardown.
  usePolling(observation.refetch, 10000, true);
  const scene = (scenes.data ?? []).find((s) => s.scene_uuid === run.data?.f_scene_uuid);
  return { run: run.data, error: run.error, sceneName: scene?.legacy_scenario_id || scene?.name || '',
    observation: observation.data, observationError: observation.error, loading: observation.status === 'loading', refresh: observation.refetch };
}
