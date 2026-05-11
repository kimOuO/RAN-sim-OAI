'use client';

import { useEffect, useRef, useState } from 'react';
import { E2_ADAPTER_BASE_URL } from '@/config';

export type ControlOutcome = 'ok' | 'sim_error' | 'fail' | 'pending';

export interface ControlOp {
  recv_ts_ms: number;
  ack_ts_ms?: number;
  latency_ms?: number;
  style: number;             // 2 = PRB Quota, 3 = Handover
  action: number;
  sim_action: string;        // "control_slice_level_prb_quota" | "control_handover" | ...
  ueid?: { amf_ue_ngap_id?: number; ran_ue_ngap_id?: number; gnb_du_ue_f1ap_id?: number };
  outcome: ControlOutcome;
  reason?: string;
}

interface State {
  ops: ControlOp[];        // 最新在前
  loading: boolean;
  error: string;
}

const POLL_MS = 2000;
const MAX_FETCH = 200;
const MAX_KEEP = 50;

/** 配對 e2adapter EventLog 中 control_req_recv ↔ control_ack_sent / control_failure。 */
export function useControlOps(): State {
  const [state, setState] = useState<State>({ ops: [], loading: true, error: '' });
  const lastSeqRef = useRef<number>(0);
  const seenRef = useRef<Set<number>>(new Set());
  const pendingRef = useRef<ControlOp[]>([]);

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const r = await fetch(
          `${E2_ADAPTER_BASE_URL}/api/v0.1/E2Adapter/EventLog/EventLogReader/read`,
          {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ since_seq: lastSeqRef.current, limit: MAX_FETCH }),
          },
        );
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (stop) return;
        const fresh: any[] = j?.data?.entries || [];
        const novel = fresh.filter(e => {
          if (seenRef.current.has(e.seq)) return false;
          seenRef.current.add(e.seq);
          return true;
        });
        if (novel.length > 0) {
          lastSeqRef.current = Math.max(lastSeqRef.current, ...novel.map((u: any) => u.seq));
        }

        const buf = pendingRef.current;
        for (const e of novel) {
          if (e.kind === 'control_req_recv') {
            buf.unshift({
              recv_ts_ms: e.ts_ms,
              style: e.style ?? 0,
              action: e.action ?? 0,
              sim_action: e.sim_action || '?',
              ueid: e.ueid,
              outcome: 'pending',
            });
          } else if (e.kind === 'control_ack_sent') {
            const target = buf.find(op =>
              op.outcome === 'pending' &&
              op.style === e.style && op.action === e.action,
            );
            if (target) {
              target.ack_ts_ms = e.ts_ms;
              target.latency_ms = e.ts_ms - target.recv_ts_ms;
              target.outcome = (e.outcome === 'ok' ? 'ok' : 'sim_error') as ControlOutcome;
            }
          } else if (e.kind === 'control_failure') {
            const target = buf.find(op =>
              op.outcome === 'pending' &&
              op.style === e.style && op.action === e.action,
            );
            if (target) {
              target.ack_ts_ms = e.ts_ms;
              target.latency_ms = e.ts_ms - target.recv_ts_ms;
              target.outcome = 'fail';
              target.reason = e.reason;
            } else {
              // 沒找到對應 req — 直接記一筆獨立 fail
              buf.unshift({
                recv_ts_ms: e.ts_ms,
                style: e.style ?? 0,
                action: e.action ?? 0,
                sim_action: e.sim_action || '?',
                outcome: 'fail',
                reason: e.reason,
              });
            }
          }
        }

        pendingRef.current = buf.slice(0, MAX_KEEP);
        setState({ ops: [...pendingRef.current], loading: false, error: '' });
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
