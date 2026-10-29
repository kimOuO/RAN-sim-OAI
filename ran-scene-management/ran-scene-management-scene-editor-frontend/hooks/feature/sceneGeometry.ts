import type { SceneTree, Ue } from '@/types/registry';

export interface Extent { xMin: number; xMax: number; zMin: number; zMax: number }

/** 場景範圍:建築 / gNB / cell / UE 路徑取外框;什麼都沒有就回原點附近 ±50 m */
export function sceneExtent(tree: SceneTree): Extent {
  const xs: number[] = [], zs: number[] = [];
  const add = (p?: number[] | null) => { if (p && p.length === 3) { xs.push(p[0]); zs.push(p[2]); } };
  tree.buildings.forEach((b) => {
    add(b.position);
    if (b.size?.length === 3) { xs.push(b.position[0] - b.size[0] / 2, b.position[0] + b.size[0] / 2); zs.push(b.position[2] - b.size[2] / 2, b.position[2] + b.size[2] / 2); }
  });
  tree.gnbs.forEach((g) => { add(g.position); g.dus.forEach((d) => d.cells.forEach((c) => add(c.position))); });
  tree.ues.forEach((u) => u.waypoints.forEach((w) => { xs.push(w[1]); zs.push(w[3]); }));
  if (!xs.length) return { xMin: -50, xMax: 50, zMin: -50, zMax: 50 };
  return { xMin: Math.min(...xs), xMax: Math.max(...xs), zMin: Math.min(...zs), zMax: Math.max(...zs) };
}

/** UE 在時間 t(秒)的位置:路徑點線性內插;超出最後一點就停在終點 */
export function uePositionAt(ue: Ue, t: number): [number, number, number] | null {
  const w = ue.waypoints;
  if (!w.length) return null;
  if (t <= w[0][0]) return [w[0][1], w[0][2], w[0][3]];
  for (let i = 1; i < w.length; i++) {
    if (t <= w[i][0]) {
      const a = w[i - 1], b = w[i]; const f = b[0] > a[0] ? (t - a[0]) / (b[0] - a[0]) : 1;
      return [a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f];
    }
  }
  const l = w[w.length - 1]; return [l[1], l[2], l[3]];
}

/** 劇本長度:所有 UE 最後一個路徑點的時間 */
export const pathDuration = (tree: SceneTree) => Math.max(0, ...tree.ues.map((u) => u.waypoints.at(-1)?.[0] ?? 0));

/** UE 在時間 t 是否在場(沒設在場時段 = 全程) */
export const ueActiveAt = (ue: Ue, t: number) => (!ue.presence_restricted && !ue.active_windows.length) || ue.active_windows.some(([a, b]) => t >= a && t < b);
