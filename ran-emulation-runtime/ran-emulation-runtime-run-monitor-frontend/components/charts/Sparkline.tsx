import type { Pt } from '@/types/telemetry';
/** 迷你折線(表格內、stat tile 內),沒有軸 */
export function Sparkline({ points, width = 120, height = 28, color = 'var(--cyan)', yMin, yMax }: { points: Pt[]; width?: number; height?: number; color?: string; yMin?: number; yMax?: number }) {
  const ys = points.map((p) => p.y).filter((v): v is number => v != null);
  if (!ys.length) return <svg width={width} height={height} />;
  const lo = yMin ?? Math.min(...ys), hi = yMax ?? Math.max(...ys); const n = points.length;
  const px = (i: number) => (n > 1 ? (i / (n - 1)) * (width - 4) + 2 : width / 2); const py = (v: number) => (hi === lo ? height / 2 : height - 3 - ((v - lo) / (hi - lo)) * (height - 6));
  let d = '', pen = false; points.forEach((p, i) => { if (p.y == null) { pen = false; return; } d += `${pen ? 'L' : 'M'}${px(i).toFixed(1)},${py(p.y).toFixed(1)}`; pen = true; });
  const last = [...points].reverse().find((p) => p.y != null);
  return <svg width={width} height={height} role="img" aria-label="sparkline"><path d={d} fill="none" stroke={color} strokeWidth="1.5" />{last && <circle cx={px(points.indexOf(last))} cy={py(last.y as number)} r="2" fill={color} />}</svg>;
}
