'use client';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Panel } from '@/components/dashboard/Panel';
import { StatTile } from '@/components/dashboard/StatTile';
import { O1PmPanels, o1Number, o1Time } from '@/components/dashboard/O1PmPanels';
import { O1CmPanel } from '@/components/dashboard/O1CmPanel';
import { O1FmPanels } from '@/components/dashboard/O1FmPanels';
import { RunSubNav } from '@/components/dashboard/RunSubNav';
import { statusLabel } from '@/hooks/feature/runStatus';
import { useRunO1Page } from '@/hooks/feature/useRunO1Page';

export default function O1Page() {
  const { id } = useParams<{ id: string }>();
  const p = useRunO1Page(id);
  if (p.error) return <p className="err">{p.error.message}</p>;
  if (!p.run) return <p className="muted">載入…</p>;
  const data = p.observation;
  const rows = data?.containers ?? [], adapters = rows.filter((r) => r.role === 'o1adapter');
  const latest = data?.pm.trend.at(-1);
  const knownMes = new Set([...(data?.scope.mes.flatMap((m) => [m.cucp, ...(m.dus?.map((d) => d.me) ?? [m.du])]) ?? []), ...adapters.map((a) => a.managed_element), ...(data?.cm.elements.filter((e) => e.source === 'o1').map((e) => e.managed_element) ?? [])]);
  const running = adapters.filter((r) => r.status === 'running').length;
  const live = p.run.status === 'running';
  return <div className="o1-page">
    <header className="runhead"><div><div className="crumbs"><Link href="/runs">Runs</Link> / <Link href={`/runs/${id}`}>{p.sceneName}</Link></div><h1>O1 / SMO</h1></div>
      <span className={`pill ${p.run.status}`}>{statusLabel(p.run)}</span><span className="muted">PM 效能 · CM 組態 · FM 告警 · 每 10 秒更新</span><span className="sp" /><RunSubNav id={id} /></header>
    <div className="toolbar o1-toolbar"><span className={`pill ${live ? 'running' : 'idle'}`}>{live ? '執行中觀測' : '歷史資料'}</span><span className="muted small">查詢時間 {o1Time(data?.observed_at)}</span><span className="sp" /><button onClick={p.refresh} disabled={p.loading}>{p.loading ? '更新中…' : '重新整理'}</button></div>
    {p.observationError && <p className="err" role="alert">O1 資料更新失敗：{p.observationError.message}。{data ? '下方保留上次成功資料。' : '請重新整理再試。'}</p>}
    {!data ? <p className="muted">讀取 O1 監控資料…</p> : <>
      <div className="stats">
        <StatTile label="O1 管理網元" value={knownMes.size} digits={0} foot={`${running} 個 adapter 運行中${live ? '' : ' · Run 已停止'}`} tone={running ? 'good' : undefined} />
        <StatTile label="DT 附著 UE" value={latest ? latest.cells.reduce((s, c) => s + c.connected_ues, 0) : null} digits={0} foot={live ? '最新 DT 量測' : '最後 DT 量測'} />
        <StatTile label="DT Σ DL 吞吐" value={latest ? latest.cells.reduce((s, c) => s + c.throughput_dl_mbps, 0) : null} unit=" Mb/s" foot={latest ? `UL ${o1Number(latest.cells.reduce((s, c) => s + c.throughput_ul_mbps, 0), 2)} Mb/s` : '尚無量測'} />
        <StatTile label="O1 PM 檔案" value={data.pm.files.length} digits={0} foot={`${data.pm.files.filter((f) => f.rows.length).length} 份保留量測內容`} />
        <StatTile label="目前 O1 活動告警" value={data.fm.current_verified ? data.fm.active.length : null} digits={0} tone={data.fm.current_verified ? data.fm.active.length ? 'serious' : 'good' : undefined} foot={data.fm.current_verified ? '全部 adapter 已讀取' : '目前狀態未查證'} />
      </div>
      {data.warnings.length > 0 && <div className="card o1-notice" role="status">{data.warnings.map((w) => <div className="warn small" key={w}>{w}</div>)}</div>}
      <div className="grid">
      <O1PmPanels data={data} />
      <O1CmPanel data={data} />
      <O1FmPanels data={data} />
      <Panel title="O1 管理端點與服務" sub={`${running} / ${adapters.length || knownMes.size} 個 adapter 運行中`} span={12} defaultOpen={false}>
        <p className="muted small">DT 服務與 VES 回覆狀態可在此查看；SMO 資料入庫尚未查證。Run 停止後管理端點不再提供服務。</p>
        {!adapters.length ? <p className="muted">此 Run 目前沒有 O1 adapter；Run 停止後服務會被移除。歷史傳送紀錄與可用快照列在上方。</p> :
          <div style={{ overflowX: 'auto' }}><table className="tbl"><thead><tr><th>gNB / 類型</th><th>Managed Element</th><th>狀態</th><th>NETCONF</th><th>SFTP</th><th>PM 週期</th><th>VES 接收端</th></tr></thead>
            <tbody>{adapters.map((r) => <tr key={r.name}><td>{r.gnb} / {r.unit_type}</td><td className="mono">{r.managed_element}</td><td><span className={`dot ${r.status === 'running' ? 'ok' : 'bad'}`} />{r.status}</td>
              <td className="mono">{r.host}:{r.netconf_port}</td><td className="mono">{r.host}:{r.sftp_port}</td><td>{r.pm_interval_sec ? `${r.pm_interval_sec} s` : '—'}</td><td className="mono small">{r.ves_url || '—'}</td></tr>)}</tbody></table></div>}
        <table className="tbl"><thead><tr><th>gNB</th><th>服務</th><th>狀態</th><th>啟動時間</th><th>重啟次數</th></tr></thead><tbody>{rows.map((r) => <tr key={r.name}><td>{r.gnb}</td><td className="mono">{r.name}</td><td>{r.status}</td><td>{r.started_at ? new Date(r.started_at).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' }) : '—'}</td><td>{r.restart_count}</td></tr>)}</tbody></table>
      </Panel>
      </div>
    </>}
  </div>;
}
