'use client';

import { useEffect, useState } from 'react';
import { DU_BASE_URL } from '@/config';
import { fetchDriverStatus } from '@/services/api/scenarioMonitor';

export interface PrbQuota {
  cell_id: string;
  min_prb: number;        // 0..100
  max_prb: number;        // 0..100
  dedicated_prb: number;  // 0..100
  cap_factor?: number;
  set_by?: string;        // "scenario" | "E2_RIC_CONTROL"/"xApp" | "MANUAL" | ...
  set_at_ms?: number;
  stale?: boolean;        // true = 無 sim 在跑時的殘留(DU 記憶體沒清,下次 Start Sim 才重置)
}

interface State {
  quotas: PrbQuota[];
  loading: boolean;
  error: string;
  simRunning: boolean;
}

const POLL_MS = 5000;

export function usePrbQuotas(): State {
  const [state, setState] = useState<State>({ quotas: [], loading: true, error: '', simRunning: false });

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const [r, driver] = await Promise.all([
          fetch(`${DU_BASE_URL}/api/v0.1/DU/MAC/MacScheduler/list_prb_quota`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
          }),
          fetchDriverStatus().catch(() => null),
        ]);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (stop) return;
        // 無 sim 在跑 → 目前 DU 裡的 quota 都是上一場留下的殘留(已邏輯清掉,
        // 只是還黏在記憶體,下次 Start Sim 的 clean reset 才實際移除)。
        const simRunning = !!driver?.running;
        const raw = j?.data?.quotas || j?.data || [];
        const quotas: PrbQuota[] = (Array.isArray(raw) ? raw : []).map((q: any) => ({
          cell_id: q.cell_id,
          min_prb: q.min_prb ?? 0,
          max_prb: q.max_prb ?? 100,
          dedicated_prb: q.dedicated_prb ?? q.dedicated ?? 0,
          cap_factor: q.cap_factor,
          set_by: q.set_by,
          set_at_ms: q.set_at_ms,
          stale: !simRunning,
        }));
        setState({ quotas, loading: false, error: '', simRunning });
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
