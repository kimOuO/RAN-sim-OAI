'use client';

import { useMemo } from 'react';
import { useControlOps, type ControlOp } from '@/hooks/feature/log/useControlOps';
import { usePrbQuotas, type PrbQuota } from '@/hooks/feature/log/usePrbQuotas';
import { useCellStatus } from '@/hooks/feature/log/useCellStatus';

const C_CARD = '#111827';
const C_BORDER = '#374151';
const C_TEXT = '#cbd5e1';
const C_MUTED = '#6b7280';
const C_OK = '#10b981';
const C_WARN = '#f59e0b';
const C_FAIL = '#ef4444';

const SIM_ACTION_LABEL: Record<string, { label: string; color: string }> = {
  control_handover: { label: 'HO', color: '#a855f7' },
  control_slice_level_prb_quota: { label: 'PRB quota', color: '#06b6d4' },
};

function intentMode(simAction: string, style: number): string {
  if (style === 2) return 'IM/ES';
  if (style === 3) return 'CCO/ES';
  return '?';
}

export function IntentControlAudit() {
  const { ops } = useControlOps();
  const { quotas } = usePrbQuotas();
  const { aggregates } = useCellStatus();

  const cellByName = useMemo(() => {
    const m = new Map<string, typeof aggregates[number]>();
    for (const a of aggregates) m.set(a.cell.cell_id, a);
    return m;
  }, [aggregates]);

  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{
        margin: 0, color: C_TEXT, fontSize: 14, fontWeight: 600,
        marginBottom: 12,
      }}>
        🎯 Intent-Driven Control Audit （xApp 指令端到端）
      </h2>

      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 12,
      }}>
        {/* Active PRB Quotas */}
        <div style={{
          background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8,
          padding: 12,
        }}>
          <div style={{ fontSize: 12, color: C_TEXT, fontWeight: 600, marginBottom: 8 }}>
            Active PRB Quotas
          </div>
          {quotas.length === 0 ? (
            <div style={{ color: C_MUTED, fontSize: 11 }}>
              (no non-default quotas — 全 cell default)
            </div>
          ) : (
            <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C_BORDER}`, color: C_MUTED }}>
                  <th style={{ textAlign: 'left', padding: 4 }}>cell</th>
                  <th style={{ textAlign: 'right', padding: 4 }}>min/max/ded</th>
                  <th style={{ textAlign: 'left', padding: 4 }}>set_by</th>
                </tr>
              </thead>
              <tbody>
                {quotas.map(q => (
                  <PrbRow key={q.cell_id} q={q} />
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Recent xApp Ops */}
        <div style={{
          background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8,
          padding: 12, maxHeight: 280, overflowY: 'auto',
        }}>
          <div style={{ fontSize: 12, color: C_TEXT, fontWeight: 600, marginBottom: 8 }}>
            Recent xApp Control Ops
          </div>
          {ops.length === 0 ? (
            <div style={{ color: C_MUTED, fontSize: 11 }}>
              (no RIC_CONTROL_REQ in event log — xApp 未下指令或 RIC 未轉發)
            </div>
          ) : (
            <table style={{ width: '100%', fontSize: 10, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C_BORDER}`, color: C_MUTED }}>
                  <th style={{ textAlign: 'left', padding: 4 }}>t</th>
                  <th style={{ textAlign: 'left', padding: 4 }}>style/action</th>
                  <th style={{ textAlign: 'left', padding: 4 }}>action</th>
                  <th style={{ textAlign: 'left', padding: 4 }}>UE</th>
                  <th style={{ textAlign: 'right', padding: 4 }}>latency</th>
                  <th style={{ textAlign: 'left', padding: 4 }}>outcome</th>
                </tr>
              </thead>
              <tbody>
                {ops.map((op, i) => (
                  <OpRow key={i} op={op} />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Effect Tracker */}
      <div style={{
        background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8,
        padding: 12, marginTop: 12,
      }}>
        <div style={{ fontSize: 12, color: C_TEXT, fontWeight: 600, marginBottom: 8 }}>
          Effect Tracker （受 quota 影響的 cell 即時 KPI）
        </div>
        {quotas.length === 0 ? (
          <div style={{ color: C_MUTED, fontSize: 11 }}>
            (no quotas applied — nothing to track)
          </div>
        ) : (
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
            gap: 8,
          }}>
            {quotas.map(q => {
              const agg = cellByName.get(q.cell_id);
              return (
                <div key={q.cell_id} style={{
                  background: '#0b1220', borderRadius: 6, padding: 10,
                  border: `1px solid ${C_BORDER}`,
                }}>
                  <div style={{
                    fontSize: 11, fontWeight: 600, color: C_TEXT, fontFamily: 'monospace',
                    marginBottom: 4,
                  }}>
                    {q.cell_id}
                  </div>
                  <div style={{ fontSize: 10, color: C_MUTED, marginBottom: 6 }}>
                    quota max={q.max_prb}% (was 100%)
                  </div>
                  {agg ? (
                    <div style={{
                      display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6,
                      fontSize: 11, fontFamily: 'monospace',
                    }}>
                      <div>
                        <span style={{ color: C_MUTED }}>PRB </span>
                        <span style={{ color: C_TEXT }}>{agg.prbUsedPct.toFixed(1)}%</span>
                      </div>
                      <div>
                        <span style={{ color: C_MUTED }}>SINR </span>
                        <span style={{ color: C_TEXT }}>
                          {agg.avgSinrDb !== null ? `${agg.avgSinrDb.toFixed(1)}` : '—'}
                        </span>
                      </div>
                      <div>
                        <span style={{ color: C_MUTED }}>UE </span>
                        <span style={{ color: C_TEXT }}>{agg.ueCount}</span>
                      </div>
                      <div>
                        <span style={{ color: C_MUTED }}>retx </span>
                        <span style={{ color: C_TEXT }}>{agg.retxRatePct.toFixed(1)}%</span>
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: 10, color: C_MUTED }}>
                      cell not in MAC snapshot
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}


function PrbRow({ q }: { q: PrbQuota }) {
  const isE2 = (q.set_by || '').toUpperCase().includes('E2');
  const setByColor = isE2 ? '#a855f7' : (q.set_by ? C_WARN : C_MUTED);
  return (
    <tr style={{ borderBottom: '1px solid #1f2937' }}>
      <td style={{ padding: 4, color: C_TEXT, fontFamily: 'monospace' }}>
        {q.cell_id}
      </td>
      <td style={{ padding: 4, color: C_TEXT, textAlign: 'right', fontFamily: 'monospace' }}>
        {q.min_prb}/{q.max_prb}/{q.dedicated_prb}
      </td>
      <td style={{ padding: 4, color: setByColor, fontWeight: 600 }}>
        {q.set_by || '—'}
      </td>
    </tr>
  );
}

function OpRow({ op }: { op: ControlOp }) {
  const meta = SIM_ACTION_LABEL[op.sim_action] || { label: op.sim_action, color: C_TEXT };
  const oc = op.outcome === 'ok' ? C_OK
    : op.outcome === 'pending' ? C_WARN
    : C_FAIL;
  return (
    <tr style={{ borderBottom: '1px solid #1f2937' }}>
      <td style={{ padding: 4, color: C_MUTED, fontFamily: 'monospace' }}>
        {new Date(op.recv_ts_ms).toLocaleTimeString('en-GB', { hour12: false })}
      </td>
      <td style={{ padding: 4, color: C_TEXT, fontFamily: 'monospace' }}>
        s{op.style}/a{op.action}
        <span style={{ color: C_MUTED, marginLeft: 4 }}>
          {intentMode(op.sim_action, op.style)}
        </span>
      </td>
      <td style={{ padding: 4, color: meta.color, fontWeight: 600 }}>
        {meta.label}
      </td>
      <td style={{ padding: 4, color: C_TEXT, fontFamily: 'monospace' }}>
        {op.ueid?.amf_ue_ngap_id ?? op.ueid?.ran_ue_ngap_id ?? '—'}
      </td>
      <td style={{ padding: 4, color: C_TEXT, textAlign: 'right', fontFamily: 'monospace' }}>
        {op.latency_ms !== undefined ? `${op.latency_ms}ms` : '—'}
      </td>
      <td style={{ padding: 4, color: oc, fontWeight: 600 }}>
        {op.outcome}
      </td>
    </tr>
  );
}
