'use client';
import Link from 'next/link';
import { useState } from 'react';
import { useSceneListPage } from '@/hooks/feature/useSceneListPage';

export default function ScenesPage() {
  const p = useSceneListPage();
  const [name, setName] = useState('');
  return (
    <section className="page">
      <header className="pagehead"><h1>場景</h1>
        <input placeholder="搜尋名稱 / 舊 scenario_id" value={p.filter} onChange={(e) => p.setFilter(e.target.value)} />
        <form onSubmit={(e) => { e.preventDefault(); if (name.trim()) { p.create(name.trim()); setName(''); } }}>
          <input placeholder="新場景名稱" value={name} onChange={(e) => setName(e.target.value)} /><button type="submit" disabled={p.busy === 'create'}>建立</button>
        </form>
      </header>
      {p.status === 'loading' && <p className="muted">載入中…</p>}
      {p.error && <p className="err">{p.error.message}</p>}
      <div className="cards">
        {p.scenes.map((s) => {
          const runs = p.runsByScene.get(s.scene_uuid) ?? [];
          const active = runs.filter((r) => r.status === 'running');
          return (
            <article key={s.scene_uuid} className="card">
              <h2><Link href={`/scenes/${s.scene_uuid}`}>{s.name}</Link></h2>
              <p className="muted">{s.legacy_scenario_id && `劇本 ${s.legacy_scenario_id} · `}{s.geometry_scene_id && `幾何 ${s.geometry_scene_id} · `}更新 {s.scene_updated_at.slice(0, 16).replace('T', ' ')}</p>
              <div className="runs">
                {runs.slice(0, 3).map((r) => (
                  <div key={r.scene_run_uuid} className={`run ${r.status}`}>
                    <span className="pill">{r.status}</span> {r.mode} · {r.speed_x}× · dt {r.sim_dt_ms}ms · {r.duration_sec}s
                    {r.status === 'running'
                      ? <button disabled={p.busy === r.scene_run_uuid} onClick={() => p.stop(r)}>Stop</button>
                      : <button disabled={p.busy === r.scene_run_uuid} onClick={() => p.start(r)}>Start</button>}
                  </div>
                ))}
                {runs.length === 0 && <p className="muted">尚無 run</p>}
              </div>
              <footer><span className="muted">{active.length ? `${active.length} 個執行中` : ''}</span><button className="danger" disabled={!!p.busy} onClick={() => { if (confirm(`刪除場景 ${s.name}?`)) p.remove(s); }}>刪除</button></footer>
            </article>
          );
        })}
      </div>
    </section>
  );
}
