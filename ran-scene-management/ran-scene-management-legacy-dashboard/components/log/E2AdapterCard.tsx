'use client';

// AG16: 不再自己 poll — 改用共享的 useE2AdapterStatus (跟 useSystemOverview 共用同一條 fetch).
import { useE2AdapterStatus } from '@/hooks/feature/log/useE2AdapterStatus';

// ── color tokens ───────
const C_OK = '#10b981';      // green
const C_WAIT = '#f59e0b';    // amber
const C_FAIL = '#ef4444';    // red
const C_NEUTRAL = '#6b7280'; // gray
const C_BG = '#1f2937';
const C_BORDER = '#374151';

function fmtAge(ms: number): string {
  if (!ms) return '—';
  const ageSec = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (ageSec < 60) return `${ageSec}s ago`;
  if (ageSec < 3600) return `${Math.floor(ageSec / 60)}m ago`;
  return `${Math.floor(ageSec / 3600)}h ago`;
}

interface DotProps { color: string; label?: string; }
function StatusDot({ color, label }: DotProps) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
        background: color, boxShadow: `0 0 6px ${color}80`,
      }} />
      {label && <span style={{ fontSize: 12, color: '#cbd5e1' }}>{label}</span>}
    </span>
  );
}

interface SectionProps { title: string; children: React.ReactNode; statusColor: string; }
function Section({ title, children, statusColor }: SectionProps) {
  return (
    <div style={{
      background: C_BG, border: `1px solid ${C_BORDER}`, borderRadius: 6,
      padding: 12, minWidth: 220, flex: '1 1 220px',
    }}>
      <div style={{
        fontSize: 12, fontWeight: 600, color: '#cbd5e1', marginBottom: 8,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span>{title}</span>
        <StatusDot color={statusColor} />
      </div>
      <div style={{ fontSize: 11, color: '#9ca3af', lineHeight: 1.6, fontFamily: 'monospace' }}>
        {children}
      </div>
    </div>
  );
}

export function E2AdapterCard() {
  const { data: status, error: fetchErr } = useE2AdapterStatus();

  if (!status) {
    return (
      <div style={{
        background: C_BG, border: `1px solid ${C_BORDER}`, borderRadius: 8,
        padding: 16, color: '#9ca3af', fontSize: 13,
      }}>
        E2 Adapter status: {fetchErr ? `unreachable (${fetchErr})` : 'loading...'}
      </div>
    );
  }

  const s = status.sctp_link;
  const e = status.e2_setup;
  const sc = status.schemas;
  const br = status.sim_bridge;
  const cs = status.codec_selftest;

  const sctpColor = !s.enabled ? C_NEUTRAL
    : s.connected ? C_OK
    : s.last_error ? C_FAIL : C_WAIT;
  const setupColor = e.completed ? C_OK : (s.connected ? C_WAIT : C_NEUTRAL);
  const schemaColor = sc.loaded ? C_OK : C_FAIL;
  const bridgeColor = br.last_error ? C_FAIL : (br.last_e2_node_id_at_ms > 0 ? C_OK : C_NEUTRAL);
  const codecColor = (cs.e2_setup_request_ok && cs.kpm_indication_ok && cs.subscription_decode_ok)
    ? C_OK : C_FAIL;

  return (
    <div style={{
      background: '#111827', border: `1px solid ${C_BORDER}`, borderRadius: 10,
      padding: 16, marginTop: 16,
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h3 style={{ margin: 0, color: '#f3f4f6', fontSize: 16 }}>
            E2 Adapter （sim ↔ Near-RT RIC bridge）
          </h3>
          <span style={{ fontSize: 11, color: '#6b7280' }}>
            shared poll 2s
          </span>
        </div>
        <span style={{ fontSize: 11, color: '#6b7280' }}>
          {fetchErr ? <span style={{ color: C_FAIL }}>{fetchErr}</span> : '✓ online'}
        </span>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        {/* ─ SCTP link ─ */}
        <Section title="SCTP Link" statusColor={sctpColor}>
          <div>target : {s.target_host}:{s.target_port}</div>
          <div>state  : {s.enabled ? (s.connected ? 'CONNECTED' : 'DISCONNECTED') : 'DISABLED'}</div>
          <div>sent   : {s.pdu_sent_count} pdu</div>
          <div>recv   : {s.pdu_recv_count} pdu</div>
          {s.last_connect_at_ms > 0 && (
            <div>connect: {fmtAge(s.last_connect_at_ms)}</div>
          )}
          {s.last_error && (
            <div style={{ color: C_FAIL, marginTop: 4, wordBreak: 'break-word' }}>
              {s.last_error}
            </div>
          )}
        </Section>

        {/* ─ E2 Setup ─ */}
        <Section title="E2 Setup" statusColor={setupColor}>
          <div>completed: {e.completed ? 'YES' : 'NO'}</div>
          <div>accepted : [{e.accepted_ran_function_ids.join(', ')}]</div>
          {e.rejected_ran_function_ids.length > 0 && (
            <div style={{ color: C_FAIL }}>rejected : [{e.rejected_ran_function_ids.join(', ')}]</div>
          )}
          {e.completed && e.accepted_ran_function_ids.length > 0 && (
            <div style={{ marginTop: 4, fontSize: 10, color: '#6b7280' }}>
              KPM=2  ·  RC=3
            </div>
          )}
        </Section>

        {/* ─ ASN.1 Schemas ─ */}
        <Section title="ASN.1 Schemas (pycrate)" statusColor={schemaColor}>
          <div>loaded: {sc.loaded ? 'YES' : 'NO'}</div>
          {sc.file_list.map(f => <div key={f}>· {f}</div>)}
          {sc.error && <div style={{ color: C_FAIL, marginTop: 4 }}>{sc.error}</div>}
        </Section>

        {/* ─ Sim Bridge ─ */}
        <Section title="Sim Bridge (HTTP)" statusColor={bridgeColor}>
          <div>cu_url: {br.cu_url}</div>
          {br.last_e2_node_id_at_ms > 0 && (
            <div>last fetch: {fmtAge(br.last_e2_node_id_at_ms)}</div>
          )}
          {br.last_error && (
            <div style={{ color: C_FAIL, marginTop: 4, wordBreak: 'break-word' }}>
              {br.last_error}
            </div>
          )}
        </Section>

        {/* ─ Codec selftest ─ */}
        <Section title="Codec Self-Test" statusColor={codecColor}>
          <div>
            <StatusDot color={cs.e2_setup_request_ok ? C_OK : C_FAIL} /> E2 Setup
            <span style={{ marginLeft: 4, color: '#6b7280' }}>{cs.e2_setup_request_size}B</span>
          </div>
          <div>
            <StatusDot color={cs.kpm_indication_ok ? C_OK : C_FAIL} /> KPM Indication
            <span style={{ marginLeft: 4, color: '#6b7280' }}>{cs.kpm_indication_size}B</span>
          </div>
          <div>
            <StatusDot color={cs.subscription_decode_ok ? C_OK : C_FAIL } /> SUB_REQ decode
          </div>
          {cs.subscription_decoded_metrics.length > 0 && (
            <div style={{ marginTop: 4, fontSize: 10, color: '#6b7280' }}>
              metrics: [{cs.subscription_decoded_metrics.join(', ')}]
            </div>
          )}
          {cs.last_error && (
            <div style={{ color: C_FAIL, marginTop: 4, wordBreak: 'break-word' }}>
              {cs.last_error}
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}
