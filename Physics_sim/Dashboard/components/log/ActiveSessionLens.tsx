'use client';

// Active Session Lens — 把 /scenarios 的 live monitor 精華擠進 /logs 頂部
//
// 設計原則:沒跑 scenario 時整個區塊 collapse 到一行 hint;跑起來時展開顯示:
//   - 雙時鐘 header(wall + sim)
//   - Driver 進度條
//   - KPM threshold log(IM/CCO/ES 三排)
//   - per-Cell PRB% 圖(sim-time cursor)
//   - per-UE RSRP+SINR+Thp 圖(sim-time cursor)
//   - Handover events + RIC actions list
//
// /scenarios 仍是「上傳+管理+完整 monitor」的入口;這裡是 ops view 的快照鏡頭。

import Link from 'next/link';
import {
  evaluateIm, evaluateCco, evaluateEs,
  type DuPmSnapshot, type TriggerEval,
} from '@/services/api/scenarioMonitor';
import { stopFastRun } from '@/services/api/scenario';
import { SimTimeChart } from '@/components/SimTimeChart';
import { useScenarioContext } from '@/components/ScenarioProvider';

const EVALUATORS: Record<string, (pm: DuPmSnapshot) => TriggerEval> = {
  im: evaluateIm, cco: evaluateCco, es: evaluateEs,
  im_fast: evaluateIm, cco_fast: evaluateCco, es_fast: evaluateEs,
  im_1hr: evaluateIm, cco_1hr: evaluateCco, es_1hr: evaluateEs,
};

function addSecToHMS(hms: string, addSec: number): string {
  const [h, m, s] = hms.split(':').map(Number);
  const total = (h * 3600 + m * 60 + s) + Math.floor(addSec);
  const hh = Math.floor(total / 3600) % 24;
  const mm = Math.floor((total % 3600) / 60);
  const ss = total % 60;
  return `${String(hh).padStart(2,'0')}:${String(mm).padStart(2,'0')}:${String(ss).padStart(2,'0')}`;
}

