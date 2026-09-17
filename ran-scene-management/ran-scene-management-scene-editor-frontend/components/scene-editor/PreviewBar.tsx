'use client';
import type { ScenePreview } from '@/hooks/feature/useScenePreview';

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
/** 畫布下方的路徑播放列:播放 / 暫停、時間軸、倍率 */
export function PreviewBar({ p }: { p: ScenePreview }) {
  if (p.duration <= 0) return null;
  return (
    <div className="previewbar">
      <button onClick={p.toggle}>{p.playing ? '❚❚' : '▶'}</button>
      <input type="range" min={0} max={p.duration} step={0.5} value={p.t} onChange={(e) => p.setT(Number(e.target.value))} />
      <span className="mono small">{fmt(p.t)} / {fmt(p.duration)}</span>
      <select value={p.rate} onChange={(e) => p.setRate(Number(e.target.value))}>{[1, 5, 10, 30, 60].map((r) => <option key={r} value={r}>{r}×</option>)}</select>
    </div>
  );
}
