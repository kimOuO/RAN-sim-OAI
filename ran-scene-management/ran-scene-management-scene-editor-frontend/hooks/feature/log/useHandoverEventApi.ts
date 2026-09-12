'use client';

import { useState, useEffect, useRef } from 'react';
import { CU_BASE_URL } from '@/config';
import type { HoEvent, HoTrigger } from './useHandoverEvents';

const VALID_TRIGGERS = new Set<string>(['A3_TTT', 'E2_RIC_CONTROL', 'MANUAL']);

function toTrigger(raw: unknown): HoTrigger {
  return typeof raw === 'string' && VALID_TRIGGERS.has(raw)
    ? (raw as HoTrigger)
    : 'UNKNOWN';
}

export function useHandoverEventApi(windowSec: number = 300): HoEvent[] {
  const [events, setEvents] = useState<HoEvent[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    stoppedRef.current = false;

    const poll = async () => {
      try {
        const res = await fetch(
          `${CU_BASE_URL}/api/v0.1/CU/Mobility/HandoverEvent/list`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ window_sec: windowSec, limit: 200 }),
          },
        );
        if (res.ok) {
          const json = await res.json();
          const raw: any[] = json?.data?.events ?? [];
          setEvents(
            raw.map(e => ({
              ts_ms: Number(e.ts_ms) || 0,
              ue_id: e.ue_id ?? null,
              source_cell: e.source_cell || 'unknown',
              target_cell: e.target_cell || 'unknown',
              trigger: toTrigger(e.trigger),
              service: 'CU' as const,
              path: '',
            })),
          );
        }
      } catch {
        // network error — keep stale data
      }
      if (!stoppedRef.current) {
        timerRef.current = setTimeout(poll, 3000);
      }
    };

    poll();
    return () => {
      stoppedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [windowSec]);

  return events;
}
