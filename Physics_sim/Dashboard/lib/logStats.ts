/**
 * RAN log 視覺化共用 utilities。所有計算都在前端從 logs[] 即時推算。
 */

export interface RingEntry {
  seq: number;
  ts_ms: number;
  service: 'CU' | 'DU' | 'RU';
  method: string;
  path: string;
  status: number;
  duration_ms: number;
  category: string;
  ue_id: string | null;
  // 2026-05-16 P4.3: PDU payload (request + response JSON) — 給 RanLogTable 展開檢視
  request_body?: string;
  response_body?: string;
}

export type CategoryGroup =
  | 'F1AP'
  | 'FAPI'
  | 'NGAP_E1AP'
  | 'E2'
  | 'Tick_RLC'
  | 'Other';

export const CATEGORY_GROUPS: CategoryGroup[] = [
  'F1AP',
  'FAPI',
  'NGAP_E1AP',
  'E2',
  'Tick_RLC',
  'Other',
];

export const GROUP_LABEL: Record<CategoryGroup, string> = {
  F1AP: 'F1AP',
  FAPI: 'FAPI',
  NGAP_E1AP: 'NGAP/E1AP',
  E2: 'E2',
  Tick_RLC: 'Tick/RLC',
  Other: 'Other',
};

export function groupOf(category: string): CategoryGroup {
  if (category.startsWith('F1AP_') || category === 'F1Setup' || category === 'F1Setup_Resp') return 'F1AP';
  if (category.startsWith('FAPI_')) return 'FAPI';
  if (category.startsWith('NGAP_') || category.startsWith('E1AP_')) return 'NGAP_E1AP';
  if (category.startsWith('E2_') || category === 'HandoverCmd') return 'E2';
  if (category.startsWith('Tick_') || category === 'RLC_SDU') return 'Tick_RLC';
  return 'Other';
}

/**
 * Stable color per category — 只要 category 名稱固定就回相同顏色。
 * 取自 tailwind palette；有區別也耐看。
 */
const CATEGORY_PALETTE = [
  '#3b82f6', // blue
  '#10b981', // emerald
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#84cc16', // lime
  '#f97316', // orange
  '#a855f7', // purple
  '#14b8a6', // teal
  '#6366f1', // indigo
];

const _categoryColorCache = new Map<string, string>();
export function colorForCategory(cat: string): string {
  const cached = _categoryColorCache.get(cat);
  if (cached) return cached;
  let h = 0;
  for (let i = 0; i < cat.length; i++) h = (h * 31 + cat.charCodeAt(i)) >>> 0;
  const c = CATEGORY_PALETTE[h % CATEGORY_PALETTE.length];
  _categoryColorCache.set(cat, c);
  return c;
}

export function percentile(values: number[], p: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length));
  return sorted[idx];
}

export interface SummaryStats {
  throughputPerSec: number;
  prevThroughputPerSec: number; // 上一個 5s 視窗，用來算箭頭
  errorCount: number;
  totalCount: number;
  p95DurationMs: number;
  maxDurationMs: number;
  activeCategoryCount: number;
  totalCategoryCount: number;
  activePerService: Record<'CU' | 'DU' | 'RU', number>;
}

export function summaryStats(
  logs: RingEntry[],
  now: number,
  windowMs: number = 30_000,
): SummaryStats {
  const windowCutoff = now - windowMs;
  const recent5s = now - 5_000;
  const prev5s = now - 10_000;

  let recentCount = 0;
  let prevCount = 0;
  let errorCount = 0;
  const durations: number[] = [];
  let maxDur = 0;
  const catsByService: Record<'CU' | 'DU' | 'RU', Set<string>> = {
    CU: new Set(),
    DU: new Set(),
    RU: new Set(),
  };
  const allCats = new Set<string>();

  for (const e of logs) {
    if (e.ts_ms < windowCutoff) continue;
    if (e.ts_ms >= recent5s) recentCount++;
    else if (e.ts_ms >= prev5s) prevCount++;
    if (e.status >= 400) errorCount++;
    durations.push(e.duration_ms);
    if (e.duration_ms > maxDur) maxDur = e.duration_ms;
    catsByService[e.service]?.add(e.category);
    allCats.add(e.category);
  }

  return {
    throughputPerSec: recentCount / 5,
    prevThroughputPerSec: prevCount / 5,
    errorCount,
    totalCount: durations.length,
    p95DurationMs: percentile(durations, 95),
    maxDurationMs: maxDur,
    activeCategoryCount: allCats.size,
    totalCategoryCount: 26, // CU+DU+RU union (見 ran_message_log.py)
    activePerService: {
      CU: catsByService.CU.size,
      DU: catsByService.DU.size,
      RU: catsByService.RU.size,
    },
  };
}

