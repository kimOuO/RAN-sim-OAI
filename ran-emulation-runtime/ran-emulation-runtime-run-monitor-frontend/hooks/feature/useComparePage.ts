'use client';
import { useEffect, useMemo, useState } from 'react';
import { useAsync } from '@/hooks/base/useAsync';
import { listKpmSamples } from '@/services/api/archive';
import { listRuns, listScenes } from '@/services/api/runs';
import type { KpmSample } from '@/types/telemetry';

export function useComparePage() {
  const runs = useAsync(listRuns, []); const scenes = useAsync(listScenes, []);
  const [picked, setPicked] = useState<string[]>([]);
  const [series, setSeries] = useState<Record<string, KpmSample[]>>({});
  useEffect(() => { for (const id of picked) if (!series[id]) listKpmSamples(id).then((s) => setSeries((p) => ({ ...p, [id]: s }))).catch(() => undefined); }, [picked, series]);
  const sceneName = useMemo(() => new Map((scenes.data ?? []).map((s) => [s.scene_uuid, s.legacy_scenario_id || s.name])), [scenes.data]);
  const candidates = useMemo(() => (runs.data ?? []).filter((r) => r.status === 'stopped' || r.status === 'running').map((r) => ({ run: r, label: `${sceneName.get(r.f_scene_uuid) ?? '?'} · ${r.mode} ${r.speed_x}× · ${r.status}` })), [runs.data, sceneName]);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < 4 ? [...p, id] : p));
  /** 每個 run 的 per-cell PrbTotDl 序列(sim-time 對齊由 x 軸共用 sim_time_ms 達成) */
  const perRunCells = useMemo(() => Object.fromEntries(picked.map((id) => {
    const m: Record<string, { t: number; v: number }[]> = {};
    for (const s of series[id] ?? []) for (const [c, k] of Object.entries(s.per_cell)) (m[c] ??= []).push({ t: s.sim_time_ms, v: k.prb_pct_dl });
    return [id, m];
  })), [picked, series]);
  return { candidates, picked, toggle, perRunCells, labelOf: (id: string) => candidates.find((c) => c.run.scene_run_uuid === id)?.label ?? id };
}
