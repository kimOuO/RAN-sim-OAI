import type { UeGenParams } from '@/config';
import type { HeightMap } from '@/services/api/scenes';

/** 由高度圖做成「這一點能不能站人」的判斷:表面高度超過 threshold 視為建築。
 *  沒有高度圖(例如純建築盒場景)就一律可走 —— 那種場景的建築本來就在 extent 裡。 */
export function walkableFromHeightMap(hm: HeightMap | null, threshold = 1.0) {
  if (!hm) return () => true;
  const [x0] = hm.x_range, [z0] = hm.z_range, st = hm.step_m;
  return (x: number, z: number) => {
    const c = Math.round((x - x0) / st), r = Math.round((z - z0) / st);
    if (r < 0 || c < 0 || r >= hm.n_rows || c >= hm.n_cols) return false;   // 場景外不要放
    const h = hm.height_m[r]?.[c];
    return h == null ? true : h <= threshold;   // 沒打到東西(空洞)就當可走
  };
}

/** 可重現的亂數(mulberry32):同一個 seed 永遠產生同一組 UE */
export function seededRandom(seed: number) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

export interface PlannedUe { name: string; speed: number; waypoints: [number, number, number, number][]; schedule: number[][] }

/** 依參數產生 UE:隨機走點(走過去 + 隨機停留)、每 trafficStep 秒換一次隨機上下行流量 [t, dl_kbps, ul_kbps]。
 *  walkable:哪些點能站人(由高度圖來,避開建築)。起點、每個轉折點與沿途取樣都會檢查;
 *  找不到可走的點就沿用上一點(UE 原地停留),不會硬塞進建築裡。 */
export function planUes(p: UeGenParams, walkable: (x: number, z: number) => boolean = () => true): PlannedUe[] {
  const rnd = seededRandom(p.seed);
  const u = (a: number, b: number) => a + (b - a) * rnd();
  const out: PlannedUe[] = [];
  for (let i = 0; i < p.count; i++) {
    const speed = Math.max(0.01, u(p.speedMin, p.speedMax));
    const pick = (): [number, number] => {
      for (let k = 0; k < 60; k++) { const cx = u(p.xMin, p.xMax), cz = u(p.zMin, p.zMax); if (walkable(cx, cz)) return [cx, cz]; }
      return [NaN, NaN];   // 這個範圍幾乎都是建築 —— 交給呼叫端沿用上一點
    };
    // 沿線每 2 m 取樣一次,整段都要可走(不然 UE 會穿牆)
    const clear = (ax: number, az: number, bx: number, bz: number) => {
      const n = Math.max(1, Math.ceil(Math.hypot(bx - ax, bz - az) / 2));
      for (let k = 1; k <= n; k++) if (!walkable(ax + ((bx - ax) * k) / n, az + ((bz - az) * k) / n)) return false;
      return true;
    };
    let t = 0; let [x, z] = pick();
    if (Number.isNaN(x)) { x = (p.xMin + p.xMax) / 2; z = (p.zMin + p.zMax) / 2; }
    const waypoints: [number, number, number, number][] = [[0, round(x), p.height, round(z)]];
    while (t < p.duration) {
      let nx = x, nz = z;
      for (let k = 0; k < 40; k++) { const [cx, cz] = pick(); if (!Number.isNaN(cx) && clear(x, z, cx, cz)) { nx = cx; nz = cz; break; } }
      t = Math.min(p.duration, t + Math.hypot(nx - x, nz - z) / speed + u(0, p.dwellMax) + (nx === x && nz === z ? p.trafficStep : 0));
      x = nx; z = nz; waypoints.push([round(t), round(x), p.height, round(z)]);
    }
    const schedule: number[][] = [];
    for (let s = 0; s < p.duration; s += Math.max(1, p.trafficStep)) {
      const dl = rnd() < p.heavyRatio ? u(p.heavyMin, p.heavyMax) : u(p.dlMin, p.dlMax);
      schedule.push([s, round(dl, 1), round(u(p.ulMin, p.ulMax), 1)]);
    }
    out.push({ name: `${p.namePrefix}${String(i).padStart(2, '0')}`, speed: round(speed), waypoints, schedule });
  }
  return out;
}

const round = (v: number, d = 3) => Math.round(v * 10 ** d) / 10 ** d;
