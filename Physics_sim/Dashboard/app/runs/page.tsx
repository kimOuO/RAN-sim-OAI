'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  listScenarios, startFastRun, stopFastRun, type ScenarioRow,
} from '@/services/api/scenario';
import {
  fetchDriverStatus, fetchDuPm, fetchControlActions, fetchHandovers,
  evaluateIm, evaluateCco, evaluateEs,
  type DuPmSnapshot, type ScenarioDriverStatus, type ControlActionRow,
  type HandoverEventRow, type TriggerEval,
} from '@/services/api/scenarioMonitor';

const PRESETS: Array<{
  id: string;
  label: string;
  desc: string;
  evaluator: (pm: DuPmSnapshot) => TriggerEval;
  requires: { min_gnbs: number; min_cells_per_gnb: number; min_ues: number };
}> = [
  { id: 'im_fast',  label: 'IM',  desc: 'PRB 滿 + channel 弱 → xApp 下 PRB quota cap',
    evaluator: evaluateIm,
    requires: { min_gnbs: 1, min_cells_per_gnb: 1, min_ues: 1 } },
  { id: 'cco_fast', label: 'CCO', desc: 'gNB 間 PRB 失衡 → xApp 下 handover',
    evaluator: evaluateCco,
    requires: { min_gnbs: 2, min_cells_per_gnb: 1, min_ues: 1 } },
  { id: 'es_fast',  label: 'ES',  desc: '低載 + 無流量 → xApp 下 HO + PRB cap',
    evaluator: evaluateEs,
    requires: { min_gnbs: 1, min_cells_per_gnb: 1, min_ues: 1 } },
];

interface RunningState {
  scenarioId: string;
  sessionUuid: string;
  ratio: number;
  startedAtWallMs: number;        // wall-clock 起跑時刻
  scenarioStartHHMMSS: string;    // scenario 內 sim-time 起跑時刻(預設 "10:00:00")
}

