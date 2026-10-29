'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAsync } from '@/hooks/base/useAsync';
import { cellColorMap } from '@/hooks/feature/kpmDerive';
import { cellOwners, stripTag } from '@/hooks/feature/live3d';
import type { UeLabelMode } from '@/components/scene3d/LiveScene3D';
import type { UeFlash } from '@/hooks/feature/useRunLive3dPage';
import { getSceneTree3d } from '@/services/api/runs';
import type { KpmSample, UeKpm } from '@/types/telemetry';

const FLASH_MS = 2500;
const toState = (w: KpmSample | undefined) => Object.fromEntries(Object.entries(w?.per_ue ?? {}).map(([id, k]) => [id, { ...k, cell: stripTag(k.serving_cell || '') }])) as Record<string, UeKpm & { cell: string }>;

/** 回放 3D:選到的視窗 → 劇本時間(scene_t_sec)、UE 狀態;與前一窗比出換手 / RLF;可自動播放 */
export function usePlayback3d(sceneUuid: string | undefined, all: KpmSample[], idx: number, setIdx: (i: number) => void) {
  const tree = useAsync(() => (sceneUuid ? getSceneTree3d(sceneUuid) : Promise.resolve(null)), [sceneUuid]);
  const w = all[idx]; const prevW = idx > 0 ? all[idx - 1] : undefined;
  const ueState = useMemo(() => toState(w), [w]);
  const sceneT = w?.scene_t_sec ?? null;
  const simNow = useCallback(() => sceneT ?? 0, [sceneT]);
  const [flashes, setFlashes] = useState<Record<string, { kind: UeFlash; until: number }>>({});
  useEffect(() => {
    const before = toState(prevW); const until = performance.now() + FLASH_MS; const f: Record<string, { kind: UeFlash; until: number }> = {};
    for (const [id, s] of Object.entries(ueState)) {
      const b = before[id]; const was = b && b.cell && b.sinr_db > -99 ? b.cell : '';
      if (was && (!s.cell || s.sinr_db <= -99)) f[id] = { kind: 'rlf', until };
      else if (was && s.cell && was !== s.cell) f[id] = { kind: 'ho', until };
    }
    setFlashes(f);
  }, [ueState, prevW]);
  const cellNames = useMemo(() => (tree.data?.gnbs ?? []).flatMap((g) => g.dus.flatMap((d) => d.cells.map((c) => c.name))), [tree.data]);
  const color = useMemo(() => cellColorMap(cellNames), [cellNames]);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(5);   // 每秒前進幾個視窗
  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => { if (idx >= all.length - 1) setPlaying(false); else setIdx(idx + 1); }, 1000 / rate);
    return () => clearInterval(t);
  }, [playing, rate, idx, all.length, setIdx]);
  const [selected, setSelected] = useState<string | null>(null);
  const owners = useMemo(() => cellOwners(tree.data), [tree.data]);
  const [labelMode, setLabelMode] = useState<UeLabelMode>('brief');
  const [showSites, setShowSites] = useState(true);
  return { tree: tree.data, ueState, flashes, color, simNow, hasSceneTime: sceneT != null, playing, toggle: () => setPlaying((p) => !p), rate, setRate, selected, setSelected, owners, labelMode, setLabelMode, showSites, setShowSites };
}
