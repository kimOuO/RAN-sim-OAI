'use client';

// AG16: 不再自己 poll — 改 derive 自共享 useE2EventLog.
import { useEffect, useRef, useState } from 'react';
import { useE2EventLog, type E2Event as Event } from '@/hooks/feature/log/useE2EventLog';

const MAX_DISPLAY = 80;

// Lanes: 0=xApp/RIC  1=Adapter  2=Sim CU
type Lane = 0 | 1 | 2;
interface ArrowSpec {
  from: Lane; to: Lane; color: string; label: string; sub?: string;
}

function arrowFor(e: Event): ArrowSpec | null {
  switch (e.kind) {
    case 'sctp_connect':
      return { from: 1, to: 0, color: '#10b981', label: 'SCTP CONNECT',
               sub: `→ ${e.host}:${e.port}` };
    case 'sctp_disconnect':
      return { from: 0, to: 1, color: '#ef4444', label: 'SCTP DISCONNECT',
               sub: e.reason || '' };
    case 'e2_setup_outcome':
      if (e.outcome === 'successfulOutcome') {
        return { from: 0, to: 1, color: '#3b82f6', label: 'E2 Setup Resp ✓',
                 sub: `accepted=[${(e.accepted || []).join(',')}]` };
      }
      return { from: 0, to: 1, color: '#ef4444', label: 'E2 Setup Resp ✗',
               sub: e.reason || '' };
    case 'sub_req_recv':
      return { from: 0, to: 1, color: '#a855f7', label: 'RIC_SUB_REQ',
               sub: `sub=${(e.sub_id || '').slice(0, 14)}… ${(e.metrics || []).length} metrics @${e.period_ms}ms` };
    case 'sub_resp_sent':
      return { from: 1, to: 0, color: '#a855f7', label: 'RIC_SUB_RESP',
               sub: `admitted=[${(e.admitted_action_ids || []).join(',')}] ${e.pdu_size}B` };
    case 'indication_sent':
      return { from: 1, to: 0, color: '#06b6d4', label: 'RIC_INDICATION',
               sub: `sn=${e.sn} ${e.pdu_size}B ${e.ue_count}UE` };
    case 'control_req_recv': {
      const u = e.ueid || {};
      return { from: 0, to: 1, color: '#fb923c', label: `RIC_CTRL_REQ s${e.style}/a${e.action}`,
               sub: `→ ${e.sim_action} amf_ue=${u.amf_ue_ngap_id || '—'}` };
    }
    case 'control_ack_sent':
      return { from: 1, to: 0, color: '#fb923c', label: `RIC_CTRL_ACK s${e.style}/a${e.action}`,
               sub: `${e.sim_action} ${e.pdu_size}B ${e.outcome}` };
    case 'control_failure':
      return { from: 1, to: 0, color: '#ef4444', label: 'CTRL FAIL',
               sub: `s${e.style}/a${e.action} ${e.reason}` };
    default:
      return null;
  }
}

function fmtTs(ms: number): string {
  const d = new Date(ms);
  return d.toLocaleTimeString('en-GB', { hour12: false }) +
    '.' + String(ms % 1000).padStart(3, '0');
}

