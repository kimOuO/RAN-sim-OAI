'use client';
import { useMemo, useState } from 'react';
import { POLL_MS } from '@/config';
import { useAsync } from '@/hooks/base/useAsync';
import { usePolling } from '@/hooks/base/usePolling';
import { getDuTick, getE2AdapterStatus, getUeDriverStatus, listRuns, listScenes } from '@/services/api/runs';

export function useRunListPage() {
  const runs = useAsync(listRuns, []); const scenes = useAsync(listScenes, []);
  const tick = useAsync(getDuTick, []); const ue = useAsync(getUeDriverStatus, []); const e2 = useAsync(getE2AdapterStatus, []);
  const [statusFilter, setStatusFilter] = useState<string>('all'); const [q, setQ] = useState('');
  usePolling(runs.refetch, POLL_MS, true); usePolling(tick.refetch, POLL_MS, true); usePolling(ue.refetch, POLL_MS, true); usePolling(e2.refetch, POLL_MS * 3, true);
  const sceneName = useMemo(() => new Map((scenes.data ?? []).map((s) => [s.scene_uuid, s.legacy_scenario_id || s.name])), [scenes.data]);
  const all = useMemo(() => [...(runs.data ?? [])].sort((a, b) => (b.started_at ?? '').localeCompare(a.started_at ?? '') || b.scene_run_uuid.localeCompare(a.scene_run_uuid)), [runs.data]);
  const counts = useMemo(() => { const m: Record<string, number> = {}; for (const r of all) m[r.status] = (m[r.status] ?? 0) + 1; return m; }, [all]);
  const rows = useMemo(() => all.filter((r) => statusFilter === 'all' || r.status === statusFilter).map((r) => ({ run: r, sceneName: sceneName.get(r.f_scene_uuid) ?? r.f_scene_uuid }))
    .filter((r) => !q || r.sceneName.toLowerCase().includes(q.toLowerCase())), [all, statusFilter, sceneName, q]);
  return { rows, counts, total: all.length, status: runs.status, error: runs.error, statusFilter, setStatusFilter, q, setQ, duTick: tick.data, ueDriver: ue.data, e2: e2.data };
}