export default function RunsPage() {
  const [scenarios, setScenarios] = useState<ScenarioRow[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const [running, setRunning] = useState<RunningState | null>(null);
  const [driver, setDriver] = useState<ScenarioDriverStatus | null>(null);
  const [pm, setPm] = useState<DuPmSnapshot | null>(null);
  const [actions, setActions] = useState<ControlActionRow[]>([]);
  const [handovers, setHandovers] = useState<HandoverEventRow[]>([]);
  const [nowMs, setNowMs] = useState<number>(Date.now());
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [scenarioStart, setScenarioStart] = useState<string>('10:00:00');

  const reload = async () => {
    try { setScenarios(await listScenarios()); } catch (e: any) { setError(e.message ?? 'list failed'); }
  };

  useEffect(() => { reload(); const t = setInterval(reload, 3000); return () => clearInterval(t); }, []);

  // monitor poll
  useEffect(() => {
    if (!running) return;
    const poll = async () => {
      const [d, p, a, ho] = await Promise.all([
        fetchDriverStatus().catch(() => null),
        fetchDuPm().catch(() => null),
        fetchControlActions(running.sessionUuid),
        fetchHandovers(running.sessionUuid),
      ]);
      if (d) setDriver(d);
      if (p) setPm(p);
      setActions(a);
      setHandovers(ho);
      setNowMs(Date.now());
    };
    poll();
    pollRef.current = setInterval(poll, 1000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [running]);

  // helper:把「HH:MM:SS + elapsed_sec」轉成 "HH:MM:SS"
  const addSecToHMS = (hms: string, addSec: number): string => {
    const [h, m, s] = hms.split(':').map(Number);
    const total = (h * 3600 + m * 60 + s) + Math.floor(addSec);
    const hh = Math.floor(total / 3600) % 24;
    const mm = Math.floor((total % 3600) / 60);
    const ss = total % 60;
    return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
  };
  const formatWallHMS = (ms: number) => {
    const d = new Date(ms);
    return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;
  };

  const onRun = async (s: ScenarioRow, ratio: number) => {
    setBusy(true); setError('');
    try {
      const wallTickMs = Math.max(10, Math.round(s.tick_ms / ratio));
      const sessionUuid = `runs_${s.scenario_id}_${Date.now()}`;
      const startedAtWallMs = Date.now();
      await startFastRun({
        scenarioId: s.scenario_id,
        targetWallTickMs: wallTickMs,
        sceneId: s.scene_id,
        sessionUuid,
        timeCompressionRatio: ratio,
      });
      setRunning({
        scenarioId: s.scenario_id, sessionUuid, ratio,
        startedAtWallMs, scenarioStartHHMMSS: scenarioStart,
      });
      setError(`✓ ${s.scenario_id} @ ${ratio}x — session=${sessionUuid}`);
    } catch (e: any) {
      setError(`start failed: ${e?.message ?? e}`);
    } finally { setBusy(false); }
  };

  const onStop = async () => {
    setBusy(true);
    try {
      await stopFastRun();
      setRunning(null); setDriver(null); setPm(null);
      setActions([]); setHandovers([]);
    }
    catch (e: any) { setError(`stop failed: ${e?.message ?? e}`); }
    finally { setBusy(false); }
  };

  const getPreset = (sid: string) => PRESETS.find(p => p.id === sid);
  const trigEval = (pm && running) ? getPreset(running.scenarioId)?.evaluator(pm) : null;
  const driverPct = driver ? (driver.sim_tick_idx / Math.max(1, driver.total_ticks) * 100) : 0;

  return (
    <div style={{ maxWidth: 1300, margin: '0 auto', padding: 24 }}>
      <h1>Scenario Runs (Fast-Replay Monitor)</h1>
      <p style={{ color: '#94a3b8', fontSize: 13 }}>
        三個 OAI 劇本一鍵跑 fast mode,即時觀察 KPM 是否達觸發門檻 + RIC 是否真的下指令。
        要上傳新劇本/Precompute 請去 <Link href="/scenarios" style={{ color: '#60a5fa' }}>/scenarios</Link>。
      </p>

      {error && (
        <div style={{
          padding: '8px 12px', margin: '12px 0', borderRadius: 4,
          background: error.startsWith('✓') ? '#064e3b' : '#7f1d1d',
          color: error.startsWith('✓') ? '#a7f3d0' : '#fecaca', fontSize: 13,
        }}>{error}</div>
      )}

      {!running && (
        <>
          <div style={{
            marginTop: 16, padding: 12, background: '#0f172a', borderRadius: 6,
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <label style={{ fontSize: 12, color: '#94a3b8' }}>Scenario 假設起始時間 (sim wall-clock):</label>
            <input
              type="time" step="1"
              value={scenarioStart}
              onChange={(e) => setScenarioStart(e.target.value)}
              style={{
                padding: '4px 8px', background: '#020617', border: '1px solid #334155',
                borderRadius: 3, color: '#e5e7eb', fontSize: 12,
              }}
            />
            <span style={{ fontSize: 11, color: '#64748b' }}>
              ↑ 跑起來時這就是 scenario 內「0 秒」對應的時鐘;sim-time clock 從這個值往前跑
            </span>
          </div>
          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginTop: 16 }}>
          {PRESETS.map((p) => {
            const sc = scenarios.find(s => s.scenario_id === p.id);
            const ready = sc?.precompute_status === 'ready';
            return (
              <div key={p.id} style={{
                padding: 16, background: '#1e293b', border: '1px solid #334155', borderRadius: 8,
              }}>
                <div style={{ fontSize: 18, fontWeight: 600, color: '#e5e7eb' }}>{p.label}</div>
                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4, minHeight: 32 }}>{p.desc}</div>
                <div style={{ marginTop: 12, fontSize: 11, color: '#64748b' }}>
                  scenario_id: <span style={{ color: '#cbd5e1' }}>{p.id}</span><br />
                  status:{' '}
                  <span style={{
                    color: ready ? '#22c55e' : (sc ? '#f59e0b' : '#ef4444'),
                  }}>{sc?.precompute_status ?? 'NOT UPLOADED'}</span>
                  {sc && sc.precompute_status === 'running' && (
                    <span style={{ marginLeft: 6 }}>({sc.precompute_progress.toFixed(0)}%)</span>
                  )}
                </div>
                <div style={{
                  marginTop: 6, fontSize: 10, color: '#94a3b8',
                  padding: '4px 6px', background: '#0f172a', borderRadius: 3,
                }}>
                  Needs:{' '}
                  <strong style={{ color: '#cbd5e1' }}>
                    ≥{p.requires.min_gnbs} gNB
                    {p.requires.min_gnbs > 1 ? ' ⚠️' : ''}
                  </strong>
                  {' · '}
                  ≥{p.requires.min_cells_per_gnb} cell/gNB · ≥{p.requires.min_ues} UE
                </div>
                <div style={{ marginTop: 12, display: 'flex', gap: 6 }}>
                  {[2, 4, 10].map((r) => (
                    <button key={r}
                      onClick={() => sc && onRun(sc, r)}
                      disabled={busy || !ready}
                      style={{
                        padding: '6px 12px', background: ready ? '#22c55e' : '#475569',
                        color: 'white', border: 'none', borderRadius: 4,
                        cursor: ready ? 'pointer' : 'not-allowed', fontSize: 12,
                      }}
                    >▶ {r}x</button>
                  ))}
                </div>
                {!sc && (
                  <div style={{ marginTop: 8, fontSize: 11, color: '#fca5a5' }}>
                    需要先去 /scenarios 上傳並 Precompute
                  </div>
                )}
              </div>
            );
          })}
          </section>
        </>
      )}

      {running && (
        <section style={{ marginTop: 16 }}>
          {/* Header bar — 含 wall-time vs sim-time 雙時鐘 */}
          <div style={{
            padding: 16, background: '#0f172a', border: '1px solid #1e3a8a', borderRadius: 8,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: 14, color: '#dbeafe' }}>
                ⚡ Running <strong>{running.scenarioId}</strong> @ {running.ratio}x
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                session_uuid: {running.sessionUuid}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 11, color: '#64748b' }}>Wall(現實時間)</div>
                <div style={{
                  fontSize: 18, color: '#cbd5e1', fontFamily: 'ui-monospace,monospace',
                  fontWeight: 600,
                }}>
                  {formatWallHMS(nowMs)}
                </div>
                <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
                  跑了 {((nowMs - running.startedAtWallMs) / 1000).toFixed(1)}s
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 11, color: '#fbbf24' }}>Sim(劇本時間)</div>
                <div style={{
                  fontSize: 18, color: '#fde68a', fontFamily: 'ui-monospace,monospace',
                  fontWeight: 600,
                }}>
                  {addSecToHMS(running.scenarioStartHHMMSS, driver?.elapsed_sim_sec ?? 0)}
                </div>
                <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
                  已過 {(driver?.elapsed_sim_sec ?? 0).toFixed(1)}s 劇本時間
                </div>
              </div>
              <button onClick={onStop} disabled={busy} style={{
                padding: '8px 14px', background: '#ef4444', color: 'white', border: 'none',
                borderRadius: 4, cursor: 'pointer', fontSize: 13,
              }}>⏹ Stop</button>
            </div>
          </div>

          {/* Progress + KPM 評估 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 12, marginTop: 12 }}>
            <div style={{ padding: 12, background: '#111827', borderRadius: 6, border: '1px solid #1f2937' }}>
              <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 8 }}>Driver Progress</div>
              {driver && (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#94a3b8' }}>
                    <span>tick {driver.sim_tick_idx} / {driver.total_ticks}</span>
                    <span>sim {driver.elapsed_sim_sec.toFixed(1)}s · wall {driver.elapsed_wall_sec.toFixed(1)}s · {driver.sim_speed_x}x</span>
                  </div>
                  <div style={{ marginTop: 6, height: 8, background: '#1f2937', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ width: `${driverPct}%`, height: '100%', background: '#3b82f6', transition: 'width 0.3s' }} />
                  </div>
                  <div style={{ marginTop: 8, fontSize: 11, color: '#64748b' }}>
                    pushes: {driver.position_push_count}  ·  injects: {driver.inject_call_count}
                    {driver.last_error && <span style={{ color: '#fca5a5', marginLeft: 8 }}>err: {driver.last_error}</span>}
                  </div>
                </>
              )}
            </div>

            <div style={{ padding: 12, background: '#111827', borderRadius: 6, border: '1px solid #1f2937' }}>
              <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 8 }}>KPM Trigger Evaluation</div>
              {trigEval ? (
                <>
                  <div style={{ display: 'inline-block', padding: '4px 10px', borderRadius: 4, fontSize: 12,
                    background: trigEval.triggered ? '#064e3b' : '#7f1d1d',
                    color: trigEval.triggered ? '#a7f3d0' : '#fecaca' }}>
                    {trigEval.triggered ? '✓ TRIGGERED' : '✗ not yet'}
                  </div>
                  <ul style={{ margin: '8px 0 0', padding: 0, listStyle: 'none' }}>
                    {trigEval.conditions.map((c, i) => (
                      <li key={i} style={{ fontSize: 11, marginTop: 4, color: c.ok ? '#a7f3d0' : '#fecaca' }}>
                        {c.ok ? '✓' : '✗'} {c.label}: <strong>{c.value}</strong>
                      </li>
                    ))}
                  </ul>
                </>
              ) : <div style={{ color: '#64748b', fontSize: 12 }}>waiting for first PM sample…</div>}
            </div>
          </div>

          {/* Cell PRB table */}
          <div style={{ marginTop: 12, padding: 12, background: '#111827', borderRadius: 6, border: '1px solid #1f2937' }}>
            <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 8 }}>per-Cell PRB / SINR / DL Bytes</div>
            {pm && (
              <table style={{ width: '100%', fontSize: 12, color: '#cbd5e1', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ color: '#94a3b8', borderBottom: '1px solid #334155' }}>
                    <th style={{ textAlign: 'left', padding: 4 }}>cell</th>
                    <th style={{ textAlign: 'right', padding: 4 }}>PRB used</th>
                    <th style={{ textAlign: 'right', padding: 4 }}>avg SINR (dB)</th>
                    <th style={{ textAlign: 'right', padding: 4 }}>avg RSRP</th>
                    <th style={{ textAlign: 'right', padding: 4 }}>DL bytes (KB)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(pm.gnbs).map(([name, g]) => {
                    const dl = Object.values(g.pdcp_bytes_dl || {}).reduce((s, v) => s + v, 0);
                    return (
                      <tr key={name} style={{ borderBottom: '1px solid #1f2937' }}>
                        <td style={{ padding: 4, fontFamily: 'ui-monospace,monospace' }}>{name}</td>
                        <td style={{ padding: 4, textAlign: 'right' }}>{g.prb_used_dl}</td>
                        <td style={{ padding: 4, textAlign: 'right' }}>{g.avg_sinr_db.toFixed(1)}</td>
                        <td style={{ padding: 4, textAlign: 'right' }}>{g.avg_rsrp_dbm.toFixed(1)}</td>
                        <td style={{ padding: 4, textAlign: 'right' }}>{(dl / 1024).toFixed(1)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* HandoverEvent timeline */}
          <div style={{ marginTop: 12, padding: 12, background: '#111827', borderRadius: 6, border: '1px solid #1f2937' }}>
            <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 8 }}>
              Handover Events ({handovers.length})
              {handovers.length === 0 && <span style={{ color: '#64748b', marginLeft: 8, fontSize: 11 }}>
                — A3 還沒觸發
              </span>}
            </div>
            {handovers.length > 0 && (
              <table style={{ width: '100%', fontSize: 12, color: '#cbd5e1', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ color: '#94a3b8', borderBottom: '1px solid #334155' }}>
                    <th style={{ textAlign: 'left', padding: 4 }}>sim-time</th>
                    <th style={{ textAlign: 'left', padding: 4 }}>UE</th>
                    <th style={{ textAlign: 'left', padding: 4 }}>source → target</th>
                    <th style={{ textAlign: 'left', padding: 4 }}>trigger</th>
                    <th style={{ textAlign: 'left', padding: 4 }}>status</th>
                  </tr>
                </thead>
                <tbody>
                  {handovers.slice(-15).map((h) => {
                    // 從 event_ts(wall-clock ISO)推算 sim-time
                    const wallMs = h.event_ts ? new Date(h.event_ts).getTime() : 0;
                    const elapsedSec = wallMs > 0 ? (wallMs - running.startedAtWallMs) / 1000 : 0;
                    const simElapsed = elapsedSec * running.ratio;
                    const simHMS = addSecToHMS(running.scenarioStartHHMMSS, simElapsed);
                    return (
                      <tr key={h.ho_uuid} style={{ borderBottom: '1px solid #1f2937' }}>
                        <td style={{ padding: 4, fontFamily: 'ui-monospace,monospace', color: '#fde68a' }}>{simHMS}</td>
                        <td style={{ padding: 4 }}>
                          <span style={{ background: '#1e40af', padding: '1px 6px', borderRadius: 3 }}>{h.ue_name}</span>
                        </td>
                        <td style={{ padding: 4 }}>
                          <span style={{ color: '#fca5a5' }}>{h.source_cell}</span>
                          {' → '}
                          <span style={{ color: '#a7f3d0' }}>{h.target_cell}</span>
                        </td>
                        <td style={{ padding: 4 }}>{h.trigger}</td>
                        <td style={{ padding: 4, color: h.status === 'SUCC' ? '#a7f3d0' : '#fcd34d' }}>{h.status}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* RIC ControlActions */}
          <div style={{ marginTop: 12, padding: 12, background: '#111827', borderRadius: 6, border: '1px solid #1f2937' }}>
            <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 8 }}>
              RIC Control Actions ({actions.length})
              {actions.length === 0 && <span style={{ color: '#64748b', marginLeft: 8, fontSize: 11 }}>
                — xApp 還沒下指令
              </span>}
            </div>
            {actions.length > 0 && (
              <table style={{ width: '100%', fontSize: 12, color: '#cbd5e1', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ color: '#94a3b8', borderBottom: '1px solid #334155' }}>
                    <th style={{ textAlign: 'left', padding: 4 }}>time</th>
                    <th style={{ textAlign: 'left', padding: 4 }}>action</th>
                    <th style={{ textAlign: 'left', padding: 4 }}>UE / cell</th>
                    <th style={{ textAlign: 'left', padding: 4 }}>outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {actions.slice(-20).map(a => (
                    <tr key={a.id} style={{ borderBottom: '1px solid #1f2937' }}>
                      <td style={{ padding: 4 }}>{a.action_ts?.slice(11, 19) ?? '-'}</td>
                      <td style={{ padding: 4 }}>
                        <strong>{a.action_label}</strong> ({a.control_style}/{a.control_action_id})
                      </td>
                      <td style={{ padding: 4 }}>
                        {a.ue_name && <span style={{ background: '#1e40af', padding: '1px 6px', borderRadius: 3, marginRight: 4 }}>{a.ue_name}</span>}
                        {a.cell_id && <span style={{ background: '#7c2d12', padding: '1px 6px', borderRadius: 3 }}>{a.cell_id}</span>}
                      </td>
                      <td style={{ padding: 4, color: a.outcome === 'OK' ? '#a7f3d0' : '#fecaca' }}>{a.outcome}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
