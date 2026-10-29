'use client';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Panel } from '@/components/dashboard/Panel';
import { RicObservationPanel } from '@/components/dashboard/RicObservationPanel';
import { RunSubNav } from '@/components/dashboard/RunSubNav';
import { StatTile } from '@/components/dashboard/StatTile';
import { statusLabel } from '@/hooks/feature/runStatus';
import { useRunRicPage } from '@/hooks/feature/useRunRicPage';
import { controlOrigin, controlOriginLabel, ctrlOk } from '@/hooks/feature/controlEvents';

const fmtT = (ms: number) => `${Math.floor(ms / 60000)}:${String(Math.floor((ms % 60000) / 1000)).padStart(2, '0')}`;
const detailText = (d: Record<string, unknown> | null) => (d ? Object.entries(d).filter(([k]) => !['id', 'recorded_at'].includes(k)).map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : String(v)}`).join(' · ') : '');

/** RIC 連線觀測與控制紀錄；依來源區分 RIC / xApp 指令和 RAN 自主 SON 事件。 */
export default function RicPage() {
  const { id } = useParams<{ id: string }>();
  const p = useRunRicPage(id);
  if (p.error) return <p className="err">{p.error.message}</p>;
  if (!p.run) return <p className="muted">載入…</p>;
  const s = p.stats;
  return (
    <>
      <header className="runhead">
        <div><div className="crumbs"><Link href="/runs">Runs</Link> / <Link href={`/runs/${id}`}>{p.sceneName}</Link></div><h1>RIC</h1></div>
        <span className={`pill ${p.run.status}`}>{statusLabel(p.run)}</span>
        <span className="muted">E2 node、訂閱、RIC / xApp 指令與 RAN 自主 SON 事件{p.live ? ' · 每 5 秒更新' : ''}</span>
        <span className="sp" /><RunSubNav id={id} />
      </header>
      <div className="stats">
        <StatTile label="控制指令與自主事件" value={s.n} digits={0} foot={`RIC / xApp ${s.ricN} · RAN 自主 SON ${s.sonN}${s.ricApplyN ? ` · RIC 指令落地 ${s.ricApplyN}` : ''}${s.otherN ? ` · 其他 ${s.otherN}` : ''} · 失敗 ${s.failed}`} />
        <StatTile label="整體成功率" value={s.okPct} unit="%" foot="含控制指令與 RAN 自主事件" tone={s.okPct == null ? undefined : s.okPct >= 95 ? 'good' : s.okPct >= 80 ? 'warning' : 'critical'} />
        <StatTile label="平均落地延遲" value={s.latMean} unit="ms" digits={0} foot={s.latMax != null ? `最大 ${s.latMax} ms` : '無延遲資料'} />
        <StatTile label="E2 node" value={p.nodes.length || Object.keys(p.ric?.nodes ?? {}).length} digits={0}
          foot={`${p.nodes.filter((n) => n.e2?.sctp_link?.connected).length} 個 SCTP 連線中`} />
      </div>
      <div className="grid">
        <Panel title="RIC 閘道 · E2 node · xApp" sub="RIC 端 k8s / e2mgr 視角(30 秒更新)" span={6}>
          {p.ricStatus === 'loading' && !p.ric ? <p className="muted">查詢 RIC 閘道…</p> : <RicObservationPanel ric={p.ric} />}
        </Panel>
        <Panel title="E2 連線與訂閱 · 每個 gNB" sub="DT 端 e2adapter / CU" span={6}>
          {!p.live ? <p className="muted">run 不在執行中,沒有即時 E2 狀態。</p> : !p.nodes.length ? <p className="muted">沒有 e2adapter 實例</p> :
            <table className="tbl"><thead><tr><th>E2 node</th><th>SCTP</th><th className="num">送出 PDU</th><th>RAN function</th><th>訂閱(xApp 請求)</th></tr></thead>
              <tbody>{p.nodes.map(({ inst, e2, subs }) => {
                const link = e2?.sctp_link as { connected?: boolean; target_host?: string; target_port?: number; pdu_sent_count?: number } | undefined;
                const setup = e2?.e2_setup as { accepted_ran_function_ids?: number[] } | undefined;
                return <tr key={inst.run_instance_uuid}>
                  <td className="mono">{inst.e2_node_id ?? inst.name}</td>
                  <td><span className={`dot ${link?.connected ? 'ok' : 'bad'}`} />{link ? (link.connected ? 'CONNECTED' : 'DOWN') : '—'}<span className="muted small"> {link ? `${link.target_host}:${link.target_port}` : ''}</span></td>
                  <td className="num">{link?.pdu_sent_count?.toLocaleString() ?? '—'}</td>
                  <td className="mono">{setup?.accepted_ran_function_ids?.join(', ') ?? '—'}</td>
                  <td>{subs == null ? <span className="muted">查不到</span> : subs.length === 0 ? <span className="muted">無</span> :
                    subs.map((x) => <div key={x.subscription_id} className="mono small">{x.service_model} RF{x.ran_function_id} · req {x.ric_req_id.requestor_id}/{x.ric_req_id.instance_id}
                      {x.action_definition?.report_period_ms ? ` · ${x.action_definition.report_period_ms} ms` : ''}{x.action_definition?.metrics ? ` · ${x.action_definition.metrics.length} 項量測` : ''}</div>)}</td>
                </tr>;
              })}</tbody></table>}
        </Panel>
        <Panel title="指令與自主事件來源" sub="區分 RIC / xApp 指令、RIC 落地結果、RAN 自主 SON 與其他來源" span={4}>
          {!s.bySource.length ? <p className="muted">尚無指令或自主事件</p> :
            <table className="tbl"><thead><tr><th>類別</th><th>來源</th><th className="num">筆數</th><th className="num">成功率</th></tr></thead>
              <tbody>{s.bySource.map(([src, v]) => <tr key={src}><td><span className={`tag ${controlOrigin(src)}`}>{controlOriginLabel(src)}</span></td><td className="mono">{src}</td><td className="num">{v.n}</td><td className="num">{((100 * v.ok) / v.n).toFixed(0)}%</td></tr>)}</tbody></table>}
        </Panel>
        <Panel title="指令與自主事件種類" span={8}>
          {!s.byAction.length ? <p className="muted">尚無指令或自主事件</p> :
            <div className="chips">{s.byAction.map(([a, n]) => <button key={a} className={`chip ${p.fAction === a ? 'on' : ''}`} onClick={() => p.setFAction(p.fAction === a ? '' : a)}>{a} · {n}</button>)}</div>}
        </Panel>
        <Panel title="控制指令與 RAN 自主事件" sub={`${p.shown.length} / ${p.all.length} 筆 · 新到舊`} span={12}>
          <div className="filters">
            <select aria-label="篩選來源類別" value={p.fOrigin} onChange={(e) => p.setFOrigin(e.target.value)}><option value="">全部類別</option><option value="ric">{controlOriginLabel('ric/')}</option><option value="ric_apply">{controlOriginLabel('son/ric_apply')}</option><option value="son">{controlOriginLabel('son/')}</option><option value="other">{controlOriginLabel('')}</option></select>
            <select aria-label="篩選事件來源" value={p.fSource} onChange={(e) => p.setFSource(e.target.value)}><option value="">全部來源</option>{p.sources.map((x) => <option key={x} value={x}>{controlOriginLabel(x)} · {x}</option>)}</select>
            <select aria-label="篩選事件種類" value={p.fAction} onChange={(e) => p.setFAction(e.target.value)}><option value="">全部種類</option>{p.actions.map((x) => <option key={x}>{x}</option>)}</select>
            <select aria-label="篩選事件結果" value={p.fOutcome} onChange={(e) => p.setFOutcome(e.target.value)}><option value="">全部結果</option>{p.outcomes.map((x) => <option key={x}>{x}</option>)}</select>
          </div>
          {!p.shown.length ? <div className="empty-state"><b>沒有符合的指令或自主事件</b><span className="muted">RIC / xApp 下發指令與 RAN 自主 SON 行為依來源分別標示；可調整上方篩選查看。</span></div> :
            <table className="tbl"><thead><tr><th>劇本時間</th><th>類別</th><th>來源</th><th>動作／事件</th><th>目標</th><th>E2 node</th><th>結果</th><th className="num">落地延遲</th><th>細節</th></tr></thead>
              <tbody>{p.shown.map((e) => <tr key={e.run_control_event_uuid}>
                <td className="mono">{fmtT(e.at_sim_ms)}</td><td><span className={`tag ${controlOrigin(e.source)}`}>{controlOriginLabel(e.source)}</span></td><td className="mono">{e.source}</td><td className="mono"><b>{e.action_type}</b></td>
                <td className="mono">{e.target}</td><td className="mono small">{e.meid ?? e.node_id ?? '—'}</td>
                <td><span className={`dot ${ctrlOk(e.outcome) ? 'good' : e.outcome === 'pending' ? 'warning' : 'critical'}`} />{e.outcome}</td>
                <td className="num">{e.landing_latency_ms != null ? `${e.landing_latency_ms} ms` : '—'}</td>
                <td className="small muted detail-cell" title={detailText(e.detail)}>{detailText(e.detail)}</td>
              </tr>)}</tbody></table>}
        </Panel>
      </div>
    </>
  );
}
