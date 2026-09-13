'use client';
import Link from 'next/link';
import { useState } from 'react';
import { MONITOR_BASE_URL, SCENE_CATEGORIES } from '@/config';
import { useSceneListPage } from '@/hooks/feature/useSceneListPage';

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
            {r ? <p className="small">{r.mode} · {r.speed_x}× · dt {r.sim_dt_ms} ms · {(r.duration_sec / 3600).toFixed(1)} h{r.mode === 'cached' ? (r.cache_path ? ' · 已預算' : ' · 未預算') : ''}</p> : <p className="muted small">尚無 run</p>}
            <footer>
              <Link href={`/scenes/${s.scene_uuid}`}><button>編輯</button></Link>
              {r && (r.status === 'running' ? <button className="danger" disabled={p.busy === r.scene_run_uuid} onClick={() => p.stop(r)}>停止</button> : <button className="primary" disabled={p.busy === r.scene_run_uuid} onClick={() => p.start(r)}>{p.busy === r.scene_run_uuid ? '啟動中…' : '啟動'}</button>)}
              {r && (r.status === 'running' || r.status === 'stopped') && <a href={`${MONITOR_BASE_URL}/runs/${r.scene_run_uuid}`} target="_blank" rel="noreferrer"><button>監控 ↗</button></a>}
              <span className="sp" /><button className="ghost danger" disabled={!!p.busy} onClick={() => { if (confirm(`刪除場景 ${s.name}?`)) p.remove(s); }}>刪除</button>
            </footer>
          </article>); })}
      </div>
    </section>
  );
}
