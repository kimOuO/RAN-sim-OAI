'use client';
import { useMemo, useState } from 'react';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import { SERIES } from '@/config';
import type { O1Observation } from '@/types/o1';
import { Panel } from './Panel';

export const o1Time = (value: string | null | undefined) => value ? new Date(value).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei', hour12: false }) : '—';
export const o1Number = (value: number | null | undefined, digits = 1) => value == null ? '—' : value.toLocaleString('zh-TW', { maximumFractionDigits: digits });
export const o1Http = (status: number | null) => status == null ? '未取得回覆' : `HTTP ${status}`;
export const o1Accepted = (status: number | null) => status != null && status >= 200 && status < 300;

const METRICS = [
  { key: 'prb_pct_dl', title: 'PM · PRB 使用率 DL', unit: '%', max: 100 },
  { key: 'throughput_dl_mbps', title: 'PM · 下行吞吐量', unit: ' Mb/s', max: undefined },
  { key: 'connected_ues', title: 'PM · 附著 UE', unit: '', max: undefined },
] as const;
const metricUnit = (key: string) => key.startsWith('DRB.UEThp') ? ' kbit/s' : key.startsWith('RRU.PrbTot') ? '%' : '';

export function O1PmPanels({ data }: { data: O1Observation }) {
  const [range, setRange] = useState(0);
  const [selectedCell, setSelectedCell] = useState('');
  const [selectedFile, setSelectedFile] = useState('');
  const trend = data.pm.trend;
  const allCells = useMemo(() => [...new Set(trend.flatMap((p) => p.cells.map((c) => c.cell_id)))].sort(), [trend]);
  const latestTime = trend.at(-1)?.at_sim_ms ?? 0;
  const view = trend.filter((p) => !range || p.at_sim_ms >= latestTime - range * 1000);
  const cells = allCells.filter((c) => !selectedCell || c === selectedCell);
  const latest = trend.at(-1);
  const fileKey = (f: { managed_element: string; filename: string }) => `${f.managed_element}:${f.filename}`;
  const files = [...data.pm.files].reverse();
  const report = files.find((f) => fileKey(f) === selectedFile) ?? files.find((f) => f.rows.length) ?? files[0];
  const dtTable = <table className="tbl"><thead><tr><th>Cell</th><th className="num">UE</th><th className="num">DL Mb/s</th><th className="num">UL Mb/s</th><th className="num">PRB DL %</th></tr></thead>
    <tbody>{(latest?.cells ?? []).filter((c) => !selectedCell || c.cell_id === selectedCell).map((c) => <tr key={c.cell_id}><td className="mono">{c.cell_id}</td><td className="num">{c.connected_ues}</td><td className="num">{o1Number(c.throughput_dl_mbps, 2)}</td><td className="num">{o1Number(c.throughput_ul_mbps, 2)}</td><td className="num">{o1Number(c.prb_pct_dl)}</td></tr>)}</tbody></table>;
  return <>
    <div className="o1-section span-12">
      <div><b>PM · 效能量測</b><p className="muted small">趨勢來源：DT 量測歸檔 · 橫軸為劇本時間 · 與下方 O1 週期彙整檔分別呈現</p></div>
      <div className="filters">
        <select aria-label="PM cell 篩選" value={selectedCell} onChange={(e) => setSelectedCell(e.target.value)}><option value="">全部 cell</option>{allCells.map((c) => <option key={c}>{c}</option>)}</select>
        <select aria-label="PM 趨勢範圍" value={range} onChange={(e) => setRange(Number(e.target.value))}><option value={0}>全部可用資料</option><option value={300}>最近 5 分鐘</option><option value={60}>最近 1 分鐘</option></select>
      </div>
    </div>
    {METRICS.map((metric) => <Panel key={metric.key} title={metric.title} sub="DT 量測 · 每 cell" span={4} table={dtTable}>
      <TimeSeriesChart yMin={0} yMax={metric.max} height={190} unit={metric.unit} xLabels={view.map((p) => p.at_sim_ms / 1000)}
        series={cells.map((cell) => ({ key: cell, label: cell, color: SERIES[allCells.indexOf(cell) % SERIES.length],
          points: view.map((p, i) => ({ x: i, y: p.cells.find((c) => c.cell_id === cell)?.[metric.key] ?? null })) }))} />
    </Panel>)}
    <Panel title="PM · 最新 cell 量測" sub={latest ? `DT 歸檔 · ${o1Time(new Date(latest.wall_time_ms).toISOString())}` : 'DT 歸檔'} span={12}>
      {latest ? dtTable : <p className="muted">本次執行尚無 DT 量測資料。</p>}
    </Panel>
    <Panel title="PM · O1 彙整檔與量測內容" sub={`${files.length} 份 · 依實際時間彙整`} span={12}>
      <p className="muted small">O1 PM 預設每 900 秒（實際時間 15 分鐘）產檔。不完整區間可能標記 suspect；HTTP 202 表示 VES 接受通知，SMO 取檔與入庫狀態尚未查證。</p>
      {!files.length ? <div className="empty-state"><b>尚無 O1 PM 檔案紀錄</b><span className="muted">尚未到彙整時間、未啟用 O1，或歷史紀錄未保留時，這裡會保持空白。</span></div> : <>
        <div className="o1-scroll"><table className="tbl"><thead><tr><th>完成時間</th><th>管理網元</th><th>PM 檔案</th><th>週期</th><th>資料完整性</th><th>VES 通知</th><th>內容</th></tr></thead>
          <tbody>{files.map((f) => <tr key={fileKey(f)} className={report === f ? 'o1-selected' : ''}><td className="mono small">{o1Time(f.end_time)}</td><td className="mono small">{f.managed_element}</td><td className="mono small o1-file">{f.filename}</td><td>{f.duration_sec == null ? '—' : `${f.duration_sec} s`}</td>
            <td><span className={f.suspect === true ? 'warn' : f.suspect === false ? 'ok' : 'muted'}>{f.suspect == null ? 'XML 未保留，無法判定' : f.suspect ? 'suspect · 不完整' : '完整'}</span></td>
            <td className={o1Accepted(f.http_status) ? 'ok' : 'muted'}>{o1Http(f.http_status)}</td><td><button className="ghost" onClick={() => setSelectedFile(fileKey(f))}>{f.rows.length ? `查看 ${f.rows.length} cell` : '查看紀錄'}</button></td></tr>)}</tbody></table></div>
        {report && <div className="o1-report"><b className="small mono">{report.filename}</b>{!report.rows.length ? <p className="muted small">此份歷史資料只保留傳送紀錄，無法還原 XML 內的量測值與 suspect 標記。後續執行會保存實際量測內容。</p> :
          <table className="tbl"><thead><tr><th>量測物件</th><th>指標</th><th className="num">數值</th><th>完整性</th></tr></thead><tbody>{report.rows.flatMap((r) => Object.entries(r.metrics).map(([key, value]) => <tr key={`${r.object}:${key}`}><td className="mono small">{r.object}</td><td className="mono small">{key}</td><td className="num">{o1Number(value, 3)}{metricUnit(key)}</td><td className={r.suspect ? 'warn' : 'ok'}>{r.suspect ? 'suspect' : '完整'}</td></tr>))}</tbody></table>}</div>}
      </>}
    </Panel>
  </>;
}
