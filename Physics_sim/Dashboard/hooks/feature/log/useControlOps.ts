'use client';

// AG16: 不再自己 poll EventLog — 改 derive 自共享 useE2EventLog.
import { useMemo } from 'react';
import { useE2EventLog, type E2Event } from './useE2EventLog';

export type ControlOutcome = 'ok' | 'sim_error' | 'fail' | 'pending';

export interface ControlOp {
  recv_ts_ms: number;
  ack_ts_ms?: number;
  latency_ms?: number;
  style: number;             // 2 = PRB Quota, 3 = Handover
  action: number;
  sim_action: string;
  ueid?: { amf_ue_ngap_id?: number; ran_ue_ngap_id?: number; gnb_du_ue_f1ap_id?: number };
  outcome: ControlOutcome;
  reason?: string;
}

interface State {
  ops: ControlOp[];          // 最新在前
  loading: boolean;
  error: string;
}

const MAX_KEEP = 50;

/** 配對 e2adapter EventLog 中 control_req_recv ↔ control_ack_sent / control_failure。 */
export function useControlOps(): State {
  const { events, error } = useE2EventLog();

  const ops = useMemo(() => {
    // 從整條 EventLog 重建 control ops (最新在前)
    const buf: ControlOp[] = [];
    for (const e of events) {
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
    return buf.slice(0, MAX_KEEP);
  }, [events]);

  return { ops, loading: events.length === 0 && !error, error };
}
