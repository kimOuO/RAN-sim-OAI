'use client';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { BarChart } from '@/components/charts/BarChart';
import { ColumnChart } from '@/components/charts/ColumnChart';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import { Panel } from '@/components/dashboard/Panel';
import { RangeBar } from '@/components/dashboard/RangeBar';
import { RanRuntimePanel } from '@/components/dashboard/RanRuntimePanel';
import { RicCommandTimeline } from '@/components/dashboard/RicCommandTimeline';
import { StatTile } from '@/components/dashboard/StatTile';
import { UeDetail } from '@/components/dashboard/UeDetail';
import { UeSmallMultiples } from '@/components/dashboard/UeSmallMultiples';
import { STATUS } from '@/config';
import { useRunDashboardPage } from '@/hooks/feature/useRunDashboardPage';
import { fmtSimTime } from '@/hooks/feature/kpmDerive';

export default function RunDashboardPage() {
  const { id } = useParams<{ id: string }>();
  const p = useRunDashboardPage(id);
  if (p.error) return <p className="err">{p.error.message}</p>;
  if (!p.run) return <p className="muted">載入 run…</p>;
  const l = p.latest; const s = p.stats.now, s0 = p.stats.prev;
  const d = (a: number | null, b: number | null) => (a != null && b != null ? a - b : null);
  const cellBars = p.cells.filter((c) => l?.per_cell[c]).map((c) => ({ label: c, value: l!.per_cell[c].prb_pct_dl, color: p.color[c], sub: `${p.ueRows.filter((u) => u.k.serving_cell === c).length} UE` }));
  const rawTable = l ? <table><thead><tr><th>UE</th><th>serving</th><th className="num">RSRP</th><th className="num">SINR</th><th className="num">MCS</th><th className="num">PRB</th><th className="num">Thp DL</th><th className="num">Thp UL</th><th className="num">RLC delay</th><th className="num">PDCP DL</th><th className="num">rank</th><th className="num">5QI</th></tr></thead>
    <tbody>{p.ueRows.map((u) => <tr key={u.id}><td className="mono">{u.id}</td><td className="mono" style={{ color: u.color }}>{u.k.serving_cell}</td><td className="num">{u.k.rsrp_dbm.toFixed(1)}</td><td className="num">{u.k.sinr_db.toFixed(1)}</td><td className="num">{u.k.mcs_dl}</td><td className="num">{u.k.rb_width_dl}</td><td className="num">{u.k.throughput_dl_mbps.toFixed(2)}</td><td className="num">{u.k.throughput_ul_mbps.toFixed(2)}</td><td className="num">{u.k.rlc_sdu_delay_dl_ms.toFixed(1)}</td><td className="num">{u.k.pdcp_sdu_volume_dl}</td><td className="num">{u.k.mimo_rank}</td><td className="num">{u.k.qos_5qi}</td></tr>)}</tbody></table> : null;
  return (
    <>
      <header className="runhead">
        <div><div className="crumbs"><Link href="/runs">Runs</Link> / <span className="mono">{p.run.scene_run_uuid.slice(-12)}</span></div><h1>{p.sceneName || p.run.f_scene_uuid}</h1></div>
        <span className={`pill ${p.run.status}`}>{p.run.status}</span>
        <span className="muted">{p.run.mode} · {p.run.speed_x}× · sim_dt {p.run.sim_dt_ms} ms{l ? ` · sim-time ${fmtSimTime(l.sim_time_ms / 1000)}` : ''}</span>
        <span className="sp" /><nav className="sub"><Link href={`/runs/${id}/events`}>事件流</Link><Link href={`/runs/${id}/playback`}>回放</Link></nav>
      </header>
      <RangeBar range={p.range} setRange={p.setRange} live={p.live} windows={p.view.length} />
      <div className="stats">
        <StatTile label="附著 UE" value={s.ue} digits={0} delta={d(s.ue, s0.ue)} />
        <StatTile label="平均 SINR" value={s.sinr} unit=" dB" delta={d(s.sinr, s0.sinr)} tone={s.sinr == null ? undefined : s.sinr >= 10 ? 'good' : s.sinr >= 0 ? 'warning' : 'critical'} />
        <StatTile label="Σ DL 吞吐" value={s.thp} unit=" Mb/s" delta={d(s.thp, s0.thp)} />
        <StatTile label="平均 PRB DL" value={s.prb} unit="%" delta={d(s.prb, s0.prb)} tone={s.prb != null && s.prb > 85 ? 'serious' : undefined} />
        <StatTile label="平均 MCS" value={s.mcs} digits={1} delta={d(s.mcs, s0.mcs)} />
        <StatTile label="換手" value={p.hoOk.length} digits={0} foot={`RLF ${p.rlf.length}`} tone={p.rlf.length ? 'serious' : undefined} />
        <StatTile label="RIC 命令" value={p.controls.length} digits={0} foot={p.e2?.sctp_link.connected ? 'E2 connected' : 'E2 down'} tone={p.e2?.sctp_link.connected ? 'good' : 'critical'} />
      </div>
      <div className="grid">
        <Panel title="PRB 使用率 DL · per cell" sub="RRU.PrbTotDl" span={6} table={<table><thead><tr><th>cell</th><th className="num">PRB DL %</th></tr></thead><tbody>{cellBars.map((b) => <tr key={b.label}><td className="mono">{b.label}</td><td className="num">{b.value.toFixed(1)}</td></tr>)}</tbody></table>}>
          <TimeSeriesChart series={p.charts.prbDl} unit="%" yMin={0} yMax={100} xLabels={p.xLabels} /></Panel>
        <Panel title="當下 cell 負載" sub={l ? `window ${l.window_index}` : undefined} span={3}><BarChart bars={cellBars} unit="%" max={100} /></Panel>
        <Panel title="每 cell UE 數" span={3}><TimeSeriesChart series={p.charts.ueCount} yMin={0} xLabels={p.xLabels} digits={0} legend={false} /></Panel>
        <Panel title="DL 吞吐 · per cell" sub="Σ UE throughput_dl" span={4}><TimeSeriesChart series={p.charts.thpDl} unit="" yMin={0} xLabels={p.xLabels} digits={2} /></Panel>
        <Panel title="平均 SINR · per cell" span={4}><TimeSeriesChart series={p.charts.sinr} unit="" yMin={-10} yMax={40} xLabels={p.xLabels} /></Panel>
        <Panel title="PRB 使用率 UL · per cell" sub="RRU.PrbTotUl" span={4}><TimeSeriesChart series={p.charts.prbUl} unit="%" yMin={0} yMax={100} xLabels={p.xLabels} /></Panel>
        <Panel title="RAN 模擬執行狀況" sub="UE driver / DU / E2" span={6}><RanRuntimePanel run={p.run} du={p.duTick} cells={p.duCells} ue={p.ueDriver} e2={p.e2} /></Panel>
        <Panel title="換手 / RLF · 每分鐘" span={3}><ColumnChart groups={[{ name: 'HO', color: STATUS.good, cols: p.eventBars.ho.map((b) => ({ label: fmtSimTime(b.x0), value: b.n })) }, { name: 'RLF', color: STATUS.critical, cols: p.eventBars.rlf.map((b) => ({ label: fmtSimTime(b.x0), value: b.n })) }]} /></Panel>
        <Panel title="SINR 分布(當下)" sub={`${p.ueRows.length} UE`} span={3}><ColumnChart groups={[{ name: 'UE', color: 'var(--cyan)', cols: p.sinrHist.map((b) => ({ label: `${b.x0}`, value: b.n })) }]} unit=" UE" /></Panel>
        <Panel title="UE 逐一觀測" sub="SINR 走勢 + serving cell 色帶,點選看全指標" span={12} table={rawTable}>
          <UeSmallMultiples items={p.ueSmall} color={p.color} selected={p.selectedUe} onSelect={(u) => p.setSelectedUe(p.selectedUe === u ? null : u)} />
          {p.ueDetail && <UeDetail id={p.ueDetail.id} metrics={p.ueDetail.metrics} serving={p.ueDetail.serving} color={p.color} xLabels={p.xLabels} onClose={() => p.setSelectedUe(null)} />}
        </Panel>
        <Panel title="RIC 命令" sub={`${p.controls.length} 筆 · 落地前後 5 窗 PRB 對照`} span={6}><RicCommandTimeline items={p.commandImpact} /></Panel>
        <Panel title="設定快照 / 起停紀錄" span={6} defaultOpen={false}>
          <div className="kv2"><div><span className="rt-k">mode</span>{p.run.mode}</div><div><span className="rt-k">speed_x</span>{p.run.speed_x}</div><div><span className="rt-k">sim_dt</span>{p.run.sim_dt_ms} ms</div><div><span className="rt-k">duration</span>{p.run.duration_sec} s</div><div><span className="rt-k">cache</span><span className="mono small">{p.run.cache_path || '—'}</span></div></div>
          <ul className="events">{p.launches.map((x) => <li key={x.launch_request_uuid} className="run"><span className="mono">{x.launch_request_created_at.slice(5, 19).replace('T', ' ')}</span><span className="pill">{x.action}</span>{x.status}</li>)}</ul></Panel>
      </div>
    </>
  );
}
