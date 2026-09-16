import type { BeamCell } from '@/hooks/feature/beamDerive';

/** 每 cell 的波束使用分佈(GoB)。色深 = 使用比例,數字 = 該波束的平均 SINR。 */
export function BeamUsagePanel({ cells }: { cells: BeamCell[] }) {
  if (!cells.length) return <div className="muted">此 run 的天線沒有波束網格(單埠或 Cat A 未設定 GoB)</div>;
  return (
    <div className="beam-usage">
      {cells.map((c) => (
        <div key={c.cell} className="beam-row">
          <div className="beam-cell"><b className="mono">{c.cell}</b><span className="muted"> · {c.beams.length} 道用過 · {c.total} 筆</span></div>
          <div className="beam-strip">
            {c.beams.map((b) => (
              <span key={b.id} className="beam-chip" title={`波束 ${b.id} · 佔比 ${(b.share * 100).toFixed(1)}% · 平均 SINR ${b.sinr?.toFixed(1) ?? '—'} dB`}
                style={{ background: `rgba(57,135,229,${0.15 + 0.85 * b.share})` }}>
                <b className="mono">#{b.id}</b>
                <i>{b.sinr != null ? `${b.sinr.toFixed(0)}dB` : '—'}</i>
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
