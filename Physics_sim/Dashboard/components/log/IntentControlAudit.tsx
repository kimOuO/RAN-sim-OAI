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

// E2SM-RC style → 控制「類型」+ 該類型涵蓋的多種 xApp 意圖。
// ★ style 號 ≠ 單一意圖:同一個 control style 被多種意圖劇本共用,不該硬鎖成一種。
//   - style 2(Radio Resource Allocation Control / PRB)→ IM、CCO、ES 都會下
//   - style 3(Connected Mode Mobility Control / Handover)→ CCO、ES、普通 HO 都會下
//   真正是哪種意圖由 xApp 邏輯決定,RC 訊息本身不帶,sim 只看得到 control 類型。
const RC_STYLE_INFO: Record<number, { type: string; intents: string }> = {
  2: { type: 'PRB/RRM', intents: 'IM·CCO·ES' },
  3: { type: 'Mobility/HO', intents: 'CCO·ES·HO' },
};

function rcStyleInfo(style: number): { type: string; intents: string } {
  return RC_STYLE_INFO[style] || { type: `style${style}`, intents: '?' };
}

export function IntentControlAudit() {
  const { ops } = useControlOps();
  const { quotas, simRunning } = usePrbQuotas();
  const { aggregates } = useCellStatus();

  // 劇本沒在跑 → Control Ops 是上一場留下的 → 標「已清除」(除非是剛下的 <10s,
  // 避免 driver.running 邊緣翻轉時誤標剛到的 control)。最多顯示 5 筆。
  const RECENT_MS = 10000;
  const now = Date.now();
  const visibleOps = ops.slice(0, 5).map(op => ({
    op,
    stale: !simRunning && (now - op.recv_ts_ms > RECENT_MS),
  }));

  const cellByName = useMemo(() => {
    const m = new Map<string, typeof aggregates[number]>();
    for (const a of aggregates) m.set(a.cell.cell_id, a);
    return m;
  }, [aggregates]);

  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{
        margin: 0, color: C_TEXT, fontSize: 14, fontWeight: 600,
        marginBottom: 4,
      }}>
        🎯 Intent-Driven Control Audit （xApp 指令端到端）
      </h2>
      <div style={{ color: C_MUTED, fontSize: 11, marginBottom: 12 }}>
        涵蓋多種意圖劇本:CCO（容量受限換手）· IM（干擾管理）· ES（節能）· 一般 Handover。
        欄位顯示 RC 控制「類型」,同一類型可由多種意圖下達（非單一）。
      </div>

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
            <span style={{ color: C_MUTED, fontWeight: 400, fontSize: 10, marginLeft: 6 }}>
              (最近 5 筆)
            </span>
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
                  <th style={{ textAlign: 'left', padding: 4 }}>src</th>
                  <th style={{ textAlign: 'left', padding: 4 }}>style/action</th>
                  <th style={{ textAlign: 'left', padding: 4 }}>action</th>
                  <th style={{ textAlign: 'left', padding: 4 }}>UE</th>
                  <th style={{ textAlign: 'right', padding: 4 }}>latency</th>
                  <th style={{ textAlign: 'left', padding: 4 }}>outcome</th>
                </tr>
              </thead>
              <tbody>
                {visibleOps.map(({ op, stale }, i) => (
                  <OpRow key={i} op={op} stale={stale} />
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
  const sb = (q.set_by || '').toUpperCase();
  const isE2 = sb.includes('E2') || sb === 'XAPP';        // 真 xApp / E2 即時下發
  const isScenario = sb === 'SCENARIO';                   // 劇本套的容量限制(非 xApp)
  const setByColor = q.stale ? C_MUTED
    : isScenario ? '#06b6d4'
    : isE2 ? '#a855f7'
    : (q.set_by ? C_WARN : C_MUTED);
  const setByLabel = isScenario ? '劇本' : (q.set_by || '—');
  return (
    <tr style={{ borderBottom: '1px solid #1f2937', opacity: q.stale ? 0.55 : 1 }}>
      <td style={{ padding: 4, color: C_TEXT, fontFamily: 'monospace' }}>
        {q.cell_id}
      </td>
      <td style={{
        padding: 4, color: C_TEXT, textAlign: 'right', fontFamily: 'monospace',
        textDecoration: q.stale ? 'line-through' : 'none',
      }}>
        {q.min_prb}/{q.max_prb}/{q.dedicated_prb}
      </td>
      <td style={{ padding: 4, fontWeight: 600 }}>
        <span style={{ color: setByColor }}>{setByLabel}</span>
        {q.stale && (
          <span style={{ color: C_MUTED, fontSize: 9, marginLeft: 4 }}
                title="無 sim 在跑 — 這是上一場留下的殘留,已邏輯清掉,下次 Start Sim 會實際移除">
            · 已清掉(殘留)
          </span>
        )}
      </td>
    </tr>
  );
}

function OpRow({ op, stale }: { op: ControlOp; stale?: boolean }) {
  const meta = SIM_ACTION_LABEL[op.sim_action] || { label: op.sim_action, color: C_TEXT };
  const rc = rcStyleInfo(op.style);
  const oc = stale ? C_MUTED
    : op.outcome === 'ok' ? C_OK
    : op.outcome === 'pending' ? C_WARN
    : C_FAIL;
  // Control Ops 走 E2 control plane(control_req_recv)= RIC/xApp 即時下發。
  // 劇本的限制(cell_quota)是直接打 DU API、不經 E2,所以不會出現在這 → 此處一律 xApp。
  return (
    <tr style={{ borderBottom: '1px solid #1f2937', opacity: stale ? 0.55 : 1 }}>
      <td style={{ padding: 4, color: C_MUTED, fontFamily: 'monospace' }}>
        {new Date(op.recv_ts_ms).toLocaleTimeString('en-GB', { hour12: false })}
      </td>
      <td style={{ padding: 4, color: '#a855f7', fontWeight: 600 }}>
        xApp
      </td>
      <td style={{
        padding: 4, color: C_TEXT, fontFamily: 'monospace',
        textDecoration: stale ? 'line-through' : 'none',
      }}>
        s{op.style}/a{op.action}
        <span style={{ color: C_TEXT, marginLeft: 4 }}>
          {rc.type}
        </span>
        <span style={{ color: C_MUTED, marginLeft: 4, fontSize: 9 }} title="此 control 類型可由這些意圖劇本下達(CCO/IM/ES/HO),非單一">
          {rc.intents}
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
        {stale && (
          <span style={{ color: C_MUTED, fontSize: 9, marginLeft: 4 }}
                title="劇本已結束 — 這是上一場留下的 control 紀錄,已清除">
            · 已清除
          </span>
        )}
      </td>
    </tr>
  );
}
