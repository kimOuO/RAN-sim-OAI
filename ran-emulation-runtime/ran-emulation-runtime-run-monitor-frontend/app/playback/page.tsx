'use client';
import { ExecutionCard } from '@/components/playback/ExecutionCard';
import { usePlaybackLibrary } from '@/hooks/feature/usePlaybackLibrary';

/** 回放清單:先看清楚每次執行的時間、劇本、組別、時長與場景,再選一次進入回放 */
export default function PlaybackLibraryPage() {
  const p = usePlaybackLibrary();
  return (
    <>
      <header className="pagehead"><h1>回放</h1><span className="muted">{p.rows.length} / {p.total} 次執行 · 每個劇本保留最近 3 次</span></header>
      <div className="toolbar">
        <div className="chips">
          <button className={`chip ${!p.cat ? 'on' : ''}`} onClick={() => p.setCat('')}>全部組別</button>
          {p.categories.map((c) => <button key={c} className={`chip ${p.cat === c ? 'on' : ''}`} onClick={() => p.setCat(c)}>{c}</button>)}
        </div>
        <select value={p.days} onChange={(e) => p.setDays(Number(e.target.value))}><option value={0}>全部時間</option><option value={1}>最近 1 天</option><option value={7}>最近 7 天</option><option value={30}>最近 30 天</option></select>
        <input placeholder="搜尋劇本…" value={p.q} onChange={(e) => p.setQ(e.target.value)} />
      </div>
      {p.error && <p className="err">{p.error.message}</p>}
      {p.status === 'loading' && !p.total && <p className="muted">載入執行紀錄…</p>}
      <div className="exec-grid">{p.rows.map((r) => <ExecutionCard key={`${r.e.f_scene_run_uuid}-${r.e.run_seq}`} e={r.e} name={r.name} category={r.category} mode={r.mode} tree={p.trees[r.sceneUuid]} latest={r.latest} />)}</div>
      {p.status === 'success' && !p.rows.length && <div className="empty-state"><b>沒有符合的執行紀錄</b><span className="muted">調整組別、時間或搜尋條件。</span></div>}
    </>
  );
}
