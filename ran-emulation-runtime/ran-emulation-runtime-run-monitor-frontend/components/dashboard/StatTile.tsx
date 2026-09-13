import type { ReactNode } from 'react';
/** Grafana 式 stat:大數字 + 單位 + 與上一窗差值 + 可選迷你圖/狀態色 */
export function StatTile({ label, value, unit = '', delta, tone, digits = 1, foot, children }: { label: string; value: number | null | undefined; unit?: string; delta?: number | null; tone?: 'good' | 'warning' | 'serious' | 'critical'; digits?: number; foot?: string; children?: ReactNode }) {
  const v = value == null || Number.isNaN(value) ? '—' : value.toFixed(digits);
  const d = delta == null || !Number.isFinite(delta) || Math.abs(delta) < 1e-9 ? null : delta;
  return (
    <div className={`stat ${tone ?? ''}`}>
      <div className="stat-l">{label}</div>
      <div className="stat-v">{v}<small>{unit}</small></div>
      <div className="stat-f">{d != null && <span className={d > 0 ? 'up' : 'down'}>{d > 0 ? '▲' : '▼'} {Math.abs(d).toFixed(digits)}{unit}</span>}{foot && <span className="muted">{foot}</span>}</div>
      {children}
    </div>
  );
}
