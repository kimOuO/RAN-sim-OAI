'use client';
import Link from 'next/link';
import { RunSubNav } from '@/components/dashboard/RunSubNav';
import { useParams } from 'next/navigation';
import { ColumnChart } from '@/components/charts/ColumnChart';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import { GnbLoadBoard } from '@/components/dashboard/GnbLoadBoard';
import { Panel } from '@/components/dashboard/Panel';
import { RangeBar } from '@/components/dashboard/RangeBar';
import { RanRuntimePanel } from '@/components/dashboard/RanRuntimePanel';
import { BeamUsagePanel } from '@/components/dashboard/BeamUsagePanel';
import { RicObservationPanel } from '@/components/dashboard/RicObservationPanel';
import { RicCommandTimeline } from '@/components/dashboard/RicCommandTimeline';
import { StatTile } from '@/components/dashboard/StatTile';
import { UeDetail } from '@/components/dashboard/UeDetail';
import { UeSmallMultiples } from '@/components/dashboard/UeSmallMultiples';
import { STATUS } from '@/config';
import { useRunDashboardPage } from '@/hooks/feature/useRunDashboardPage';
import { fmtSimTime } from '@/hooks/feature/kpmDerive';
import { lastResultLabel, statusLabel } from '@/hooks/feature/runStatus';

