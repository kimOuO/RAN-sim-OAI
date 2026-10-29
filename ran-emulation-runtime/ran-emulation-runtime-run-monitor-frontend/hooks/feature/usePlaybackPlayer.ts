'use client';
import { useMemo } from 'react';
import { useAsync } from '@/hooks/base/useAsync';
import { allCells, cellColorMap, cellSeries, meanSinrByCell, prbDl, thpDlByCell, ueCountByCell } from '@/hooks/feature/kpmDerive';
import { usePlayback3d } from '@/hooks/feature/usePlayback3d';
import { controlOrigin } from '@/hooks/feature/controlEvents';
import { listControlEventsOfSeq, listExecutions, listHandoverEventsOfSeq, listKpmSamplesOfSeq } from '@/services/api/archive';
import { getRun, listScenes } from '@/services/api/runs';
import type { KpmSample } from '@/types/telemetry';

export interface TimelineMark { i: number; kind: 'ho' | 'rlf' | 'ric' | 'son'; label: string; t: number }

/** 某一次執行的回放:一條時間軸(視窗索引)同時驅動 3D、UE 卡片、圖表與事件 */
export function usePlaybackPlayer(runUuid: string, seq: number, idx: number, setIdx: (i: number) => void) {
  const run = useAsync(() => getRun(runUuid), [runUuid]);
  const scenes = useAsync(listScenes, []);
  const exec = useAsync(async () => (await listExecutions(runUuid)).find((e) => e.run_seq === seq) ?? null, [runUuid, seq]);
  const kpm = useAsync(async () => (await listKpmSamplesOfSeq(runUuid, seq)).sort((a, b) => (a.scene_t_sec ?? a.sim_time_ms / 1000) - (b.scene_t_sec ?? b.sim_time_ms / 1000) || a.id - b.id), [runUuid, seq]);
  const hos = useAsync(() => listHandoverEventsOfSeq(runUuid, seq), [runUuid, seq]);
  const ctrls = useAsync(() => listControlEventsOfSeq(runUuid, seq), [runUuid, seq]);
  const all: KpmSample[] = useMemo(() => kpm.data ?? [], [kpm.data]);
  const v = usePlayback3d(run.data?.f_scene_uuid, all, idx, setIdx);

  const tSec = useMemo(() => all.map((w) => w.scene_t_sec ?? w.sim_time_ms / 1000), [all]);
  const idxAt = (t: number) => { let lo = 0, hi = tSec.length - 1; if (hi < 0) return 0; while (lo < hi) { const m = (lo + hi) >> 1; if (tSec[m] < t) lo = m + 1; else hi = m; } return lo; };
  const cells = useMemo(() => allCells(all), [all]);
  const color = useMemo(() => cellColorMap(cells), [cells]);
  const charts = useMemo(() => ({
    prb: cellSeries(all, cells, color, prbDl), thp: cellSeries(all, cells, color, thpDlByCell),
    ues: cellSeries(all, cells, color, ueCountByCell), sinr: cellSeries(all, cells, color, meanSinrByCell),
  }), [all, cells, color]);

  const marks = useMemo<TimelineMark[]>(() => {
    const m: TimelineMark[] = [];
    for (const h of hos.data ?? []) { const t = h.at_sim_ms / 1000; m.push({ i: idxAt(t), t, kind: h.outcome === 'RLF' ? 'rlf' : 'ho', label: h.outcome === 'RLF' ? `${h.ue_id} RLF @ ${h.source_cell}` : `${h.ue_id} 換手 ${h.source_cell} → ${h.target_cell}${h.outcome === 'SUCC' ? '' : `(${h.outcome})`}` }); }
    for (const c of ctrls.data ?? []) { const t = c.at_sim_ms / 1000; m.push({ i: idxAt(t), t, kind: controlOrigin(c.source) === 'ric' ? 'ric' : 'son', label: `${c.source} ${c.action_type} → ${c.target}(${c.outcome})` }); }
    return m.sort((a, b) => a.t - b.t);
  }, [hos.data, ctrls.data, tSec]);   // eslint-disable-line react-hooks/exhaustive-deps

  const cur = all[idx]; const curT = tSec[idx] ?? 0;
  const recent = useMemo(() => marks.filter((m) => m.t <= curT + 0.5).slice(-30).reverse(), [marks, curT]);
  const sofar = useMemo(() => ({ ho: marks.filter((m) => m.kind === 'ho' && m.t <= curT).length, rlf: marks.filter((m) => m.kind === 'rlf' && m.t <= curT).length, ctrl: marks.filter((m) => (m.kind === 'ric' || m.kind === 'son') && m.t <= curT).length }), [marks, curT]);
  const scene = (scenes.data ?? []).find((s) => s.scene_uuid === run.data?.f_scene_uuid);
  return {
    run: run.data, exec: exec.data, scene, loading: kpm.status === 'loading' || run.status === 'loading', error: kpm.error ?? run.error,
    all, cur, curT, tSec, charts, cells, color, marks, recent, sofar, v,
  };
}
