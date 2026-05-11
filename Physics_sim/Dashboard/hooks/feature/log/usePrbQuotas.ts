'use client';

import { useEffect, useState } from 'react';
import { DU_BASE_URL } from '@/config';

export interface PrbQuota {
  cell_id: string;
  min_prb: number;        // 0..100
  max_prb: number;        // 0..100
  dedicated_prb: number;  // 0..100
  cap_factor?: number;
  set_by?: string;        // "MANUAL" | "E2_RIC_CONTROL" | ...
  set_at_ms?: number;
}

interface State {
  quotas: PrbQuota[];
  loading: boolean;
  error: string;
}

const POLL_MS = 5000;

export function usePrbQuotas(): State {
  const [state, setState] = useState<State>({ quotas: [], loading: true, error: '' });

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const r = await fetch(`${DU_BASE_URL}/api/v0.1/DU/MAC/MacScheduler/list_prb_quota`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (stop) return;
        const raw = j?.data?.quotas || j?.data || [];
        const quotas: PrbQuota[] = (Array.isArray(raw) ? raw : []).map((q: any) => ({
          cell_id: q.cell_id,
          min_prb: q.min_prb ?? 0,
          max_prb: q.max_prb ?? 100,
          dedicated_prb: q.dedicated_prb ?? q.dedicated ?? 0,
          cap_factor: q.cap_factor,
          set_by: q.set_by,
          set_at_ms: q.set_at_ms,
        }));
        setState({ quotas, loading: false, error: '' });
      } catch (e: any) {
        if (stop) return;
        setState(s => ({ ...s, loading: false, error: e?.message || String(e) }));
      }
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { stop = true; clearInterval(id); };
  }, []);

  return state;
}
