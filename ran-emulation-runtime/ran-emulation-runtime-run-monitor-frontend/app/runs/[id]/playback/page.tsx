'use client';
import Link from 'next/link';
import { Suspense, useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import { Panel } from '@/components/dashboard/Panel';
import { RunSubNav } from '@/components/dashboard/RunSubNav';
import { ExecutionCard } from '@/components/playback/ExecutionCard';
import { LabelControls } from '@/components/scene3d/LabelControls';
import { LiveScene3D } from '@/components/scene3d/LiveScene3D';
import { UeCards } from '@/components/scene3d/UeCards';
import { fmtSimTime } from '@/hooks/feature/kpmDerive';
import { usePlaybackLibrary } from '@/hooks/feature/usePlaybackLibrary';
import { usePlaybackPlayer, type TimelineMark } from '@/hooks/feature/usePlaybackPlayer';

const fmtDate = (ms: number | null | undefined) => (ms ? new Date(ms).toLocaleString('zh-TW', { hour12: false }) : '—');
const MARK_LABEL: Record<TimelineMark['kind'], string> = { ho: '換手', rlf: 'RLF', ric: 'RIC 命令', son: 'gNB SON' };

/** 回放:沒帶 ?seq= 先列這個 run 的每次執行(時間 / 時長 / 場景)讓使用者挑;帶了就進播放器 */
export default function PlaybackPage() {
  return <Suspense fallback={<p className="muted">載入…</p>}><PlaybackInner /></Suspense>;
}

function PlaybackInner() {
  const { id } = useParams<{ id: string }>();
  const seq = Number(useSearchParams().get('seq') || 0);
  return seq ? <Player id={id} seq={seq} /> : <RunExecutions id={id} />;
}

function RunExecutions({ id }: { id: string }) {
  const p = usePlaybackLibrary(id);
  const first = p.rows[0];
  return (
    <>
      <header className="runhead"><div><div className="crumbs"><Link href="/playback">回放</Link> / {first?.name ?? id.slice(-8)}</div><h1>選擇要回放的執行</h1></div><span className="sp" /><RunSubNav id={id} /></header>
      {p.status === 'loading' && !p.total && <p className="muted">載入執行紀錄…</p>}
      <div className="exec-grid">{p.rows.map((r) => <ExecutionCard key={r.e.run_seq} e={r.e} name={r.name} category={r.category} mode={r.mode} tree={p.trees[r.sceneUuid]} latest={r.latest} />)}</div>
      {p.status === 'success' && !p.rows.length && <div className="empty-state"><b>這個劇本沒有保留的執行紀錄</b><span className="muted">每個劇本只保留最近 3 次執行的資料。</span></div>}
    </>
  );
}

function Player({ id, seq }: { id: string; seq: number }) {
  const [idx, setIdx] = useState(0);
  const p = usePlaybackPlayer(id, seq, idx, setIdx);
  const v = p.v; const n = p.all.length;
  useEffect(() => { setIdx(0); }, [id, seq]);
  if (p.error) return <p className="err">{p.error.message}</p>;
  if (!n) return <p className="muted">{p.loading ? '載入這次執行的資料…' : '這次執行沒有封存的量測資料'}</p>;
  const total = p.tSec[n - 1] ?? 0, t0 = p.tSec[0] ?? 0;
  const sceneName = p.scene?.legacy_scenario_id || p.scene?.name || id.slice(-8);
  const chart = (title: string, sub: string, series: typeof p.charts.prb, unit: string, yMin?: number, yMax?: number) => (
    <Panel title={title} sub={sub} span={6}><TimeSeriesChart series={series} unit={unit} height={170} yMin={yMin} yMax={yMax} xLabels={p.tSec} cursor={idx} onPick={setIdx} /></Panel>);
  return (
    <>
      <header className="runhead">
        <div><div className="crumbs"><Link href="/playback">回放</Link> / <Link href={`/runs/${id}/playback`}>{sceneName}</Link> / 第 {seq} 次執行</div><h1>{sceneName}</h1></div>
        <span className="muted">{p.scene?.category ? `組別 ${p.scene.category} · ` : ''}{fmtDate(p.exec?.started_ms)} 開始 · 模擬 {fmtSimTime(total - t0)}{p.exec ? `(實際 ${fmtSimTime(p.exec.wall_sec)})` : ''}</span>
        <span className="sp" /><LabelControls mode={v.labelMode} setMode={v.setLabelMode} sites={v.showSites} setSites={v.setShowSites} /><RunSubNav id={id} />
      </header>

      <div className="card timeline">
        <div className="tl-row">
          <button className="mini" onClick={v.toggle} aria-label={v.playing ? '暫停' : '播放'}>{v.playing ? '❚❚' : '▶'}</button>
          <select value={v.rate} onChange={(e) => v.setRate(Number(e.target.value))}>{[1, 2, 5, 10, 30, 60].map((r) => <option key={r} value={r}>{r}× 速</option>)}</select>
          <b className="mono">{fmtSimTime(p.curT)}</b><span className="muted mono">/ {fmtSimTime(total)}</span>
          <span className="muted small">{Object.keys(p.cur?.per_ue ?? {}).length} UE · 至此 換手 {p.sofar.ho} · RLF {p.sofar.rlf} · 控制命令 {p.sofar.ctrl}</span>
          <span className="sp" /><span className="legend-inline small"><i className="mk ho" />換手 <i className="mk rlf" />RLF <i className="mk ric" />RIC <i className="mk son" />SON</span>
        </div>
        <div className="tl-track">
          <svg className="tl-marks" viewBox={`0 0 ${Math.max(1, n - 1)} 10`} preserveAspectRatio="none">
            {p.marks.map((m, k) => <line key={k} x1={m.i} x2={m.i} y1={m.kind === 'rlf' ? 0 : m.kind === 'ho' ? 3 : 6} y2={m.kind === 'rlf' ? 4 : m.kind === 'ho' ? 7 : 10} className={`mk ${m.kind}`} vectorEffect="non-scaling-stroke" />)}
          </svg>
          <input type="range" min={0} max={n - 1} value={idx} onChange={(e) => setIdx(Number(e.target.value))} aria-label="時間軸" />
        </div>
      </div>

      {v.tree && <div className="live3d-wrap playback3d"><div className="live3d">
        {v.hasSceneTime ? <LiveScene3D tree={v.tree} simNow={v.simNow} ueState={v.ueState} flashes={v.flashes} color={v.color} selected={v.selected} onSelect={v.setSelected} labelMode={v.labelMode} showSites={v.showSites} />
          : <p className="muted pad">這次執行沒有劇本時間(舊資料),無法畫 UE 位置。</p>}
      </div>
      <UeCards names={v.tree.ues.map((u) => u.name)} ueState={v.ueState} color={v.color} owners={v.owners} selected={v.selected} onSelect={v.setSelected} /></div>}

      <div className="grid">
        {chart('PRB 使用率 DL', '每 cell · 點圖可跳到該時間', p.charts.prb, '%', 0, 100)}
        {chart('下行吞吐', 'Σ UE · 每 cell', p.charts.thp, ' Mb/s')}
        {chart('附著 UE 數', '每 cell', p.charts.ues, '', 0)}
        {chart('平均 SINR', '每 cell', p.charts.sinr, ' dB')}
        <Panel title="事件" sub={`目前時間之前最近 ${p.recent.length} 筆 · 新到舊`} span={12}>
          {!p.recent.length ? <p className="muted">這個時間之前還沒有事件</p> :
            <ul className="cmd-list">{p.recent.map((m, k) => <li key={k} onClick={() => setIdx(m.i)} style={{ cursor: 'pointer' }}><i className={`mk ${m.kind}`} /><span className="mono">{fmtSimTime(m.t)}</span><span className={`tag ${m.kind}`}>{MARK_LABEL[m.kind]}</span><span className="mono">{m.label}</span></li>)}</ul>}
        </Panel>
      </div>
    </>
  );
}