export function ActiveSessionLens({ sessionStartedAtMs: _sessionStartedAtMs }: { sessionStartedAtMs?: number | null }) {
  // polling 已搬到 layout 層級的 <ScenarioProvider>,這裡只 consume context
  // → 切 page (/scenarios → /logs → /editor) 不會中斷 history,跑劇本資料保留。
  const { driver, pm, actions, handovers, history, sessionUuid, sessionStartedAtMs } = useScenarioContext();

  // 沒有 active session — 顯示一條 hint
  if (!driver || !driver.running) {
    return (
      <section style={{
        margin: '8px 0 16px', padding: '8px 12px',
        background: '#0f172a', border: '1px solid #1e293b', borderRadius: 4,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{ fontSize: 12, color: '#64748b' }}>
          ⓘ No active scenario session.
        </span>
        <Link href="/scenarios" style={{ fontSize: 12, color: '#60a5fa' }}>
          → Start one from /scenarios
        </Link>
      </section>
    );
  }

  // Active session — 展開全部
  const totalTicks = driver.total_ticks || 1;
  const pct = (driver.sim_tick_idx / totalTicks) * 100;
  const scenarioStart = '10:00:00';  // TODO: 從 metadata 拉
  const simHMS = addSecToHMS(scenarioStart, driver.elapsed_sim_sec);
  const evalFn = EVALUATORS[driver.scenario_id ?? ''];
  const trigEval = (evalFn && pm) ? evalFn(pm) : null;
  const simNowSec = Math.round(driver.elapsed_sim_sec);

  // chart series 配置
  const cellKeys = history.length > 0 ? Object.keys(history[history.length-1]).filter(k => k.startsWith('prb_')) : [];
  const ueKeys = history.length > 0 ? Object.keys(history[history.length-1]).filter(k => k.startsWith('rsrp_')) : [];
  const CELL_COLORS = ['#22c55e', '#ef4444', '#3b82f6', '#f59e0b'];
  const UE_COLORS = ['#60a5fa', '#fbbf24', '#a78bfa', '#f472b6'];

  const cellSeries = cellKeys.map((k, i) => ({
    key: k, label: k.replace('prb_', '') + ' PRB%',
    color: CELL_COLORS[i % CELL_COLORS.length],
  }));
  const ueRsrpSeries = ueKeys.map((k, i) => ({
    key: k, label: k.replace('rsrp_', '') + ' RSRP',
    color: UE_COLORS[i % UE_COLORS.length],
  }));

  // handover markers
  const haMarkers = handovers.map(h => {
    const wallMs = h.event_ts ? new Date(h.event_ts).getTime() : 0;
    const elapsedWallSec = wallMs > 0 ? (wallMs - (sessionStartedAtMs ?? 0)) / 1000 : 0;
    return {
      simSec: Math.round(elapsedWallSec * driver.sim_speed_x),
      label: `${h.ue_name}: ${h.source_cell.split('_').pop()}→${h.target_cell.split('_').pop()}`,
      color: '#fbbf24',
    };
  });

  const wrapper: React.CSSProperties = {
    margin: '8px 0 20px', padding: 12,
    background: '#0c1525', border: '1px solid #1e3a8a', borderRadius: 8,
  };

  return (
    <section style={wrapper}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
        <div>
          <span style={{ fontSize: 13, color: '#dbeafe', fontWeight: 600 }}>
            🎬 Active Scenario Lens — <strong>{driver.scenario_id}</strong> @ {driver.sim_speed_x}x
          </span>
          <span style={{ marginLeft: 12, fontSize: 11, color: '#64748b' }}>
            session: {sessionUuid.slice(-10)}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#fbbf24' }}>Sim time</div>
            <div style={{ fontSize: 16, color: '#fde68a', fontFamily: 'ui-monospace,monospace', fontWeight: 600 }}>
              {simHMS}
            </div>
          </div>
          <button onClick={async () => { await stopFastRun(); }} style={{
            padding: '6px 12px', background: '#ef4444', color: 'white',
            border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12,
          }}>⏹ Stop</button>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8' }}>
          <span>tick {driver.sim_tick_idx} / {totalTicks}</span>
          <span>{pct.toFixed(0)}% · pushes={driver.position_push_count} · injects={driver.inject_call_count}</span>
        </div>
        <div style={{ height: 4, background: '#1f2937', borderRadius: 2, overflow: 'hidden', marginTop: 4 }}>
          <div style={{ width: `${pct}%`, height: '100%', background: '#3b82f6' }} />
        </div>
      </div>

      {/* KPM threshold log */}
      {trigEval && (
        <div style={{
          padding: '6px 10px', background: '#0a0f1d', border: '1px solid #1f2937',
          borderRadius: 4, marginBottom: 10,
        }}>
          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
            KPM trigger:{' '}
            <span style={{
              padding: '1px 6px', borderRadius: 2,
              background: trigEval.triggered ? '#064e3b' : '#7f1d1d',
              color: trigEval.triggered ? '#a7f3d0' : '#fecaca',
            }}>
              {trigEval.triggered ? '✓ TRIGGERED' : '✗ not yet'}
            </span>
          </div>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            {trigEval.conditions.map((c, i) => (
              <li key={i} style={{ fontSize: 10, color: c.ok ? '#a7f3d0' : '#fca5a5' }}>
                {c.ok ? '✓' : '✗'} {c.label} <strong>{c.value}</strong>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Mini cursor charts (cell + UE) side by side */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div>
          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>per-Cell PRB% — sim-time</div>
          <SimTimeChart
            data={history as any}
            scenarioStart={scenarioStart}
            leftSeries={cellSeries}
            leftLabel="PRB%"
            height={120}
            cursor={simNowSec}
            markers={haMarkers}
          />
        </div>
        <div>
          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>per-UE RSRP — sim-time</div>
          <SimTimeChart
            data={history as any}
            scenarioStart={scenarioStart}
            leftSeries={ueRsrpSeries}
            leftLabel="dBm"
            height={120}
            cursor={simNowSec}
            markers={haMarkers}
          />
        </div>
      </div>

      {/* Bottom: HO + RIC actions tables (compact) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 10 }}>
        <div style={{ fontSize: 11 }}>
          <div style={{ color: '#94a3b8', marginBottom: 4 }}>
            Handovers ({handovers.length})
          </div>
          {handovers.length === 0 ? (
            <div style={{ color: '#64748b', fontSize: 10 }}>— no HO yet</div>
          ) : (
            <ul style={{ margin: 0, padding: 0, listStyle: 'none', maxHeight: 80, overflowY: 'auto' }}>
              {handovers.slice(-5).map(h => (
                <li key={h.ho_uuid} style={{ color: '#cbd5e1', padding: '2px 0' }}>
                  <span style={{ color: '#1e40af', padding: '0 4px', background: '#0a0f1d', borderRadius: 2 }}>{h.ue_name}</span>
                  {' '}<span style={{ color: '#fca5a5' }}>{h.source_cell.split('_').pop()}</span>
                  {' → '}<span style={{ color: '#a7f3d0' }}>{h.target_cell.split('_').pop()}</span>
                  {' '}<span style={{ color: h.status === 'SUCC' ? '#a7f3d0' : '#fcd34d', fontSize: 10 }}>{h.status}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div style={{ fontSize: 11 }}>
          <div style={{ color: '#94a3b8', marginBottom: 4 }}>
            RIC Control Actions ({actions.length})
          </div>
          {actions.length === 0 ? (
            <div style={{ color: '#64748b', fontSize: 10 }}>— no xApp action yet</div>
          ) : (
            <ul style={{ margin: 0, padding: 0, listStyle: 'none', maxHeight: 80, overflowY: 'auto' }}>
              {actions.slice(-5).map(a => (
                <li key={a.id} style={{ color: '#cbd5e1', padding: '2px 0' }}>
                  <span style={{ color: '#fbbf24' }}>{a.action_ts?.slice(11, 19) ?? ''}</span>
                  {' '}<strong>{a.action_label}</strong>
                  {a.ue_name && <span style={{ marginLeft: 4, padding: '0 4px', background: '#0a0f1d', borderRadius: 2, color: '#60a5fa' }}>{a.ue_name}</span>}
                  {a.cell_id && <span style={{ marginLeft: 4, padding: '0 4px', background: '#0a0f1d', borderRadius: 2, color: '#fca5a5' }}>{a.cell_id}</span>}
                  {' '}<span style={{ color: a.outcome === 'OK' ? '#a7f3d0' : '#fecaca', fontSize: 10 }}>{a.outcome}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
