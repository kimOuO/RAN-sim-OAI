import type { SceneTree3d, SceneTreeLite, Ue3d } from '@/types/telemetry';

/** 歸檔裡的 cell 帶 run 標籤(e05:gnb1_c0);場景樹是原名 */
export const stripTag = (cell: string) => cell.replace(/^[0-9a-f]{3}:/i, '');

/** UE 在時間 t(秒)的位置:路徑點線性內插,超過終點停在終點;不在場回 null */
export function uePositionAt(ue: Ue3d, t: number): [number, number, number] | null {
  if ((ue.presence_restricted || ue.active_windows.length) && !ue.active_windows.some(([a, b]) => t >= a && t < b)) return null;
  const w = ue.waypoints; if (!w.length) return null;
  if (t <= w[0][0]) return [w[0][1], w[0][2], w[0][3]];
  for (let i = 1; i < w.length; i++) if (t <= w[i][0]) {
    const a = w[i - 1], b = w[i], f = b[0] > a[0] ? (t - a[0]) / (b[0] - a[0]) : 1;
    return [a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f];
  }
  const l = w[w.length - 1]; return [l[1], l[2], l[3]];
}

/** 每個 cell 名稱 → 世界座標(cell 有獨立位置用自己的,否則用 gNB 的) */
export function cellPositions(tree: SceneTree3d): Record<string, [number, number, number]> {
  const m: Record<string, [number, number, number]> = {};
  for (const g of tree.gnbs) for (const d of g.dus) for (const c of d.cells) { const p = c.position ?? g.position; m[c.name] = [p[0] ?? 0, p[1] ?? 0, p[2] ?? 0]; }
  return m;
}

/** 場景範圍 → 中心、尺度(標記大小與鏡頭距離用) */
export function sceneView(tree: SceneTree3d, geo?: { x: number[]; z: number[] } | null) {
  const xs: number[] = [], zs: number[] = [];
  tree.gnbs.forEach((g) => { xs.push(g.position[0]); zs.push(g.position[2]); });
  tree.ues.forEach((u) => u.waypoints.forEach((w) => { xs.push(w[1]); zs.push(w[3]); }));
  tree.buildings.forEach((b) => { xs.push(b.position[0]); zs.push(b.position[2]); });
  // 2026-09-21:掃描模型的尺寸不在 tree 裡,不併進來的話大場景開啟時鏡頭只對著中間一小塊
  if (geo) { xs.push(...geo.x); zs.push(...geo.z); }
  if (!xs.length) return { center: [0, 0, 0] as [number, number, number], extent: 80, scale: 1 };
  const extent = Math.max(10, Math.max(...xs) - Math.min(...xs), Math.max(...zs) - Math.min(...zs));
  return { center: [(Math.min(...xs) + Math.max(...xs)) / 2, 0, (Math.min(...zs) + Math.max(...zs)) / 2] as [number, number, number], extent, scale: Math.max(0.4, Math.min(6, extent / 120)) };
}

/** SINR → 0..1(-10 dB 以下最暗、30 dB 以上最亮) */
export const sinrLevel = (s: number | null | undefined) => (s == null || s <= -99 ? 0 : Math.max(0, Math.min(1, (s + 10) / 40)));

export interface CellOwner { gnb: string; du: string; pci: number }
/** cell 名稱 → 所屬 gNB / DU(UE 卡片、站台標籤、DU cell 表用)。DU 沒名字時用 du0、du1… */
export function cellOwners(tree: SceneTree3d | SceneTreeLite | null | undefined): Record<string, CellOwner> {
  const m: Record<string, CellOwner> = {};
  for (const g of tree?.gnbs ?? []) g.dus.forEach((d, i) => d.cells.forEach((c) => { m[c.name] = { gnb: g.name, du: d.name ?? `du${i}`, pci: c.pci }; }));
  return m;
}

/** gNB / DU / cell 數量(標題列摘要用) */
export function topologyCounts(tree: SceneTree3d | SceneTreeLite | null | undefined) {
  const gnbs = tree?.gnbs ?? [];
  const dus = gnbs.flatMap((g) => g.dus);
  return { gnb: gnbs.length, du: dus.length, cell: dus.reduce((n, d) => n + d.cells.length, 0) };
}

/** UE 是否有服務 cell(沒有 cell 或 SINR 是哨兵值 = 未附著) */
export const ueAttached = (s: { cell?: string; sinr_db?: number; attached?: boolean } | undefined) => !!(s && (s.attached ?? (!!s.cell && s.sinr_db != null && s.sinr_db > -99)));
