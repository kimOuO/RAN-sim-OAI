import { fmtSimTime } from '@/hooks/feature/kpmDerive';
import type { DuCell, DuTick, E2AdapterStatus, RunInstance, SceneRun, UeDriverStatus } from '@/types/telemetry';

/** RAN 模擬執行狀況:UE driver 進度、DU tick / 倍速、DU 上的 cell、E2 面 */
export function RanRuntimePanel({ run, du, cells, ue, e2, instances }: { run: SceneRun; du: DuTick | null; cells: DuCell[]; ue: UeDriverStatus | null; e2: E2AdapterStatus | null; instances: RunInstance[] }) {
  const ago = (iso: string | null) => (iso ? `${Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))} s 前` : '—');
  const prog = ue && ue.total_ticks ? Math.min(1, ue.sim_tick_idx / ue.total_ticks) : 0;
  const speedOk = du ? du.achieved_speed_x >= du.sim_speed_x * 0.9 : false;
  const link = e2?.sctp_link;
  return (
    <div className="runtime">
      <div className="rt-row">
        <div className="rt-k">劇本進度</div>
        <div className="rt-v"><div className="prog"><i style={{ width: `${prog * 100}%` }} /></div>
          <span className="mono small">{ue ? `${fmtSimTime(ue.elapsed_sim_sec)} / ${fmtSimTime((ue.total_ticks * run.sim_dt_ms) / 1000)} sim · wall ${fmtSimTime(ue.elapsed_wall_sec)} · ${ue.phase}` : 'UE driver 無回應'}</span></div>
      </div>
      <div className="rt-grid">
        <div><span className="rt-k">達成倍速</span><b className={speedOk ? 'ok' : 'warn'}>{du ? `${du.achieved_speed_x.toFixed(2)}×` : '—'}</b><span className="muted"> / 設定 {run.speed_x}×</span></div>
        <div><span className="rt-k">DU tick</span><b>{du?.tick_count ?? '—'}</b><span className="muted"> sfn {du?.sfn ?? '—'} · wall {du?.wall_tick_ms ?? '—'} ms</span></div>
        <div><span className="rt-k">UE 附著</span><b>{ue ? ue.ue_count - ue.attach_failed.length : '—'}</b><span className="muted"> / {ue?.ue_count ?? '—'}{ue?.attach_failed.length ? ` · 失敗 ${ue.attach_failed.length}` : ''}</span></div>
        <div><span className="rt-k">E2 → RIC</span><b className={link?.connected ? 'ok' : 'bad'}>{link ? (link.connected ? 'CONNECTED' : 'DOWN') : '—'}</b><span className="muted"> {link ? `${link.target_host}:${link.target_port}` : ''}</span></div>
      </div>
      {instances.length > 0 && <div className="inst-row">{instances.map((i) => <span key={i.run_instance_uuid} className="inst" title={i.container_id}><span className={`dot ${i.status === 'running' ? 'ok' : i.status === 'starting' || i.status === 'degraded' ? 'warning' : 'bad'}`} /><b className="mono">{i.role}-{i.f_scene_run_uuid.slice(-8)}</b><span className="muted">:{i.host_port ?? '—'} · {i.status} · 心跳 {ago(i.last_heartbeat)}</span>{i.health_detail ? <span className="inst-detail" style={{ color: 'var(--warning, #e6a23c)' }}> ⚠ {i.health_detail}</span> : null}</span>)}</div>}
      <table className="cells"><thead><tr><th>DU cell</th><th>PCI</th><th>PRB</th><th>freq</th><th>BW</th><th>狀態</th></tr></thead>
        <tbody>{cells.map((c) => <tr key={c.cell_id}><td className="mono">{c.cell_id}</td><td className="num">{c.pci}</td><td className="num">{c.total_prb}</td><td className="num">{c.freq_ghz} GHz</td><td className="num">{c.bw_mhz} MHz</td><td><span className={`dot ${c.is_active ? 'ok' : 'bad'}`} />{c.is_active ? 'active' : 'off'}</td></tr>)}</tbody></table>
    </div>
  );
}
