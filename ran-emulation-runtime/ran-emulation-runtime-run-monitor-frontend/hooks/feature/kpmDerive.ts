import { SERIES, type UeMetricKey } from '@/config';
import type { KpmSample, Pt, SceneTreeLite, Series, UeKpm } from '@/types/telemetry';

/** cell → 固定色:依名稱排序後對應 slot,不因篩選改色(dataviz「色跟實體走」) */
export function cellColorMap(cells: string[]): Record<string, string> {
  return Object.fromEntries([...cells].sort().map((c, i) => [c, SERIES[Math.min(i, SERIES.length - 1)]]));
}
export function allCells(samples: KpmSample[]): string[] {
  const s = new Set<string>(); for (const w of samples) { for (const c of Object.keys(w.per_cell)) s.add(c); for (const u of Object.values(w.per_ue)) if (u.serving_cell) s.add(u.serving_cell); }
  return [...s].sort();
}
export function allUes(samples: KpmSample[]): string[] { const s = new Set<string>(); for (const w of samples) for (const u of Object.keys(w.per_ue)) s.add(u); return [...s].sort(); }
/** x 軸用視窗序(1 s/窗),避免舊資料 sim_time 不單調 */
export const xOf = (i: number) => i;
export function cellSeries(samples: KpmSample[], cells: string[], color: Record<string, string>, pick: (w: KpmSample, c: string) => number | null): Series[] {
  return cells.map((c) => ({ key: c, label: c, color: color[c], points: samples.map((w, i) => ({ x: xOf(i), y: pick(w, c) })) }));
}
export const prbDl = (w: KpmSample, c: string) => w.per_cell[c]?.prb_pct_dl ?? null;
export const prbUl = (w: KpmSample, c: string) => w.per_cell[c]?.prb_pct_ul ?? null;
export const thpDlByCell = (w: KpmSample, c: string) => { let s = 0, n = 0; for (const u of Object.values(w.per_ue)) if (u.serving_cell === c) { s += u.throughput_dl_mbps ?? 0; n++; } return n ? s : (w.per_cell[c] ? 0 : null); };
export const ueCountByCell = (w: KpmSample, c: string) => { let n = 0; for (const u of Object.values(w.per_ue)) if (u.serving_cell === c) n++; return w.per_cell[c] || n ? n : null; };
export const meanSinrByCell = (w: KpmSample, c: string) => { let s = 0, n = 0; for (const u of Object.values(w.per_ue)) if (u.serving_cell === c) { s += u.sinr_db; n++; } return n ? s / n : null; };
export function ueSeries(samples: KpmSample[], ue: string, key: UeMetricKey): Pt[] { return samples.map((w, i) => ({ x: xOf(i), y: (w.per_ue[ue]?.[key] as number | null | undefined) ?? null })); }
export function ueServingStrip(samples: KpmSample[], ue: string): { x: number; cell: string }[] { return samples.map((w, i) => ({ x: xOf(i), cell: w.per_ue[ue]?.serving_cell ?? '' })); }
export function latestUes(w: KpmSample | null): [string, UeKpm][] { return w ? Object.entries(w.per_ue).sort(([a], [b]) => a.localeCompare(b)) : []; }
export function mean(xs: number[]): number | null { return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null; }
export function histogram(values: number[], min: number, max: number, bins: number): { x0: number; x1: number; n: number }[] {
  const w = (max - min) / bins; const out = Array.from({ length: bins }, (_, i) => ({ x0: min + i * w, x1: min + (i + 1) * w, n: 0 }));
  for (const v of values) { const i = Math.min(bins - 1, Math.max(0, Math.floor((v - min) / w))); out[i].n++; }
  return out;
}
/** 事件依 sim-time 分桶(每 bucketSec 秒),用來畫 HO / RLF 直條 */
export function bucketEvents(atMs: number[], bucketSec: number, totalSec: number): { x0: number; n: number }[] {
  const nb = Math.max(1, Math.ceil(totalSec / bucketSec)); const out = Array.from({ length: nb }, (_, i) => ({ x0: i * bucketSec, n: 0 }));
  for (const t of atMs) { const i = Math.min(nb - 1, Math.max(0, Math.floor(t / 1000 / bucketSec))); out[i].n++; }
  return out;
}
export const fmtSimTime = (sec: number) => { const s = Math.max(0, Math.round(sec)); const m = Math.floor(s / 60); const h = Math.floor(m / 60); return h ? `${h}h${String(m % 60).padStart(2, '0')}m` : `${m}:${String(s % 60).padStart(2, '0')}`; };

export const thpUlByCell = (w: KpmSample, c: string) => { let s = 0, n = 0; for (const u of Object.values(w.per_ue)) if (u.serving_cell === c) { s += u.throughput_ul_mbps ?? 0; n++; } return n ? s : (w.per_cell[c] ? 0 : null); };
export const meanRlcDelayByCell = (w: KpmSample, c: string) => { let s = 0, n = 0; for (const u of Object.values(w.per_ue)) if (u.serving_cell === c) { s += u.rlc_sdu_delay_dl_ms ?? 0; n++; } return n ? s / n : null; };
export const meanMcsByCell = (w: KpmSample, c: string) => { let s = 0, n = 0; for (const u of Object.values(w.per_ue)) if (u.serving_cell === c) { s += u.mcs_dl ?? 0; n++; } return n ? s / n : null; };
/** gNB → cells:用場景樹的 cell 名稱對 KPM 的 cell_id;對不到的歸「其他」 */
export function groupCellsByGnb(cells: string[], tree: SceneTreeLite | null): { gnb: string; cells: string[] }[] {
  const owner = new Map<string, string>();
  for (const g of tree?.gnbs ?? []) for (const du of g.dus) for (const c of du.cells) owner.set(c.name, g.name);
  const m = new Map<string, string[]>();
  // KPM 的 cell_id 帶 run 標籤(e01:src),場景樹的名字沒有 → 剝掉再比對
  const bare = (c: string) => (c.includes(':') ? c.split(':')[1] : c);
  for (const c of cells) { const g = owner.get(bare(c)) ?? '其他'; (m.get(g) ?? m.set(g, []).get(g)!).push(c); }
  return [...m.entries()].sort(([a], [b]) => (a === '其他' ? 1 : b === '其他' ? -1 : a.localeCompare(b))).map(([gnb, cs]) => ({ gnb, cells: cs }));
}
