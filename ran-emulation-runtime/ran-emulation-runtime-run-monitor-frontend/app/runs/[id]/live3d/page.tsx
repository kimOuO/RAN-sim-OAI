'use client';
import Link from 'next/link';
import { RunSubNav } from '@/components/dashboard/RunSubNav';
import { useParams } from 'next/navigation';
import { LiveScene3D } from '@/components/scene3d/LiveScene3D';
import { LabelControls } from '@/components/scene3d/LabelControls';
import { UeCards } from '@/components/scene3d/UeCards';
import { topologyCounts, uePositionAt, ueAttached } from '@/hooks/feature/live3d';
import { useRunLive3dPage } from '@/hooks/feature/useRunLive3dPage';
import { statusLabel } from '@/hooks/feature/runStatus';

/** 3D 即時:UE 隨模擬時間移動,顏色 = 服務 cell、大小 / 亮度 = SINR;換手閃白、RLF 閃紅 */
export default function Live3dPage() {
  const { id } = useParams<{ id: string }>();
  const p = useRunLive3dPage(id);
  if (p.error) return <p className="err">{p.error.message}</p>;
  if (!p.run || !p.tree) return <p className="muted">載入場景…</p>;
  const cells = Object.entries(p.color);
  // 在場:依 UE 的在場時段;不在場的不畫。列出下一個進場時間,避免「只看到 gNB」時以為壞了
  const t = p.driver?.elapsed_sim_sec ?? 0;
  const present = p.tree ? p.tree.ues.filter((u) => uePositionAt(u, t) !== null).length : 0;
  const nextIn = p.tree ? Math.min(Infinity, ...p.tree.ues.flatMap((u) => u.active_windows.map(([a]) => a).filter((a) => a > t))) : Infinity;
  const fmt = (x: number) => `${Math.floor(x / 3600)}h${String(Math.floor((x % 3600) / 60)).padStart(2, '0')}m`;
  const attached = Object.values(p.ueState).filter(ueAttached).length;
  const topo = topologyCounts(p.tree);
  return (
    <>
      <header className="runhead">
        <div><div className="crumbs"><Link href="/runs">Runs</Link> / <Link href={`/runs/${id}`}>{p.sceneName}</Link></div><h1>3D 即時</h1></div>
        <span className={`pill ${p.run.status}`}>{statusLabel(p.run)}</span>
        {p.live && p.driver?.running && p.driver.clock_running === false && <span className="err">模擬時鐘未更新</span>}
        <span className="muted">{p.driver ? `模擬 ${Math.floor((p.driver.elapsed_sim_sec ?? 0) / 60)}:${String(Math.floor((p.driver.elapsed_sim_sec ?? 0) % 60)).padStart(2, '0')} · ${Number.isFinite(p.driver.sim_speed_x) ? `${p.driver.sim_speed_x}× · ` : ''}` : ''}{attached}/{p.tree.ues.length} UE 附著</span>
        <span className="sp" />
        <span className="muted small">{topo.gnb} gNB · {topo.du} DU · {topo.cell} cell · 通道 {p.run.mode === 'cached' ? '快取' : '即時'}</span>
        <LabelControls mode={p.labelMode} setMode={p.setLabelMode} sites={p.showSites} setSites={p.setShowSites} />
        <RunSubNav id={id} />
      </header>
      <div className="live3d-wrap">
      <div className="live3d">
        <LiveScene3D tree={p.tree} simNow={p.simNow} ueState={p.ueState} flashes={p.flashes} color={p.color} selected={p.selected} onSelect={p.setSelected} labelMode={p.labelMode} showSites={p.showSites} />
        <div className="live3d-legend" data-declutter-obstacle>
          {cells.map(([c, col]) => <div key={c}><i style={{ background: col }} />{c}</div>)}
          <div><i style={{ background: '#5b6778' }} />未附著</div>
          <div className="small">在場 UE {present}/{p.tree.ues.length}{present < p.tree.ues.length && Number.isFinite(nextIn) ? ` · 下一個 ${fmt(nextIn)} 進場(目前 ${fmt(t)})` : ''}</div>
          <div className="muted small">大小 / 亮度 = SINR · 閃白 = 換手 · 閃紅 = RLF · 點 UE 或右側卡片看數值與路徑</div>
          {!p.live && <div className="warn small">run 不在執行中,UE 停在最後讀到的時間</div>}
        </div>
      </div>
      <UeCards names={p.tree.ues.map((u) => u.name)} ueState={p.ueState} color={p.color} owners={p.owners} selected={p.selected} onSelect={p.setSelected} />
      </div>
    </>
  );
}
