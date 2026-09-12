'use client';

import { useMemo } from 'react';

interface UeTrajectory {
  name: string;
  positions: number[][];   // [[t, x, y, z], ...]
}

interface CellMarker {
  cell_id: string;
  x: number;
  z: number;
  azimuth_deg?: number;
}

interface Props {
  ues: UeTrajectory[];
  cells: CellMarker[];     // gNB / cell positions(from scene)
  simT: number;            // current sim-time(seconds)
  width?: number;
  height?: number;
}

// Interpolate UE position at given t
function interpolate(positions: number[][], t: number): [number, number] {
  if (!positions || positions.length === 0) return [0, 0];
  if (t <= positions[0][0]) return [positions[0][1], positions[0][3]];
  if (t >= positions[positions.length - 1][0]) {
    const p = positions[positions.length - 1];
    return [p[1], p[3]];
  }
  for (let i = 0; i < positions.length - 1; i++) {
    const a = positions[i], b = positions[i + 1];
    if (a[0] <= t && t <= b[0]) {
      const r = b[0] === a[0] ? 0 : (t - a[0]) / (b[0] - a[0]);
      return [a[1] + (b[1] - a[1]) * r, a[3] + (b[3] - a[3]) * r];
    }
  }
  const last = positions[positions.length - 1];
  return [last[1], last[3]];
}

const COLORS = ['#0ea5e9', '#ec4899', '#10b981', '#f59e0b', '#a855f7'];

export function ScenarioMap({ ues, cells, simT, width = 380, height = 260 }: Props) {
  // 自動算邊界含所有 UE waypoint + cell
  const bounds = useMemo(() => {
    let xs: number[] = [], zs: number[] = [];
    for (const ue of ues) for (const p of ue.positions) { xs.push(p[1]); zs.push(p[3]); }
    for (const c of cells) { xs.push(c.x); zs.push(c.z); }
    if (xs.length === 0) return { minX: -100, maxX: 100, minZ: -100, maxZ: 100 };
    const pad = 30;
    return {
      minX: Math.min(...xs) - pad, maxX: Math.max(...xs) + pad,
      minZ: Math.min(...zs) - pad, maxZ: Math.max(...zs) + pad,
    };
  }, [ues, cells]);

  const toX = (x: number) => ((x - bounds.minX) / (bounds.maxX - bounds.minX)) * width;
  // z 軸畫面上「往下=正z」反過來,讓「北邊(z>0)」在地圖上方
  const toY = (z: number) => height - ((z - bounds.minZ) / (bounds.maxZ - bounds.minZ)) * height;

  return (
    <svg width={width} height={height} style={{ background: '#020617', borderRadius: 4, display: 'block' }}>
      {/* grid */}
      {[0.25, 0.5, 0.75].map((f, i) => (
        <g key={i}>
          <line x1={width * f} y1={0} x2={width * f} y2={height} stroke="#1e293b" />
          <line x1={0} y1={height * f} x2={width} y2={height * f} stroke="#1e293b" />
        </g>
      ))}
      {/* axis labels */}
      <text x={4} y={12} fill="#64748b" fontSize={9} fontFamily="ui-monospace">
        x∈[{bounds.minX.toFixed(0)},{bounds.maxX.toFixed(0)}] z↑北
      </text>

      {/* cell markers */}
      {cells.map((c, i) => {
        const cx = toX(c.x); const cy = toY(c.z);
        // azimuth arrow:0°=朝北(z+),180°=朝南(z-),90°=朝東(x+)
        const az = c.azimuth_deg ?? 0;
        const rad = (az * Math.PI) / 180;
        // 方向 (sinθ, -cosθ) screen 座標
        const dx = Math.sin(rad) * 20;
        const dy = -Math.cos(rad) * 20;
        return (
          <g key={c.cell_id}>
            <circle cx={cx} cy={cy} r={6} fill="#fbbf24" stroke="#92400e" strokeWidth={1.5} />
            <line x1={cx} y1={cy} x2={cx + dx} y2={cy + dy}
                  stroke="#fbbf24" strokeWidth={2} markerEnd="url(#arr)" />
            <text x={cx + 8} y={cy - 7} fill="#fde68a" fontSize={10} fontFamily="ui-monospace">
              {c.cell_id}
            </text>
          </g>
        );
      })}
      <defs>
        <marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <polygon points="0 0, 6 3, 0 6" fill="#fbbf24" />
        </marker>
      </defs>

      {/* UE trails + current position */}
      {ues.map((ue, ui) => {
        const color = COLORS[ui % COLORS.length];
        const pts = ue.positions.map(p => `${toX(p[1])},${toY(p[3])}`).join(' ');
        const [curX, curZ] = interpolate(ue.positions, simT);
        return (
          <g key={ue.name}>
            <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5}
                      strokeDasharray="3 3" opacity={0.55} />
            <circle cx={toX(curX)} cy={toY(curZ)} r={5} fill={color}
                    stroke="#0f172a" strokeWidth={1.5} />
            <text x={toX(curX) + 8} y={toY(curZ) + 4}
                  fill={color} fontSize={10} fontFamily="ui-monospace">
              {ue.name} ({curX.toFixed(0)},{curZ.toFixed(0)})
            </text>
          </g>
        );
      })}
    </svg>
  );
}
