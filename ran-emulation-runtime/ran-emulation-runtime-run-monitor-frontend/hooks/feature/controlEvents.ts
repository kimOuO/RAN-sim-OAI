import type { ControlEvent } from '@/types/telemetry';

export type ControlOrigin = 'ric' | 'ric_apply' | 'son' | 'other';
const LABELS: Record<ControlOrigin, string> = { ric: 'RIC / xApp 指令', ric_apply: 'RIC 指令落地', son: 'RAN 自主 SON', other: '其他' };

/** 依歸檔來源分類；RAN 自主行為不計入 RIC / xApp 下發指令。 */
export const controlOrigin = (source: string): ControlOrigin => source === 'son/ric_apply' ? 'ric_apply' : source.startsWith('ric/') ? 'ric' : source.startsWith('son/') ? 'son' : 'other';
export const controlOriginLabel = (source: string) => LABELS[controlOrigin(source)];
export const ctrlOk = (outcome: string) => ['ACK', 'success', 'applied'].includes(outcome);

export function countControlOrigins(events: Pick<ControlEvent, 'source'>[]) {
  const counts: Record<ControlOrigin, number> = { ric: 0, ric_apply: 0, son: 0, other: 0 };
  for (const event of events) counts[controlOrigin(event.source)]++;
  return counts;
}
