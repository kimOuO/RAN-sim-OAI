'use client';
import { useEffect, useMemo, useState } from 'react';
import { SERIES } from '@/config';
import { useAsync } from '@/hooks/base/useAsync';
import { listKpmSamples } from '@/services/api/archive';
import { listRuns, listScenes } from '@/services/api/runs';
import { mean, xOf } from '@/hooks/feature/kpmDerive';
import type { KpmSample, Series } from '@/types/telemetry';

/** 並看:每個 run 一個顏色(最多 4),同一指標的 run 們畫在同一張圖(sim-time 對齊) */
export function useComparePage() {
  const runs = useAsync(listRuns, []); const scenes = useAsync(listScenes, []);
  const [picked, setPicked] = useState<string[]>([]);
  const [series, setSeries] = useState<Record<string, KpmSample[]>>({});
  useEffect(() => { for (const id of picked) if (!series[id]) listKpmSamples(id).then((s) => setSeries((p) => ({ ...p, [id]: s }))).catch(() => undefined); }, [picked, series]);
  const sceneName = useMemo(() => new Map((scenes.data ?? []).map((s) => [s.scene_uuid, s.legacy_scenario_id || s.name])), [scenes.data]);
  const candidates = useMemo(() => (runs.data ?? []).filter((r) => r.status === 'stopped' || r.status === 'running')
    .map((r) => ({ run: r, label: `${sceneName.get(r.f_scene_uuid) ?? '?'} · ${r.mode} ${r.speed_x}×`, short: (sceneName.get(r.f_scene_uuid) ?? '?') + ' ' + r.scene_run_uuid.slice(-4) })), [runs.data, sceneName]);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < 4 ? [...p, id] : p));
  const colorOf = (id: string) => SERIES[Math.max(0, picked.indexOf(id)) % SERIES.length];
  const labelOf = (id: string) => candidates.find((c) => c.run.scene_run_uuid === id)?.short ?? id;
  const metric = (pick: (w: KpmSample) => number | null): Series[] => picked.map((id) => ({ key: id, label: labelOf(id), color: colorOf(id), points: (series[id] ?? []).map((w, i) => ({ x: xOf(i), y: pick(w) })) }));
  const charts = useMemo(() => ({
    prb: metric((w) => mean(Object.values(w.per_cell).map((c) => c.prb_pct_dl))),
    thp: metric((w) => Object.values(w.per_ue).reduce((a, u) => a + (u.throughput_dl_mbps ?? 0), 0)),
    sinr: metric((w) => mean(Object.values(w.per_ue).map((u) => u.sinr_db))),
    ue: metric((w) => Object.keys(w.per_ue).length),
    mcs: metric((w) => mean(Object.values(w.per_ue).map((u) => u.mcs_dl))),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [picked, series, candidates]);
  return { candidates, picked, toggle, charts, colorOf, labelOf, loaded: picked.filter((id) => series[id]).length };
}
