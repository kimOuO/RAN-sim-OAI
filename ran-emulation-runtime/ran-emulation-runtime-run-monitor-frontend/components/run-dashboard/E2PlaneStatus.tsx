import type { DuTick, E2AdapterStatus, SceneRun } from '@/types/telemetry';

export function E2PlaneStatus({ run, e2, du }: { run: SceneRun; e2: E2AdapterStatus | null; du: DuTick | null }) {
  const link = e2?.sctp_link;
  return (
    <dl className="kv">
      <dt>E2 node</dt><dd className="mono">{run.e2_node_id || '—'}</dd>
      <dt>SCTP → RIC</dt><dd>{link ? <><span className={`pill ${link.connected ? 'good' : 'poor'}`}>{link.connected ? 'connected' : 'down'}</span> {link.target_host}:{link.target_port}</> : <span className="muted">E2Adapter 無回應</span>}</dd>
      <dt>倍速</dt><dd className="num">{run.speed_x}× 設定{du ? ` → ${du.achieved_speed_x.toFixed(2)}× 達成` : ''}</dd>
      <dt>DU tick</dt><dd className="num">{du ? `${du.tick_count} (${du.is_running ? 'running' : 'stopped'}, wall ${du.wall_tick_ms} ms)` : '—'}</dd>
      <dt>模式</dt><dd>{run.mode} · sim_dt {run.sim_dt_ms} ms · {run.duration_sec}s</dd>
    </dl>
  );
}
