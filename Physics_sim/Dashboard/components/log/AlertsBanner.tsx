'use client';

import { useMemo } from 'react';
import { useSystemOverview } from '@/hooks/feature/log/useSystemOverview';
import type { RingEntry } from '@/lib/logStats';

type Severity = 'critical' | 'warning' | 'info';

interface Alert {
  id: string;
  severity: Severity;
  title: string;
  detail: string;
}

const C_CARD = '#111827';
const C_BORDER = '#374151';
const C_TEXT = '#cbd5e1';
const C_MUTED = '#6b7280';
const C_BY_SEV: Record<Severity, string> = {
  critical: '#ef4444',
  warning: '#f59e0b',
  info: '#3b82f6',
};

interface Props {
  logs: RingEntry[];
}

const SEV_ORDER: Severity[] = ['critical', 'warning', 'info'];
const P95_THRESHOLD_MS = 200;

export function AlertsBanner({ logs }: Props) {
  const sys = useSystemOverview();
  const alerts = useMemo(() => deriveAlerts(sys, logs), [sys, logs]);

  if (alerts.length === 0) {
    return (
      <div style={{
        background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8,
        padding: '10px 14px', marginBottom: 16,
        fontSize: 12, color: C_MUTED,
      }}>
        ✓ No active alerts.
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {alerts.map(a => (
        <div key={a.id} style={{
          background: C_CARD,
          borderLeft: `3px solid ${C_BY_SEV[a.severity]}`,
          border: `1px solid ${C_BORDER}`,
          borderRadius: 6, padding: '8px 12px',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <span style={{
            fontSize: 9, fontWeight: 700, letterSpacing: 0.6,
            color: C_BY_SEV[a.severity], minWidth: 60,
          }}>
            {a.severity.toUpperCase()}
          </span>
          <span style={{ fontSize: 13, fontWeight: 600, color: C_TEXT, minWidth: 200 }}>
            {a.title}
          </span>
          <span style={{ fontSize: 12, color: C_MUTED, fontFamily: 'monospace' }}>
            {a.detail}
          </span>
        </div>
      ))}
    </div>
  );
}


function deriveAlerts(sys: ReturnType<typeof useSystemOverview>, logs: RingEntry[]): Alert[] {
  const out: Alert[] = [];

  // 1) E2 silent peer — sent/recv ratio 異常高
  if (sys.e2.connected && sys.e2.sent > 100) {
    const ratio = sys.e2.sent / Math.max(sys.e2.recv, 1);
    if (ratio > 100) {
      out.push({
        id: 'e2_silent',
        severity: 'critical',
        title: 'RIC silent peer',
        detail: `Adapter sent ${sys.e2.sent} pdu but only received ${sys.e2.recv}. RIC may be dropping indications.`,
      });
    }
  }

  // 2) E2 setup not completed
  if (sys.e2.connected && !sys.e2.setup_ok) {
    out.push({
      id: 'e2_setup_pending',
      severity: 'warning',
      title: 'E2 Setup incomplete',
      detail: 'SCTP up but E2 Setup Response not yet accepted.',
    });
  }
  if (!sys.e2.connected) {
    out.push({
      id: 'e2_disconnected',
      severity: 'critical',
      title: 'E2 link DOWN',
      detail: 'Adapter not connected to RIC e2term.',
    });
  }

  // 3) Tick stopped
  if (sys.tick && !sys.tick.is_running) {
    out.push({
      id: 'tick_stopped',
      severity: 'critical',
      title: 'DU tick driver stopped',
      detail: 'Simulation halted — no scheduling occurring.',
    });
  }

  // 4) PMI=0 systematic note (always-on, info-level)
  out.push({
    id: 'pmi_zero',
    severity: 'info',
    title: 'PMI=0 systematic',
    detail: 'DU passes pmi=0 / layers=1 to RU; SINR/CQI biased low (~3-8 dB) — known mock limitation.',
  });

  // 5) F1AP UE Context Modification p95 latency
  const recent = logs.filter(e =>
    e.ts_ms > Date.now() - 30_000 &&
    /ue_context_modification/i.test(e.path),
  );
  if (recent.length >= 5) {
    const sorted = [...recent].map(e => e.duration_ms).sort((a, b) => a - b);
    const p95 = sorted[Math.floor(sorted.length * 0.95)] ?? sorted[sorted.length - 1];
    if (p95 > P95_THRESHOLD_MS) {
      out.push({
        id: 'ue_ctx_mod_p95',
        severity: 'warning',
        title: 'F1AP UE_Context_Mod p95 high',
        detail: `Last 30s p95 = ${p95}ms (>${P95_THRESHOLD_MS}ms threshold), n=${recent.length}.`,
      });
    }
  }

  // sort by severity
  return out.sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity));
}
