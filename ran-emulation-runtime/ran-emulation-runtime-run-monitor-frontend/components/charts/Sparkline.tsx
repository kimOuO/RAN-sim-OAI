/** 內建 SVG 折線(不拉圖表庫):一條序列、一個尺度、端點強調、y 軸兩個刻度。 */
export function Sparkline({ points, width = 260, height = 56, unit = '', color = 'currentColor', yMin, yMax }:
  { points: { t: number; v: number }[]; width?: number; height?: number; unit?: string; color?: string; yMin?: number; yMax?: number }) {
  if (!points.length) return <svg width={width} height={height} role="img" aria-label="no data" />;
  const xs = points.map((p) => p.t), ys = points.map((p) => p.v);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), lo = yMin ?? Math.min(...ys), hi = yMax ?? Math.max(...ys);
  const px = (t: number) => (x1 === x0 ? width / 2 : 34 + ((t - x0) / (x1 - x0)) * (width - 40));
  const py = (v: number) => (hi === lo ? height / 2 : height - 6 - ((v - lo) / (hi - lo)) * (height - 12));
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${px(p.t).toFixed(1)},${py(p.v).toFixed(1)}`).join(' ');
  const last = points[points.length - 1];
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`series of ${points.length} points`}>
      <text x="2" y="10" fontSize="9" fill="currentColor" opacity=".6">{hi.toFixed(0)}{unit}</text>
      <text x="2" y={height - 2} fontSize="9" fill="currentColor" opacity=".6">{lo.toFixed(0)}{unit}</text>
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" />
      <circle cx={px(last.t)} cy={py(last.v)} r="2.5" fill={color} />
    </svg>
  );
}
