'use client';

import { useEffect, useRef, useState } from 'react';
import { E2_ADAPTER_BASE_URL } from '@/config';

interface Event {
  seq: number;
  ts_ms: number;
  kind: string;
  [k: string]: any;
}

const POLL_MS = 2000;
const MAX_DISPLAY = 100;

const KIND_META: Record<string, { color: string; icon: string; label: string }> = {
  sctp_connect:           { color: '#10b981', icon: '🔗', label: 'SCTP CONNECT' },
  sctp_disconnect:        { color: '#ef4444', icon: '✂️', label: 'SCTP DISCONNECT' },
  e2_setup_outcome:       { color: '#3b82f6', icon: '🤝', label: 'E2 SETUP' },
  sub_req_recv:           { color: '#a855f7', icon: '📥', label: 'SUB_REQ RECV' },
  sub_resp_sent:          { color: '#a855f7', icon: '📤', label: 'SUB_RESP SENT' },
  indication_sent:        { color: '#06b6d4', icon: '📡', label: 'INDICATION SENT' },
  indication_encode_fail: { color: '#ef4444', icon: '⚠️', label: 'ENCODE FAIL' },
  pdu_recv:               { color: '#94a3b8', icon: '📥', label: 'PDU RECV' },
  control_req_recv:       { color: '#fb923c', icon: '🎛️', label: 'RC CTRL RECV' },
  control_ack_sent:       { color: '#fb923c', icon: '✅', label: 'RC CTRL ACK' },
  control_failure:        { color: '#ef4444', icon: '❌', label: 'RC CTRL FAIL' },
};

function fmtTs(ms: number): string {
  const d = new Date(ms);
  return d.toLocaleTimeString('en-GB', { hour12: false }) + '.' + String(ms % 1000).padStart(3, '0');
}

function describeEvent(e: Event): string {
  switch (e.kind) {
    case 'sctp_connect':
      return `${e.host}:${e.port}`;
    case 'sctp_disconnect':
      return e.reason || 'closed';
    case 'e2_setup_outcome':
      return `${e.outcome} accepted=${JSON.stringify(e.accepted)} rejected=${JSON.stringify(e.rejected)}${e.reason ? ' · ' + e.reason : ''}`;
    case 'sub_req_recv':
      return `sub_id=${e.sub_id} ranFunc=${e.ran_func_id} period=${e.period_ms}ms metrics=${(e.metrics || []).length}`;
    case 'sub_resp_sent':
      return `sub_id=${e.sub_id} admitted=${JSON.stringify(e.admitted_action_ids)} ${e.pdu_size}B`;
    case 'indication_sent':
      return `sub=${e.sub_id} sn=${e.sn} ${e.pdu_size}B ueCount=${e.ue_count}`;
    case 'indication_encode_fail':
      return `sub=${e.sub_id} ${e.error || ''}`;
    case 'pdu_recv':
      return `proc=${e.proc_code} ${e.type_name} ${e.size}B`;
    case 'control_req_recv': {
      const u = e.ueid || {};
      return `style=${e.style} action=${e.action} → sim ${e.sim_action} amf_ue=${u.amf_ue_ngap_id || '—'}`;
    }
    case 'control_ack_sent':
      return `style=${e.style}/${e.action} sim ${e.sim_action} ${e.pdu_size}B outcome=${e.outcome}`;
    case 'control_failure':
      return `style=${e.style}/${e.action} ${e.reason}`;
    default:
      return JSON.stringify(e);
  }
}

export function E2EventTimeline() {
  const [events, setEvents] = useState<Event[]>([]);
  const [error, setError] = useState<string>('');
  const lastSeqRef = useRef<number>(0);
  const seenSeqsRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    let cancelled = false;
    const pollOnce = async () => {
      try {
        const resp = await fetch(
          `${E2_ADAPTER_BASE_URL}/api/v0.1/E2Adapter/EventLog/EventLogReader/read`,
          { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ since_seq: lastSeqRef.current, limit: 200 }) },
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();
        if (cancelled) return;
        const fresh: Event[] = json.data?.entries || [];
        const uniq = fresh.filter(f => {
          if (seenSeqsRef.current.has(f.seq)) return false;
          seenSeqsRef.current.add(f.seq);
          return true;
        });
        if (uniq.length > 0) {
          lastSeqRef.current = Math.max(lastSeqRef.current, ...uniq.map(u => u.seq));
          setEvents(prev => [...uniq, ...prev].slice(0, MAX_DISPLAY));
        }
        setError('');
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message || String(e));
      }
    };
    pollOnce();
    const id = setInterval(pollOnce, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return (
    <div style={{
      background: '#111827', border: '1px solid #374151', borderRadius: 10,
      padding: 16, marginTop: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    marginBottom: 12 }}>
        <h3 style={{ margin: 0, color: '#f3f4f6', fontSize: 16 }}>
          📋 E2 Plane Event Timeline
        </h3>
        <span style={{ fontSize: 11, color: '#6b7280' }}>
          {events.length} events · poll {POLL_MS}ms · max {MAX_DISPLAY} shown
          {error && <span style={{ color: '#ef4444', marginLeft: 8 }}>· err: {error}</span>}
        </span>
      </div>

      {events.length === 0 ? (
        <div style={{ color: '#6b7280', fontSize: 12, fontFamily: 'monospace' }}>
          (no events yet — adapter 啟動 + 對通 RIC 後事件會出現在這裡)
        </div>
      ) : (
        <div style={{ maxHeight: 360, overflowY: 'auto', fontFamily: 'monospace', fontSize: 11 }}>
          {events.map(e => {
            const meta = KIND_META[e.kind] || { color: '#94a3b8', icon: '·', label: e.kind };
            return (
              <div key={e.seq} style={{
                display: 'grid',
                gridTemplateColumns: '120px 22px 130px 1fr',
                gap: 8, padding: '4px 8px',
                borderLeft: `3px solid ${meta.color}`,
                borderBottom: '1px solid #1f2937',
                background: '#0f172a',
              }}>
                <span style={{ color: '#94a3b8' }}>{fmtTs(e.ts_ms)}</span>
                <span>{meta.icon}</span>
                <span style={{ color: meta.color, fontWeight: 600 }}>{meta.label}</span>
                <span style={{ color: '#cbd5e1', wordBreak: 'break-all' }}>
                  {describeEvent(e)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