export default function RunDashboardPage() {
  const { id } = useParams<{ id: string }>();
  const p = useRunDashboardPage(id);
  if (p.error) return <p className="err">{p.error.message}</p>;
  if (!p.run) return <p className="muted">載入 run…</p>;
  const l = p.latest; const s = p.stats.now, s0 = p.stats.prev;
  const d = (a: number | null, b: number | null) => (a != null && b != null ? a - b : null);
  const rawTable = l ? <table><thead><tr><th>UE</th><th>serving</th><th className="num">RSRP</th><th className="num">SINR</th><th className="num">MCS DL/UL</th><th className="num">PRB DL/UL</th><th className="num">UL SINR</th><th className="num">Thp DL</th><th className="num">Thp UL</th><th className="num">RLC delay</th><th className="num">PDCP DL</th><th className="num">rank</th><th className="num">5QI</th></tr></thead>
    <tbody>{p.ueRows.map((u) => <tr key={u.id}><td className="mono">{u.id}</td><td className="mono" style={{ color: u.color }}>{u.k.serving_cell}</td><td className="num">{u.k.rsrp_dbm.toFixed(1)}</td><td className="num">{u.k.sinr_db.toFixed(1)}</td><td className="num">{u.k.mcs_dl}/{u.k.mcs_ul ?? '—'}</td><td className="num">{u.k.rb_width_dl}/{u.k.rb_width_ul ?? '—'}</td><td className="num">{u.k.ul_sinr_db != null ? u.k.ul_sinr_db.toFixed(1) : '—'}</td><td className="num">{u.k.throughput_dl_mbps.toFixed(2)}</td><td className="num">{u.k.throughput_ul_mbps.toFixed(2)}</td><td className="num">{u.k.rlc_sdu_delay_dl_ms.toFixed(1)}</td><td className="num">{u.k.pdcp_sdu_volume_dl}</td><td className="num">{u.k.mimo_rank}</td><td className="num">{u.k.qos_5qi}</td></tr>)}</tbody></table> : null;
  return (
    <>
      <header className="runhead">
        <div><div className="crumbs"><Link href="/runs">Runs</Link> / <span className="mono">{p.run.scene_run_uuid.slice(-12)}</span></div><h1>{p.sceneName || p.run.f_scene_uuid}</h1></div>
        <span className={`pill ${p.run.status}`}>{statusLabel(p.run)}</span>{lastResultLabel(p.run) && <span className="muted small"> {lastResultLabel(p.run)}</span>}
        {p.topo.gnb > 0 && <span className="muted">{p.topo.gnb} gNB · {p.topo.du} DU · {p.topo.cell} cell{p.ueDriver && Number.isFinite(p.ueDriver.ue_count) ? ` · ${p.ueDriver.ue_count} UE` : ''}</span>}
        <span className="muted">通道 {p.run.mode === 'cached' ? '快取' : '即時'} · {p.run.speed_x}× · sim_dt {p.run.sim_dt_ms} ms{l ? ` · sim-time ${fmtSimTime(l.sim_time_ms / 1000)}` : ''}</span>
        <span className="sp" /><RunSubNav id={id} />
      </header>
      <RangeBar range={p.range} setRange={p.setRange} live={p.live} windows={p.view.length} />
      <div className="stats">
        <StatTile label="附著 UE" value={s.ue} digits={0} delta={d(s.ue, s0.ue)} />
        <StatTile label="平均 SINR" value={s.sinr} unit=" dB" delta={d(s.sinr, s0.sinr)} tone={s.sinr == null ? undefined : s.sinr >= 10 ? 'good' : s.sinr >= 0 ? 'warning' : 'critical'} />
        <StatTile label="Σ DL 吞吐" value={s.thp} unit=" Mb/s" delta={d(s.thp, s0.thp)} />
        <StatTile label="平均 PRB DL" value={s.prb} unit="%" delta={d(s.prb, s0.prb)} tone={s.prb != null && s.prb > 85 ? 'serious' : undefined} />
        <StatTile label="平均 MCS" value={s.mcs} digits={1} delta={d(s.mcs, s0.mcs)} />
        <StatTile label="換手" value={p.hoOk.length} digits={0} foot={`RLF ${p.rlf.length}`} tone={p.rlf.length ? 'serious' : undefined} />
        <StatTile label="RIC / xApp 指令" value={p.controlCounts.ric} digits={0} foot={`RAN 自主 SON ${p.controlCounts.son}${p.controlCounts.ric_apply ? ` · RIC 指令落地 ${p.controlCounts.ric_apply}` : ''}${p.controlCounts.other ? ` · 其他 ${p.controlCounts.other}` : ''}`} />
      </div>
      <div className="grid">
        <Panel title="PRB 使用率 DL · gNB → cell" sub={`RRU.PrbTotDl · ${l ? `window ${l.window_index}` : ''}`} span={8} table={<table><thead><tr><th>gNB</th><th>cell</th><th className="num">PRB DL %</th><th className="num">PRB UL %</th><th className="num">UE</th></tr></thead><tbody>{p.gnbGroups.flatMap((g) => g.cells.map((c) => <tr key={c}><td className="mono">{g.gnb}</td><td className="mono">{c}</td><td className="num">{(l?.per_cell[c]?.prb_pct_dl ?? 0).toFixed(1)}</td><td className="num">{(l?.per_cell[c]?.prb_pct_ul ?? 0).toFixed(1)}</td><td className="num">{p.cellUeCount[c] ?? 0}</td></tr>))}</tbody></table>}>
          <GnbLoadBoard groups={p.gnbGroups} latest={l} color={p.color} ueCount={p.cellUeCount} /></Panel>
        <Panel title="PRB 使用率 UL · gNB → cell" sub="RRU.PrbTotUl" span={4}><GnbLoadBoard groups={p.gnbGroups} latest={l} color={p.color} ueCount={p.cellUeCount} metric="prb_pct_ul" label="PRB UL" /></Panel>
        <Panel title="PRB DL 走勢 · per cell" span={6}><TimeSeriesChart series={p.charts.prbDl} unit="%" yMin={0} yMax={100} xLabels={p.xLabels} /></Panel>
        <Panel title="PRB UL 走勢 · per cell" span={6}><TimeSeriesChart series={p.charts.prbUl} unit="%" yMin={0} yMax={100} xLabels={p.xLabels} /></Panel>
        <Panel title="DL 吞吐 · per cell" sub="Σ UE DRB.UEThpDl" span={4}><TimeSeriesChart series={p.charts.thpDl} unit=" Mb/s" yMin={0} xLabels={p.xLabels} digits={2} /></Panel>
        <Panel title="UL 吞吐 · per cell" sub="Σ UE DRB.UEThpUl" span={4}><TimeSeriesChart series={p.charts.thpUl} unit=" Mb/s" yMin={0} xLabels={p.xLabels} digits={2} /></Panel>
        <Panel title="平均 SINR · per cell" span={4}><TimeSeriesChart series={p.charts.sinr} unit=" dB" yMin={-10} yMax={40} xLabels={p.xLabels} /></Panel>
        <Panel title="RLC SDU delay DL · per cell 平均" sub="DRB.RlcSduDelayDl" span={4}><TimeSeriesChart series={p.charts.rlcDelay} unit=" ms" yMin={0} xLabels={p.xLabels} /></Panel>
        <Panel title="平均 MCS · per cell" span={4}><TimeSeriesChart series={p.charts.mcs} yMin={0} yMax={28} xLabels={p.xLabels} /></Panel>
        <Panel title="每 cell UE 數" span={4}><TimeSeriesChart series={p.charts.ueCount} yMin={0} xLabels={p.xLabels} digits={0} /></Panel>
        <Panel title="RAN 模擬執行狀況" sub={p.runtimeGone ? 'per-run 容器已收掉 · 無即時資料' : p.perRun ? 'per-run 容器 · UE driver / DU / E2' : '共用容器 · UE driver / DU / E2'} span={6}>
          {p.runtimeGone
            ? <p className="muted">這個 run 已結束,per-run 容器(CU / DU / RU / UE / E2Adapter)已移除,沒有即時狀態可讀。歷史 KPM 與事件仍在上方各面板。</p>
            : <RanRuntimePanel run={p.run} du={p.duTick} cells={p.duCells} ue={p.ueDriver} e2={p.e2} e2Nodes={p.e2Nodes} instances={p.instances} owners={p.owners} />}
        </Panel>
        <Panel title="RIC 端觀測" sub="閘道登記 · E2 node 連線 · 觀測中的 xApp pod(30 s 更新)" span={6}><RicObservationPanel ric={p.ric} /></Panel>
        <Panel title="波束使用分佈" sub="每 cell 的 GoB 波束(色深 = 使用比例,數字 = 平均 SINR);O-RAN WG1 §4.6.4.1 每波束統計" span={6}><BeamUsagePanel cells={p.beamCells} /></Panel>
        <Panel title="換手 / RLF · 每分鐘" span={3}><ColumnChart groups={[{ name: 'HO', color: STATUS.good, cols: p.eventBars.ho.map((b) => ({ label: fmtSimTime(b.x0), value: b.n })) }, { name: 'RLF', color: STATUS.critical, cols: p.eventBars.rlf.map((b) => ({ label: fmtSimTime(b.x0), value: b.n })) }]} /></Panel>
        <Panel title="SINR 分布(當下)" sub={`${p.ueRows.length} UE`} span={3}><ColumnChart groups={[{ name: 'UE', color: 'var(--cyan)', cols: p.sinrHist.map((b) => ({ label: `${b.x0}`, value: b.n })) }]} unit=" UE" /></Panel>
        <Panel title="UE 逐一觀測" sub="SINR 走勢 + serving cell 色帶,點選看全指標" span={12} table={rawTable}>
          <UeSmallMultiples items={p.ueSmall} color={p.color} selected={p.selectedUe} onSelect={(u) => p.setSelectedUe(p.selectedUe === u ? null : u)} />
          {p.ueDetail && <UeDetail id={p.ueDetail.id} metrics={p.ueDetail.metrics} serving={p.ueDetail.serving} color={p.color} xLabels={p.xLabels} last={p.ueDetail.last} onClose={() => p.setSelectedUe(null)} />}
        </Panel>
        <Panel title="控制指令與 RAN 自主事件" sub={`${p.controls.length} 筆 · 依來源分類 · 執行前後 5 窗 PRB 對照`} span={6}><RicCommandTimeline items={p.commandImpact} /></Panel>
        <Panel title="設定快照 / 起停紀錄" span={6} defaultOpen={false}>
          <div className="kv2"><div><span className="rt-k">mode</span>{p.run.mode}</div><div><span className="rt-k">speed_x</span>{p.run.speed_x}</div><div><span className="rt-k">sim_dt</span>{p.run.sim_dt_ms} ms</div><div><span className="rt-k">duration</span>{p.run.duration_sec} s</div><div><span className="rt-k">cache</span><span className="mono small">{p.run.cache_path || '—'}</span></div></div>
          <ul className="events">{p.launches.map((x) => <li key={x.launch_request_uuid} className="run"><span className="mono">{x.launch_request_created_at.slice(5, 19).replace('T', ' ')}</span><span className="pill">{x.action}</span>{x.status}</li>)}</ul></Panel>
      </div>
    </>
  );
}
