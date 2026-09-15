import type { RicObservation } from '@/types/telemetry';

/** RIC 端視角:閘道有沒有登記這個 run、E2 node 連線、哪個 xApp pod 在看(只讀)。 */
export function RicObservationPanel({ ric }: { ric: RicObservation | null }) {
  if (!ric) return <div className="muted">尚未取得 RIC 閘道資料</div>;
  if (!ric.gateway || !ric.scenario) return <div className="ric-obs"><span className="dot bad" /> 閘道未登記此 run{ric.scenario?.error ? <span className="muted"> · {ric.scenario.error}</span> : null}</div>;
  const sc = ric.scenario;
  return (
    <div className="ric-obs">
      <div className="ue-now">
        <span>profile <b>{sc.profile ?? '—'}</b></span><span>isolation <b>{sc.isolation ?? '—'}</b></span><span>state <b>{sc.state ?? '—'}</b></span>
        <span>RAN functions <b className="mono">{(sc.ranFunctions ?? []).join(',') || '—'}</b></span>
        <span>control <b>{sc.controlPolicy?.allowWrite ? (sc.controlPolicy.allowedStyles ?? []).join(' / ') || 'write' : 'read-only'}</b></span>
      </div>
      {Object.entries(ric.nodes).map(([nid, n]) => {
        const pods = n.view?.observedBy ?? [];
        const connected = n.e2ConnectionStatus === 'CONNECTED';
        return (
          <div key={nid} className="inst-row">
            <span className="inst"><span className={`dot ${connected ? 'ok' : 'bad'}`} /><b className="mono">{n.meid}</b><span className="muted"> · {n.e2ConnectionStatus ?? '?'} · 訂閱 {n.subscriptionCount == null ? '查不到' : n.subscriptionCount}</span>{n.degraded?.length ? <span style={{ color: 'var(--warning, #e6a23c)' }}> ⚠ RIC 端異常:{n.degraded.join(', ')}</span> : null}</span>
            {pods.length === 0 ? <span className="inst"><span className="dot warning" /><span className="muted">無 xApp pod 觀測</span></span>
              : pods.map((p) => <span key={p.name} className="inst" title={p.podIP}><span className={`dot ${p.ready && p.phase === 'Running' ? 'ok' : 'warning'}`} /><b className="mono">{p.name}</b><span className="muted"> · {p.phase}{p.ready ? '' : ' · not ready'}</span></span>)}
          </div>
        );
      })}
    </div>
  );
}
