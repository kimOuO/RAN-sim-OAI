import type { O1Observation } from '@/types/o1';
import { Panel } from './Panel';
import { o1Time } from './O1PmPanels';

export function O1CmPanel({ data }: { data: O1Observation }) {
  const cm = data.cm;
  const source = cm.source === 'o1' ? 'O1 目前讀值' : cm.source === 'snapshot' ? 'O1 最後觀測快照' : '目前劇本設定';
  const cells = cm.elements.flatMap((el) => el.cells.map((c) => ({ ...c, me: el.managed_element, gnb: el.gnb })));
  return <Panel title="CM · 網元與 cell 組態" sub={source} span={12}>
    <p className="muted small">{cm.source === 'scene' ? '本次沒有保留 O1 組態快照；下方顯示目前劇本設定，不能代表上次執行時的實際狀態。' : `來源：O1 adapter 管理資料 · 觀測時間 ${o1Time(cm.observed_at)}`}</p>
    {!cm.elements.length ? <p className="muted">尚無管理網元與組態資料。</p> : <>
      <div className="o1-me-grid">{cm.elements.map((el) => <div className="mini-panel" key={el.managed_element}><div className="mini-h">{el.gnb} · {el.unit_type}</div><b className="mono small">{el.managed_element}</b><div className="muted small">{el.cells.length} cell{el.vendor ? ` · ${el.vendor}` : ''}{el.software_version ? ` · ${el.software_version}` : ''}</div>{el.observed_at && <div className="muted small">觀測 {o1Time(el.observed_at)}</div>}</div>)}</div>
      <table className="tbl"><thead><tr><th>gNB / ME</th><th>Cell / Local ID</th><th>PLMN</th><th className="num">PCI</th><th className="num">TAC</th><th className="num">ARFCN DL</th><th className="num">BW DL/UL MHz</th><th className="num">PRB</th><th>管理狀態</th><th>運作狀態</th><th>Cell 狀態</th></tr></thead>
        <tbody>{cells.map((c) => <tr key={`${c.me}:${c.dn}`}><td>{c.gnb}<div className="mono muted small">{c.me}</div></td><td className="mono small" title={c.dn}>{c.dn?.split(',').at(-1) ?? '—'}<div className="muted">local {c.local_cell_id ?? '—'} · {c.kind}</div></td><td className="mono">{c.plmn.join(', ') || '—'}</td><td className="num">{c.nRPCI ?? '—'}</td><td className="num">{c.nRTAC ?? '—'}</td><td className="num">{c.arfcnDL ?? '—'}</td><td className="num">{c.bSChannelBwDL ?? '—'} / {c.bSChannelBwUL ?? '—'}</td><td className="num">{c.numberOfRBs ?? '—'}</td><td>{c.administrativeState ?? '未觀測'}</td><td>{c.operationalState ?? '未觀測'}</td><td>{c.cellState ?? '未觀測'}</td></tr>)}</tbody></table>
      {cm.elements.some((el) => el.jobs.length) && <details className="o1-report"><summary>PM 量測工作 · PerfMetricJob</summary><table className="tbl"><thead><tr><th>管理網元</th><th>彙整 / 上報週期</th><th>啟用量測項目</th></tr></thead><tbody>{cm.elements.flatMap((el) => el.jobs.map((job) => <tr key={`${el.managed_element}:${job.dn}`}><td className="mono small">{el.managed_element}</td><td>{job.granularity_sec ?? '—'} / {job.reporting_sec ?? '—'} s</td><td><div className="chips">{job.metrics.map((m) => <span className="chip mono" key={m}>{m}</span>)}</div></td></tr>))}</tbody></table></details>}
    </>}
    <p className="muted small">此頁提供組態觀測。後端目前支援調整 PM 量測項目；頻寬寫入只記錄請求，尚未改變模擬頻寬，adapter 重啟會重設 CM 修改。</p>
  </Panel>;
}
