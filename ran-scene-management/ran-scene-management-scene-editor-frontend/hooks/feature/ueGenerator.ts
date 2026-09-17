import type { UeGenParams } from '@/config';

/** 可重現的亂數(mulberry32):同一個 seed 永遠產生同一組 UE */
export function seededRandom(seed: number) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

export interface PlannedUe { name: string; speed: number; waypoints: [number, number, number, number][]; schedule: number[][] }

/** 依參數產生 UE:隨機走點(走過去 + 隨機停留)、每 trafficStep 秒換一次隨機上下行流量 [t, dl_kbps, ul_kbps] */
export function planUes(p: UeGenParams): PlannedUe[] {
  const rnd = seededRandom(p.seed);
  const u = (a: number, b: number) => a + (b - a) * rnd();
  const out: PlannedUe[] = [];
  for (let i = 0; i < p.count; i++) {
    const speed = Math.max(0.01, u(p.speedMin, p.speedMax));
    let t = 0; let x = u(p.xMin, p.xMax), z = u(p.zMin, p.zMax);
    const waypoints: [number, number, number, number][] = [[0, round(x), p.height, round(z)]];
    while (t < p.duration) {
      const nx = u(p.xMin, p.xMax), nz = u(p.zMin, p.zMax);
      t = Math.min(p.duration, t + Math.hypot(nx - x, nz - z) / speed + u(0, p.dwellMax));
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
