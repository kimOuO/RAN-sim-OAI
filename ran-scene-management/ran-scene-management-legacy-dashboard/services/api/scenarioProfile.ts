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
  // 劇本實際的 gNB / cell 幾何（地圖與 Cell card 用真實位置，不再 hardcode）
  gnbs?: Array<{
    name: string;
    position?: number[];
    frequency_ghz?: number;
    bandwidth_mhz?: number;
    power_dbm?: number;
    cells?: Array<{
      pci?: number;
      cell_id: string;
      azimuth_deg?: number;
      position?: number[];
    }>;
  }>;
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
  totalSecOverride?: number,
): Array<Record<string, number>> {
  const out: Array<Record<string, number>> = [];
  const totalSec = Math.ceil(totalSecOverride ?? scenario.duration_sec);
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

/** 這個劇本的 UE 主要沿哪個軸移動。原本預覽圖寫死畫 z(CCO 是南北移動),
 *  但 ANR 十二題的 UE 是東西向走 x、z 恆定 —— 畫出來是一條直線,
 *  看起來就像「這個劇本沒有 UE 位置」。改成自動挑變化大的那軸。 */
export function dominantAxis(scenario: RawScenario): 'x' | 'z' {
  let rx = 0, rz = 0;
  for (const u of scenario.ues || []) {
    const p = normalizePositions(u.positions, scenario.duration_sec);
    if (!p.length) continue;
    let xmin = p[0][1], xmax = p[0][1], zmin = p[0][3], zmax = p[0][3];
    for (const q of p) {
      if (q[1] < xmin) xmin = q[1]; else if (q[1] > xmax) xmax = q[1];
      if (q[3] < zmin) zmin = q[3]; else if (q[3] > zmax) zmax = q[3];
    }
    rx = Math.max(rx, xmax - xmin); rz = Math.max(rz, zmax - zmin);
  }
  return rx > rz ? 'x' : 'z';
}

// Build position vs time. axis 預設 z(CCO 南北移動);ANR 等東西向劇本傳 'x'。
export function buildPositionZSeries(
  scenario: RawScenario,
  resolutionSec = 1,
  totalSecOverride?: number,
  axis: 'x' | 'z' = 'z',
): Array<Record<string, number>> {
  const out: Array<Record<string, number>> = [];
  const totalSec = Math.ceil(totalSecOverride ?? scenario.duration_sec);
  const ai = axis === 'x' ? 0 : 2;
  // 先 normalize 一次,不要在 t 迴圈裡重建陣列
  const norm = (scenario.ues || []).map(u => ({
    name: u.name, pos: normalizePositions(u.positions, scenario.duration_sec),
  }));
  for (let t = 0; t <= totalSec; t += resolutionSec) {
    const row: Record<string, number> = { tick: t };
    for (const ue of norm) row[`${ue.name}_${axis}`] = interpolatePos(ue.pos, t)[ai];
    out.push(row);
  }
  return out;
}

function interpolatePos(positions: number[][], t: number): [number, number, number] {
  if (!positions || positions.length === 0) return [0, 0, 0];
  if (t <= positions[0][0]) return [positions[0][1], positions[0][2], positions[0][3]];
  const last = positions[positions.length - 1];
  if (t >= last[0]) return [last[1], last[2], last[3]];
  // 二分搜尋找 t 所在區間。原本是線性掃 —— 長劇本(2880 點 × 每秒取樣 86400 格)
  // 會變成上億次比較,是 /scenarios 卡頓的主因。
  let lo = 0, hi = positions.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (positions[mid][0] <= t) lo = mid; else hi = mid;
  }
  const a = positions[lo], b = positions[hi];
  const r = b[0] === a[0] ? 0 : (t - a[0]) / (b[0] - a[0]);
  return [a[1] + (b[1] - a[1]) * r, a[2] + (b[2] - a[2]) * r, a[3] + (b[3] - a[3]) * r];
}

/** 預覽圖用的取樣間隔:不論劇本多長都只取約 MAX_PREVIEW_POINTS 點。
 *  86400 秒的劇本每秒一格 = 86400 個點,圖上根本畫不出來,純浪費。 */
export const MAX_PREVIEW_POINTS = 600;
export function previewResolutionSec(durationSec: number): number {
  return Math.max(1, Math.ceil((durationSec || 1) / MAX_PREVIEW_POINTS));
}

/** 劇本 positions 有兩種格式:`[t,x,y,z]`(自帶時戳)與 `[x,y,z]`(沒時戳)。
 *  後者 sim 端由 scenario_loader._normalize_positions 把時戳平均攤在 duration 上,
 *  前端必須做同一件事,否則會把 x 當成時間、把 undefined 當成 z —— 症狀是
 *  卡片「看不到 UE 位置」。 */
export function normalizePositions(
  positions: number[][], durationSec: number,
): number[][] {
  if (!positions || positions.length === 0) return [];
  if (positions[0].length >= 4) return positions;
  const n = positions.length;
  if (n === 1) return [[0, positions[0][0], positions[0][1], positions[0][2]]];
  const step = (durationSec || 1) / (n - 1);
  return positions.map((p, i) => [i * step, p[0], p[1], p[2]]);
}

/** 預覽該畫多長:UE 軌跡實際跨度。
 *  劇本 duration 常是 86400s 但軌跡只有幾百秒 —— 照 duration 畫的話
 *  99% 的圖是軌跡結束後的一條直線,又大又看不出東西。 */
export function previewSpanSec(scenario: RawScenario): number {
  let span = 0;
  for (const u of scenario.ues || []) {
    const p = normalizePositions(u.positions, scenario.duration_sec);
    if (p.length) span = Math.max(span, p[p.length - 1][0] - p[0][0]);
  }
  return span > 0 ? span : Math.ceil(scenario.duration_sec);
}
