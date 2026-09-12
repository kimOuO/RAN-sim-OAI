'use client';

import { useMemo, useState } from 'react';
import {
  LineChart, Line, ResponsiveContainer, YAxis, Tooltip, XAxis,
} from 'recharts';
import { useCellStatus } from '@/hooks/feature/log/useCellStatus';
import { useUeMetricsHistory, type MetricName } from '@/hooks/feature/log/useUeMetricsHistory';

const C_CARD = '#111827';
const C_BORDER = '#374151';
const C_TEXT = '#cbd5e1';
const C_MUTED = '#6b7280';
const C_ACCENT = '#a855f7';

const METRIC_DETAILS: { name: MetricName; label: string; color: string; unit: string }[] = [
  { name: 'RSRP', label: 'RSRP', color: '#06b6d4', unit: 'dBm' },
  { name: 'SINR', label: 'SINR', color: '#ef4444', unit: 'dB' },
  { name: 'DRB.UEThpDl', label: 'Throughput DL', color: '#10b981', unit: 'kbps' },
  { name: 'DRB.RlcSduDelayDl', label: 'RLC Delay DL', color: '#f59e0b', unit: 'ms' },
];

const METRIC_NAMES = METRIC_DETAILS.map(m => m.name);

export function UeSignalLab() {
  const { ueStates, loading } = useCellStatus();
  const [selected, setSelected] = useState<string | null>(null);

  // 自動選第一個 UE
  const effectiveSelection = useMemo(() => {
    if (selected && ueStates.some(u => u.ue_id === selected)) return selected;
    return ueStates[0]?.ue_id || null;
  }, [selected, ueStates]);

  const history = useUeMetricsHistory(effectiveSelection, METRIC_NAMES);
  const seriesByName = useMemo(() => {
    const m = new Map<string, typeof history.series[number]>();
    history.series.forEach(s => m.set(s.metric, s));
    return m;
  }, [history.series]);

  const selectedUe = useMemo(
    () => ueStates.find(u => u.ue_id === effectiveSelection),
    [ueStates, effectiveSelection],
  );

  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{
        margin: 0, color: C_TEXT, fontSize: 14, fontWeight: 600,
        marginBottom: 12,
      }}>
        🔬 UE Signal Lab
      </h2>
      <div style={{
        display: 'grid', gridTemplateColumns: '200px 1fr', gap: 12,
        background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8,
        padding: 12,
      }}>
        {/* UE List */}
        <div style={{
          maxHeight: 400, overflowY: 'auto',
          paddingRight: 8, borderRight: `1px solid ${C_BORDER}`,
        }}>
          <div style={{ fontSize: 10, color: C_MUTED, textTransform: 'uppercase', marginBottom: 6 }}>
            UE list ({ueStates.length})
          </div>
          {loading && ueStates.length === 0 && (
            <div style={{ fontSize: 11, color: C_MUTED }}>loading...</div>
          )}
          {ueStates.map(u => (
            <button key={u.ue_id} onClick={() => setSelected(u.ue_id)} style={{
              display: 'block', width: '100%', textAlign: 'left',
              padding: '8px 10px', marginBottom: 4, borderRadius: 4,
              background: u.ue_id === effectiveSelection ? '#1e293b' : 'transparent',
              border: `1px solid ${u.ue_id === effectiveSelection ? C_ACCENT : 'transparent'}`,
              color: C_TEXT, cursor: 'pointer', fontSize: 12, fontFamily: 'monospace',
            }}>
              <div style={{
                color: u.ue_id === effectiveSelection ? C_ACCENT : C_TEXT,
                fontWeight: 600,
              }}>
                {u.ue_id}
              </div>
              <div style={{ fontSize: 10, color: C_MUTED, marginTop: 2 }}>
                {u.serving_cell_id || '—'}
                {u.last_cqi !== undefined && ` · CQI ${u.last_cqi}`}
              </div>
            </button>
          ))}
        </div>

        {/* Detail */}
        <div>
          {selectedUe ? (
            <>
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                marginBottom: 12,
              }}>
                <div>
                  <span style={{
                    fontSize: 14, fontWeight: 700, color: C_ACCENT,
                    fontFamily: 'monospace',
                  }}>
                    {selectedUe.ue_id}
                  </span>
                  <span style={{ fontSize: 11, color: C_MUTED, marginLeft: 8 }}>
                    @ {selectedUe.serving_cell_id || '—'}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: C_MUTED, fontFamily: 'monospace' }}>
                  CQI={selectedUe.last_cqi ?? '—'} ·
                  MCS={selectedUe.last_mcs_dl ?? '—'} ·
                  rank={selectedUe.last_rank ?? '—'} ·
                  PMI={selectedUe.last_pmi ?? '—'}
                </div>
              </div>

              <div style={{
                display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12,
              }}>
                {METRIC_DETAILS.map(m => {
                  const series = seriesByName.get(m.name);
                  const points = series?.points || [];
                  const latest = points.length > 0 ? points[points.length - 1].value : null;
                  const data = points.map((p, i) => ({ i, v: p.value }));

                  return (
                    <div key={m.name} style={{
                      background: '#0b1220', border: `1px solid ${C_BORDER}`, borderRadius: 6,
                      padding: 10,
                    }}>
                      <div style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                        marginBottom: 4,
                      }}>
                        <span style={{ fontSize: 10, color: C_MUTED, textTransform: 'uppercase' }}>
                          {m.label}
                        </span>
                        <span style={{
                          fontSize: 14, fontWeight: 700, color: m.color, fontFamily: 'monospace',
                        }}>
                          {latest !== null && latest !== undefined
                            ? `${Number(latest).toFixed(1)} ${m.unit}`
                            : '—'}
                        </span>
                      </div>
                      <div style={{ height: 80 }}>
                        {data.length > 0 ? (
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={data}>
                              <YAxis hide domain={['auto', 'auto']} />
                              <XAxis hide dataKey="i" />
                              <Tooltip
                                contentStyle={{
                                  background: '#0b1220', border: `1px solid ${C_BORDER}`,
                                  fontSize: 11,
                                }}
                                labelFormatter={() => ''}
                                formatter={(v: any) => [`${Number(v).toFixed(2)} ${m.unit}`, m.label]}
                              />
                              <Line type="monotone" dataKey="v" stroke={m.color}
                                    strokeWidth={2} dot={false}
                                    isAnimationActive={false} />
                            </LineChart>
                          </ResponsiveContainer>
                        ) : (
                          <div style={{
                            height: '100%', display: 'flex', alignItems: 'center',
                            justifyContent: 'center', fontSize: 11, color: C_MUTED,
                          }}>
                            no history (waiting for KPM data)
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {history.error && (
                <div style={{ marginTop: 8, fontSize: 11, color: '#ef4444' }}>
                  err: {history.error}
                </div>
              )}
            </>
          ) : (
            <div style={{
              padding: 24, textAlign: 'center', color: C_MUTED, fontSize: 12,
            }}>
              {ueStates.length === 0
                ? '(no UE attached yet)'
                : 'Select a UE from the list to view metric history'}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
