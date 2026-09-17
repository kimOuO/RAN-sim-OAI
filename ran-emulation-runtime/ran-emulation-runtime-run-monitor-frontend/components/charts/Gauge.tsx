/** 圓環百分比(cell 當下負載);顏色跟 cell 走,超過門檻加狀態環 */
export function Gauge({ value: raw, label, sub, color, size = 84, warn = 85 }: { value: number | null; label: string; sub?: string; color: string; size?: number; warn?: number }) {
  const value = raw != null && Number.isFinite(raw) ? raw : null;   // NaN 當成沒有資料
  const r = size / 2 - 7, C = 2 * Math.PI * r; const v = value == null ? 0 : Math.max(0, Math.min(100, value));
  const tone = value == null ? '' : v >= warn ? 'serious' : v >= warn * 0.7 ? 'warning' : '';
  return (
    <div className={`gauge ${tone}`} title={`${label}: ${value == null ? '—' : value.toFixed(1)}%`}>
      <svg width={size} height={size} role="img" aria-label={`${label} ${v.toFixed(0)}%`}>
        <circle cx={size / 2} cy={size / 2} r={r} className="g-track" strokeWidth="7" fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth="7" fill="none" strokeLinecap={v > 0 ? "round" : "butt"} strokeDasharray={`${(v / 100) * C} ${C}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
        <text x="50%" y="50%" dy="5" textAnchor="middle" className="g-val">{value == null ? '—' : `${value.toFixed(0)}%`}</text>
      </svg>
      <div className="g-l mono">{label}</div>{sub && <div className="g-s muted">{sub}</div>}
    </div>
  );
}
