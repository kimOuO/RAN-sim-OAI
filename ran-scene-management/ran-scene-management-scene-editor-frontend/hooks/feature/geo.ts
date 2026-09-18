import type { LatLon } from '@/types/geometry';

/** 緯度 lat 處每度的公尺數(與後端 osm_to_mitsuba._meters_per_degree 同式) */
export function metersPerDegree(lat: number): { mLat: number; mLon: number } {
  const phi = (lat * Math.PI) / 180;
  return {
    mLat: 111132.92 - 559.82 * Math.cos(2 * phi) + 1.175 * Math.cos(4 * phi) - 0.0023 * Math.cos(6 * phi),
    mLon: 111412.84 * Math.cos(phi) - 93.5 * Math.cos(3 * phi) + 0.118 * Math.cos(5 * phi),
  };
}

/** 以 (lat, lon) 為中心、半邊長 halfM 公尺的正方形 */
export function squareAround(lat: number, lon: number, halfM: number): LatLon[] {
  const { mLat, mLon } = metersPerDegree(lat);
  const dLat = halfM / mLat, dLon = halfM / mLon;
  return [[lat + dLat, lon - dLon], [lat + dLat, lon + dLon], [lat - dLat, lon + dLon], [lat - dLat, lon - dLon]];
}

/** 多邊形面積(m²):投影到中心點的平面後用鞋帶公式;範圍 ≤ 數公里時誤差可忽略 */
export function polygonAreaM2(poly: LatLon[]): number {
  if (poly.length < 3) return 0;
  const lat0 = poly.reduce((s, p) => s + p[0], 0) / poly.length;
  const { mLat, mLon } = metersPerDegree(lat0);
  let a = 0;
  for (let i = 0; i < poly.length; i++) {
    const [y1, x1] = poly[i], [y2, x2] = poly[(i + 1) % poly.length];
    a += x1 * mLon * (y2 * mLat) - x2 * mLon * (y1 * mLat);
  }
  return Math.abs(a) / 2;
}

/** 地標外框的半邊長(公尺),夾在 [min, max] 之間 —— 搜尋結果的框常常只有一棟樓或整個行政區 */
export function landmarkHalfSize(bbox: { min_lat: number; min_lon: number; max_lat: number; max_lon: number }, min = 100, max = 300): number {
  const { mLat, mLon } = metersPerDegree((bbox.min_lat + bbox.max_lat) / 2);
  const half = Math.max(((bbox.max_lat - bbox.min_lat) * mLat) / 2, ((bbox.max_lon - bbox.min_lon) * mLon) / 2);
  return Math.min(max, Math.max(min, half));
}

/** 兩點中點(多邊形邊上的「插入頂點」把手用) */
export const midpoint = (a: LatLon, b: LatLon): LatLon => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
