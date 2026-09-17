'use client';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { LiveScene3D } from '@/components/scene3d/LiveScene3D';
import { useRunLive3dPage } from '@/hooks/feature/useRunLive3dPage';

/** 3D 即時:UE 隨模擬時間移動,顏色 = 服務 cell、大小 / 亮度 = SINR;換手閃白、RLF 閃紅 */
export default function Live3dPage() {
  const { id } = useParams<{ id: string }>();
  const p = useRunLive3dPage(id);
  if (p.error) return <p className="err">{p.error.message}</p>;
  if (!p.run || !p.tree) return <p className="muted">載入場景…</p>;
  const cells = Object.entries(p.color);
  const attached = Object.values(p.ueState).filter((s) => s.cell && s.sinr_db > -99).length;
  return (
    <>
      <header className="runhead">
        <div><div className="crumbs"><Link href="/runs">Runs</Link> / <Link href={`/runs/${id}`}>{p.sceneName}</Link></div><h1>3D 即時</h1></div>
        <span className={`pill ${p.run.status}`}>{p.run.status}</span>
        <span className="muted">{p.driver ? `模擬 ${Math.floor((p.driver.elapsed_sim_sec ?? 0) / 60)}:${String(Math.floor((p.driver.elapsed_sim_sec ?? 0) % 60)).padStart(2, '0')} · ${p.driver.sim_speed_x}× · ` : ''}{attached}/{p.tree.ues.length} UE 附著</span>
        <span className="sp" />
        <label className="check-inline"><input type="checkbox" checked={p.showLabels} onChange={(e) => p.setShowLabels(e.target.checked)} /> 顯示全部名稱</label>
        <nav className="sub"><Link href={`/runs/${id}`}>儀表板</Link><Link href={`/runs/${id}/events`}>事件流</Link><Link href={`/runs/${id}/playback`}>回放</Link></nav>
      </header>
      <div className="live3d">
        <LiveScene3D tree={p.tree} simNow={p.simNow} ueState={p.ueState} flashes={p.flashes} color={p.color} selected={p.selected} onSelect={p.setSelected} showLabels={p.showLabels} />
        <div className="live3d-legend">
          {cells.map(([c, col]) => <div key={c}><i style={{ background: col }} />{c}</div>)}
          <div><i style={{ background: '#5b6778' }} />未附著</div>
          <div className="muted small">大小 / 亮度 = SINR · 閃白 = 換手 · 閃紅 = RLF · 點 UE 看數值與路徑</div>
          {!p.live && <div className="warn small">run 不在執行中,UE 停在最後讀到的時間</div>}
        </div>
      </div>
    </>
  );
}