/**
 * 把 logs 切成 time bucket，輸出可直接餵 Recharts AreaChart。
 *
 * @returns array of { bucketIdx: number, label: string } & {[cat]: count}，最舊→最新
 */
export interface TimelineBucket {
  bucketIdx: number;
  label: string;
  ts: number;
  [category: string]: number | string;
}

export function bucketizeTimeline(
  logs: RingEntry[],
  now: number,
  topCategories: string[],
  windowMs: number = 60_000,
  bucketMs: number = 2_000,
): TimelineBucket[] {
  const numBuckets = Math.ceil(windowMs / bucketMs);
  const start = now - windowMs;
  const buckets: TimelineBucket[] = [];
  const topSet = new Set(topCategories);

  for (let i = 0; i < numBuckets; i++) {
    const bStart = start + i * bucketMs;
    const secsAgo = Math.round((now - bStart - bucketMs) / 1000);
    const bucket: TimelineBucket = {
      bucketIdx: i,
      label: secsAgo <= 0 ? 'now' : `-${secsAgo}s`,
      ts: bStart,
    };
    for (const c of topCategories) bucket[c] = 0;
    bucket.other = 0;
    buckets.push(bucket);
  }

  for (const e of logs) {
    if (e.ts_ms < start) continue;
    const idx = Math.min(numBuckets - 1, Math.max(0, Math.floor((e.ts_ms - start) / bucketMs)));
    const key = topSet.has(e.category) ? e.category : 'other';
    buckets[idx][key] = ((buckets[idx][key] as number) || 0) + 1;
  }

  return buckets;
}

export interface CategoryStat {
  category: string;
  count: number;
  errorCount: number;
  p50: number;
  p95: number;
  maxMs: number;
}

export function topCategoriesWithStats(
  logs: RingEntry[],
  now: number,
  windowMs: number = 30_000,
  topN: number = 8,
): CategoryStat[] {
  const cutoff = now - windowMs;
  const byCat: Record<string, { durations: number[]; errors: number }> = {};
  for (const e of logs) {
    if (e.ts_ms < cutoff) continue;
    const slot = (byCat[e.category] ||= { durations: [], errors: 0 });
    slot.durations.push(e.duration_ms);
    if (e.status >= 400) slot.errors++;
  }
  return Object.entries(byCat)
    .map(([cat, s]) => ({
      category: cat,
      count: s.durations.length,
      errorCount: s.errors,
      p50: percentile(s.durations, 50),
      p95: percentile(s.durations, 95),
      maxMs: s.durations.reduce((m, x) => (x > m ? x : m), 0),
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, topN);
}

export interface HeatmapCell {
  service: 'CU' | 'DU' | 'RU';
  group: CategoryGroup;
  count: number;
}

export function serviceGroupHeatmap(
  logs: RingEntry[],
  now: number,
  windowMs: number = 30_000,
): { cells: HeatmapCell[]; maxCount: number } {
  const cutoff = now - windowMs;
  const services: Array<'CU' | 'DU' | 'RU'> = ['CU', 'DU', 'RU'];
  const counts: Record<string, number> = {};
  for (const s of services) for (const g of CATEGORY_GROUPS) counts[`${s}|${g}`] = 0;
  for (const e of logs) {
    if (e.ts_ms < cutoff) continue;
    counts[`${e.service}|${groupOf(e.category)}`]++;
  }
  const cells: HeatmapCell[] = [];
  let maxCount = 0;
  for (const s of services) {
    for (const g of CATEGORY_GROUPS) {
      const c = counts[`${s}|${g}`];
      cells.push({ service: s, group: g, count: c });
      if (c > maxCount) maxCount = c;
    }
  }
  return { cells, maxCount };
}

/**
 * Filter logs by user-selected criteria. 圖表+表格共用同一個 derived array。
 */
export interface LogFilters {
  service: 'all' | 'CU' | 'DU' | 'RU';
  group: 'all' | CategoryGroup;
  status: 'all' | '2xx' | '4xx' | '5xx';
  hideTick: boolean;
}

export function applyFilters(logs: RingEntry[], f: LogFilters): RingEntry[] {
  return logs.filter((e) => {
    if (f.service !== 'all' && e.service !== f.service) return false;
    if (f.group !== 'all' && groupOf(e.category) !== f.group) return false;
    if (f.status === '2xx' && !(e.status >= 200 && e.status < 300)) return false;
    if (f.status === '4xx' && !(e.status >= 400 && e.status < 500)) return false;
    if (f.status === '5xx' && e.status < 500) return false;
    if (f.hideTick && e.category.startsWith('Tick_')) return false;
    return true;
  });
}
