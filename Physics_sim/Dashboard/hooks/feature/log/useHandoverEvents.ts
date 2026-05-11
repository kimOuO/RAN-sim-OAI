'use client';

import { useMemo } from 'react';
import type { RingEntry } from '@/lib/logStats';

export type HoTrigger = 'A3_TTT' | 'E2_RIC_CONTROL' | 'MANUAL' | 'UNKNOWN';

export interface HoEvent {
  ts_ms: number;
  ue_id: string | null;
  source_cell: string;          // 'unknown' if not derivable
  target_cell: string;          // 'unknown' if not derivable
  trigger: HoTrigger;
  service: 'CU' | 'DU' | 'RU';
  path: string;
}

/**
 * 從 logs ring 偵測 HO 訊號（基於 HTTP path / category）。
 * RingEntry 不含 message string，因此無法解析 source/target/trigger 細節。
 * 後續若加 /CU/Mobility/HandoverEvent/list endpoint 可改用之取得完整資料。
 *
 * 偵測規則：
 * - path 含 "ue_context_modification" → F1 UE Context Modification（HO 結果）
 * - path 含 "Session/SessionController/handover" → 手動 HO (MANUAL)
 * - path 含 "E2/Control/request" 且回應 OK → 可能是 E2_RIC_CONTROL (RC handover)
 */
export function useHandoverEvents(
  logs: RingEntry[],
  windowSec: number = 300,
): HoEvent[] {
  return useMemo(() => {
    if (!logs || logs.length === 0) return [];
    const cutoff = Date.now() - windowSec * 1000;
    const out: HoEvent[] = [];

    for (const e of logs) {
      if (e.ts_ms < cutoff) continue;
      const path = e.path || '';

      // F1 UE Context Modification — CU→DU outbound 表示 HO 已執行
      if (/ue_context_modification/i.test(path)) {
        out.push({
          ts_ms: e.ts_ms,
          ue_id: e.ue_id,
          source_cell: 'unknown',
          target_cell: 'unknown',
          trigger: 'UNKNOWN',  // 無法從 path 區分 A3 vs E2 vs MANUAL
          service: e.service,
          path,
        });
        continue;
      }

      // 手動 HO API
      if (/Session\/SessionController\/handover/i.test(path)) {
        out.push({
          ts_ms: e.ts_ms,
          ue_id: e.ue_id,
          source_cell: 'unknown',
          target_cell: 'unknown',
          trigger: 'MANUAL',
          service: e.service,
          path,
        });
        continue;
      }

      // E2 Control Request (style 3 的話是 HO，但 path 看不出 style)
      if (/E2\/Control\/request/i.test(path) && e.status >= 200 && e.status < 300) {
        out.push({
          ts_ms: e.ts_ms,
          ue_id: e.ue_id,
          source_cell: 'unknown',
          target_cell: 'unknown',
          trigger: 'E2_RIC_CONTROL',
          service: e.service,
          path,
        });
      }
    }
    return out.sort((a, b) => b.ts_ms - a.ts_ms);
  }, [logs, windowSec]);
}
