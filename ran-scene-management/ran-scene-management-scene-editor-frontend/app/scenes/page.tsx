'use client';
import Link from 'next/link';
import { useState } from 'react';
import { MONITOR_BASE_URL, SCENE_CATEGORIES } from '@/config';
import { useSceneListPage } from '@/hooks/feature/useSceneListPage';
import type { SceneRun } from '@/types/registry';

const catLabel = (k: string) => SCENE_CATEGORIES.find((c) => c.key === k)?.label ?? '其他';
export default function ScenesPage() {
  const p = useSceneListPage();
  const [name, setName] = useState('');
  return (
    <section className="shell page">
      <header className="pagehead"><h1>場景</h1><span className="muted">{p.counts.all ?? 0} 個</span><span className="sp" />
        <input placeholder="搜尋名稱 / 劇本 id" value={p.filter} onChange={(e) => p.setFilter(e.target.value)} />
        <form className="inline" onSubmit={(e) => { e.preventDefault(); if (name.trim()) { p.create(name.trim()); setName(''); } }}><input placeholder="新場景名稱" value={name} onChange={(e) => setName(e.target.value)} /><button className="primary" type="submit" disabled={p.busy === 'create'}>建立</button></form>
      </header>
      <div className="chips">{p.categories.map((c) => <button key={c.key} className={`chip ${p.category === c.key ? 'on' : ''}`} onClick={() => p.setCategory(c.key)}>{c.label} <span className="muted">{p.counts[c.key] ?? 0}</span></button>)}</div>
      {p.status === 'loading' && !p.scenes.length && <p className="muted">載入中…</p>}
      {p.error && <p className="err">{p.error.message}</p>}
      <div className="cards">
        {p.scenes.map(({ scene: s, category, runs }) => { const r = runs[0]; return (
          <article key={s.scene_uuid} className={`card cat-${category}`}>
            <div className="card-top"><span className="tag">{catLabel(category)}</span>{r && <span className={`pill ${r.status}`}>{r.status}</span>}</div>
            <h2><Link href={`/scenes/${s.scene_uuid}`}>{s.name}</Link></h2>
            <p className="muted small">{s.legacy_scenario_id ? `劇本 ${s.legacy_scenario_id}` : '手動建立'}{s.geometry_scene_id ? ` · 幾何 ${s.geometry_scene_id}` : ''} · 更新 {s.scene_updated_at.slice(5, 16).replace('T', ' ')}</p>
            {r ? <p className="small">{r.mode} · {r.speed_x}× · dt {r.sim_dt_ms} ms · {(r.duration_sec / 3600).toFixed(1)} h{r.mode === 'cached' ? (r.status === 'precomputing' ? '' : r.cache_path ? ' · 已預算' : ' · 未預算') : ''}</p> : <p className="muted small">尚無 run</p>}
            {r && r.status !== 'running' && r.status !== 'precomputing' && (
              <div className="runctl">
                <label><span>模式</span>
                  <select value={r.mode} disabled={p.busy === r.scene_run_uuid}
                          onChange={(e) => p.setMode(r, e.target.value as SceneRun['mode'])}>
                    <option value="live">live(即時)</option>
                    <option value="cached">cached(預算)</option>
                  </select></label>
                <label><span>倍速</span>
                  {/* 倍速只有 cached 有意義:live 每 tick 都要即時 ray tracing,實測
                      (18 UE × 3 cell、sim_dt 500 ms)只到約 1.6×,所以鎖 1×。
                      cached 的上限也不是無限 —— 同一組場景實測 5× 達成 4.99× 且丟包 0,
                      30× 只達成 27.3× 且丟了 1091 筆量測報告,所以 10× 以上標成吃力。 */}
                  <select value={r.speed_x}
                          disabled={r.mode === 'live' || !r.cache_path || p.busy === r.scene_run_uuid}
                          title={r.mode === 'live' ? 'live 模式即時運算,固定 1×' : !r.cache_path ? '先預算才能加速' : undefined}
                          onChange={(e) => p.setSpeed(r, Number(e.target.value))}>
                    {[1, 2, 5, 10, 20, 30].map((v) => <option key={v} value={v}>{v}×{v > 5 ? '(吃力)' : ''}</option>)}
                  </select></label>
              </div>)}
            {r && r.status === 'precomputing' && (() => { const s = p.precomp[r.scene_run_uuid]; const pr = s?.progress; return <div className="prog-row"><div className="prog"><i style={{ width: `${pr?.pct ?? 0}%` }} /></div><span className="muted small">{pr ? `${pr.pct.toFixed(1)}% · ${pr.rate_tps.toFixed(1)} t/s · 剩 ${Math.round(pr.eta_sec / 60)} 分` : (s?.state ?? '啟動中…')}</span></div>; })()}
            <footer>
              <Link href={`/scenes/${s.scene_uuid}`}><button>編輯</button></Link>
              {r && r.mode === 'cached' && !r.cache_path && r.status !== 'precomputing' && r.status !== 'running' && <button disabled={p.busy === r.scene_run_uuid} onClick={() => p.precompute(r)}>預算</button>}
              {r && r.status === 'precomputing' && <button className="danger" disabled={p.busy === r.scene_run_uuid} onClick={() => p.stopPrecompute(r)}>停止預算</button>}
              {r && r.status !== 'precomputing' && (r.status === 'running' ? <button className="danger" disabled={p.busy === r.scene_run_uuid} onClick={() => p.stop(r)}>停止</button> : <button className="primary" disabled={p.busy === r.scene_run_uuid || (r.mode === 'cached' && !r.cache_path)} title={r.mode === 'cached' && !r.cache_path ? '先預算' : undefined} onClick={() => p.start(r)}>{p.busy === r.scene_run_uuid ? '啟動中…' : '啟動'}</button>)}
              {r && (r.status === 'running' || r.status === 'stopped') && <a href={`${MONITOR_BASE_URL}/runs/${r.scene_run_uuid}`} target="_blank" rel="noreferrer"><button>監控 ↗</button></a>}
              <span className="sp" /><button className="ghost danger" disabled={!!p.busy} onClick={() => { if (confirm(`刪除場景 ${s.name}?`)) p.remove(s); }}>刪除</button>
            </footer>
          </article>); })}
      </div>
    </section>
  );
}
