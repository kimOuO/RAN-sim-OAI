'use client';

// 共享 E2 EventLog (since_seq 增量) — useControlOps + E2SequenceDiagram 之前各 poll 一次, 重複。
// 比一般 makePoller 多兩件事: (a) since_seq 增量; (b) ring buffer (累積結果不能蓋掉).
import { useEffect, useState } from 'react';
import { E2_ADAPTER_BASE_URL } from '@/config';

export interface E2Event {
  seq: number;
  ts_ms: number;
  kind: string;
  [k: string]: any;
}

const POLL_MS = 2000;
const RING_SIZE = 500;

let events: E2Event[] = [];
let lastSeq = 0;
let error = '';
let timer: ReturnType<typeof setInterval> | null = null;
let listeners: ((e: E2Event[]) => void)[] = [];
let busy = false;

async function tick() {
  if (busy) return;
  busy = true;
  try {
    const r = await fetch(
      `${E2_ADAPTER_BASE_URL}/api/v0.1/E2Adapter/EventLog/EventLogReader/read`,
      {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ since_seq: lastSeq, limit: 200 }),
      },
    );
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    const fresh: E2Event[] = j?.data?.entries || [];
    if (fresh.length > 0) {
      lastSeq = Math.max(lastSeq, ...fresh.map(e => e.seq));
      events = [...events, ...fresh].slice(-RING_SIZE);
      listeners.forEach(fn => fn(events));
    }
    error = '';
  } catch (e: any) {
    error = e?.message || String(e);
  } finally {
    busy = false;
  }
}

export function useE2EventLog(): { events: E2Event[]; error: string } {
  const [snap, setSnap] = useState<E2Event[]>(events);
  useEffect(() => {
    setSnap(events);
    listeners.push(setSnap);
    if (listeners.length === 1) {
      tick();
      timer = setInterval(tick, POLL_MS);
    }
    return () => {
      listeners = listeners.filter(l => l !== setSnap);
      if (listeners.length === 0 && timer) {
        clearInterval(timer); timer = null;
      }
    };
  }, []);
  return { events: snap, error };
}