export function E2SequenceDiagram() {
  const { events: allEvents, error } = useE2EventLog();
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState<Set<string>>(new Set([
    'sctp_connect', 'sctp_disconnect', 'e2_setup_outcome',
    'sub_req_recv', 'sub_resp_sent', 'indication_sent',
    'control_req_recv', 'control_ack_sent', 'control_failure',
  ]));
  const scrollRef = useRef<HTMLDivElement>(null);

  // 共享 ring 最多 500,本 component 只顯示最後 MAX_DISPLAY 筆.
  const events: Event[] = allEvents.slice(-MAX_DISPLAY);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight, behavior: 'smooth',
      });
    }
  }, [events.length, autoScroll]);

  const allKinds = [
    'sctp_connect', 'sctp_disconnect', 'e2_setup_outcome',
    'sub_req_recv', 'sub_resp_sent', 'indication_sent',
    'control_req_recv', 'control_ack_sent', 'control_failure',
  ];

  function toggle(k: string) {
    const n = new Set(filter);
    if (n.has(k)) n.delete(k); else n.add(k);
    setFilter(n);
  }

  const filteredEvents = events.filter(e => filter.has(e.kind));

  const counts: Record<string, number> = {};
  events.forEach(e => { counts[e.kind] = (counts[e.kind] || 0) + 1; });

  const LANE_WIDTH = 280;     // px per lane
  const LANE_LABELS = ['xApp / Near-RT RIC', 'E2 Adapter', 'Sim CU/DU/RU'];
  const LANE_COLORS = ['#a855f7', '#06b6d4', '#10b981'];

  return (
    <div style={{
      background: '#0b1220', border: '1px solid #374151', borderRadius: 10,
      padding: 16, marginTop: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    marginBottom: 12 }}>
        <h3 style={{ margin: 0, color: '#f3f4f6', fontSize: 16 }}>
          🪜 E2 Plane Sequence Diagram (ladder view)
        </h3>
        <span style={{ fontSize: 11, color: '#6b7280' }}>
          {events.length} events · shared poll 2s
          {error && <span style={{ color: '#ef4444', marginLeft: 8 }}>· err: {error}</span>}
        </span>
      </div>

      {/* Filter chips + auto-scroll toggle */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12,
                    alignItems: 'center' }}>
        {allKinds.map(k => {
          const active = filter.has(k);
          const meta = arrowFor({ kind: k, seq: 0, ts_ms: 0 } as any);
          const color = meta?.color || '#6b7280';
          const c = counts[k] || 0;
          return (
            <button key={k} onClick={() => toggle(k)} style={{
              padding: '3px 8px', fontSize: 10, borderRadius: 4,
              background: active ? color : 'transparent',
              color: active ? '#0b1220' : color,
              border: `1px solid ${color}`,
              cursor: 'pointer', fontWeight: 600, fontFamily: 'monospace',
            }}>
              {k} · {c}
            </button>
          );
        })}
        <label style={{ marginLeft: 'auto', fontSize: 11, color: '#cbd5e1', cursor: 'pointer' }}>
          <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)}
                 style={{ marginRight: 4 }} />
          auto-scroll
        </label>
      </div>

      {/* Lane headers */}
      <div style={{
        display: 'grid', gridTemplateColumns: `90px ${LANE_WIDTH}px ${LANE_WIDTH}px ${LANE_WIDTH}px`,
        gap: 0, borderBottom: '2px solid #374151', paddingBottom: 8, marginBottom: 8,
      }}>
        <div style={{ fontSize: 10, color: '#6b7280' }}>time</div>
        {LANE_LABELS.map((label, i) => (
          <div key={i} style={{
            textAlign: 'center', color: LANE_COLORS[i], fontWeight: 700, fontSize: 12,
            borderTop: `3px solid ${LANE_COLORS[i]}`, paddingTop: 4,
          }}>
            {label}
          </div>
        ))}
      </div>

      {/* Sequence rows */}
      <div ref={scrollRef} style={{
        position: 'relative', maxHeight: 460, overflowY: 'auto',
        fontFamily: 'monospace', fontSize: 11,
      }}>
        {/* Vertical lifeline lines */}
        <div style={{
          position: 'absolute', top: 0, bottom: 0, left: 0, right: 0,
          pointerEvents: 'none',
          backgroundImage: [
            `linear-gradient(to right, transparent calc(90px + ${LANE_WIDTH/2}px - 1px),
               #374151 calc(90px + ${LANE_WIDTH/2}px - 1px),
               #374151 calc(90px + ${LANE_WIDTH/2}px),
               transparent calc(90px + ${LANE_WIDTH/2}px))`,
            `linear-gradient(to right, transparent calc(90px + ${LANE_WIDTH + LANE_WIDTH/2}px - 1px),
               #374151 calc(90px + ${LANE_WIDTH + LANE_WIDTH/2}px - 1px),
               #374151 calc(90px + ${LANE_WIDTH + LANE_WIDTH/2}px),
               transparent calc(90px + ${LANE_WIDTH + LANE_WIDTH/2}px))`,
            `linear-gradient(to right, transparent calc(90px + ${2*LANE_WIDTH + LANE_WIDTH/2}px - 1px),
               #374151 calc(90px + ${2*LANE_WIDTH + LANE_WIDTH/2}px - 1px),
               #374151 calc(90px + ${2*LANE_WIDTH + LANE_WIDTH/2}px),
               transparent calc(90px + ${2*LANE_WIDTH + LANE_WIDTH/2}px))`,
          ].join(','),
        }} />

        {filteredEvents.length === 0 ? (
          <div style={{ color: '#6b7280', padding: 16 }}>
            (no events yet — adapter 連通 + xApp 訂閱後事件會出現)
          </div>
        ) : (
          filteredEvents.map(e => {
            const arrow = arrowFor(e);
            if (!arrow) return null;
            return (
              <SequenceRow key={e.seq} ts={e.ts_ms} arrow={arrow} laneWidth={LANE_WIDTH} />
            );
          })
        )}
      </div>
    </div>
  );
}

interface RowProps {
  ts: number; arrow: ArrowSpec; laneWidth: number;
}
function SequenceRow({ ts, arrow, laneWidth }: RowProps) {
  // calculate arrow geometry
  const fromCenter = 90 + arrow.from * laneWidth + laneWidth / 2;
  const toCenter   = 90 + arrow.to   * laneWidth + laneWidth / 2;
  const left  = Math.min(fromCenter, toCenter);
  const right = Math.max(fromCenter, toCenter);
  const width = right - left;
  const direction = arrow.to > arrow.from ? 'right' : 'left';

  return (
    <div style={{ position: 'relative', height: 38, marginBottom: 2 }}>
      {/* Time column */}
      <div style={{ position: 'absolute', left: 0, top: 4, width: 90,
                    color: '#94a3b8', fontSize: 10 }}>
        {fmtTs(ts)}
      </div>
      {/* Arrow line */}
      <div style={{
        position: 'absolute', top: 18, left, width,
        height: 2, background: arrow.color,
      }} />
      {/* Arrowhead */}
      {direction === 'right' ? (
        <div style={{
          position: 'absolute', top: 14, left: right - 6,
          width: 0, height: 0,
          borderTop: '5px solid transparent',
          borderBottom: '5px solid transparent',
          borderLeft: `6px solid ${arrow.color}`,
        }} />
      ) : (
        <div style={{
          position: 'absolute', top: 14, left,
          width: 0, height: 0,
          borderTop: '5px solid transparent',
          borderBottom: '5px solid transparent',
          borderRight: `6px solid ${arrow.color}`,
        }} />
      )}
      {/* Label centered above arrow */}
      <div style={{
        position: 'absolute', top: 0, left: left + 6,
        width: width - 12,
        textAlign: 'center', color: arrow.color, fontWeight: 600, fontSize: 11,
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}>
        {arrow.label}
      </div>
      {/* Sub-label below */}
      {arrow.sub && (
        <div style={{
          position: 'absolute', top: 22, left: left + 6,
          width: width - 12,
          textAlign: 'center', color: '#94a3b8', fontSize: 10,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {arrow.sub}
        </div>
      )}
    </div>
  );
}
