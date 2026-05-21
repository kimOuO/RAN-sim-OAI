// Phase B — 從 scenario JSON 計算 input profile(traffic / position),給圖表用
// 輸出格式對齊 SignalChart:{ tick: number, <series>: number }[]

export interface RawScenario {
  scenario_id: string;
  scene_id: string;
  duration_sec: number;
  tick_ms: number;
  ues: Array<{ name: string; positions: number[][] }>;
  traffic: Array<{ ue_name: string; profile: number[][] }>;
  default_serving_cell?: string;
}

function piecewiseConstant(profile: number[][], t: number, col: number): number {
  if (!profile || profile.length === 0) return 0;
  if (t < profile[0][0]) return 0;
  let last = profile[0];
  for (const p of profile) {
    if (p[0] > t) break;
    last = p;
  }
  return last[col] || 0;
}

// Build traffic chart data: {sim_t: 0, ue_a_dl: 5000, ue_b_dl: 3000}
export function buildTrafficSeries(
  scenario: RawScenario,
  resolutionSec = 1,
): Array<Record<string, number>> {
  const out: Array<Record<string, number>> = [];
  const totalSec = Math.ceil(scenario.duration_sec);
  for (let t = 0; t <= totalSec; t += resolutionSec) {
    const row: Record<string, number> = { tick: t };
    for (const tf of scenario.traffic || []) {
      const dl = piecewiseConstant(tf.profile, t, 1);
      row[`${tf.ue_name}_dl`] = dl;
    }
    out.push(row);
  }
  return out;
}

// Build position vs time. For chart use scalar — z 軸最直觀(因為 CCO 是南北移動)
export function buildPositionZSeries(
  scenario: RawScenario,
  resolutionSec = 1,
): Array<Record<string, number>> {
  const out: Array<Record<string, number>> = [];
  const totalSec = Math.ceil(scenario.duration_sec);
  for (let t = 0; t <= totalSec; t += resolutionSec) {
    const row: Record<string, number> = { tick: t };
    for (const ue of scenario.ues) {
      const pos = interpolatePos(ue.positions, t);
      row[`${ue.name}_z`] = pos[2];
    }
    out.push(row);
  }
  return out;
}

function interpolatePos(positions: number[][], t: number): [number, number, number] {
  if (!positions || positions.length === 0) return [0, 0, 0];
  if (t <= positions[0][0]) return [positions[0][1], positions[0][2], positions[0][3]];
  if (t >= positions[positions.length - 1][0]) {
    const p = positions[positions.length - 1];
    return [p[1], p[2], p[3]];
  }
  for (let i = 0; i < positions.length - 1; i++) {
    const a = positions[i], b = positions[i + 1];
    if (a[0] <= t && t <= b[0]) {
      const r = b[0] === a[0] ? 0 : (t - a[0]) / (b[0] - a[0]);
      return [a[1] + (b[1] - a[1]) * r, a[2] + (b[2] - a[2]) * r, a[3] + (b[3] - a[3]) * r];
    }
  }
  const last = positions[positions.length - 1];
  return [last[1], last[2], last[3]];
}
