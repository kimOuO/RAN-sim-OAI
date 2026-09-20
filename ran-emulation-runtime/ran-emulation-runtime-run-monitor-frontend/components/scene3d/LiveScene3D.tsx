'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import { SceneMeshes, type MeshView } from '@/components/scene3d/SceneMeshes';
import * as THREE from 'three';
import { Canvas, useFrame, type ThreeEvent } from '@react-three/fiber';
import { Edges, Grid, Html, Line, OrbitControls } from '@react-three/drei';
import { CELL_COLORS, COVERAGE_SCALE, CoverageLayer, RAMP_CSS, type CoverageMode } from '@/components/scene3d/CoverageLayer';
import { computeCoverage, sceneBounds, type CoverageResult } from '@/services/api/coverage';
import { cellPositions, sceneView, sinrLevel, uePositionAt } from '@/hooks/feature/live3d';
import type { UeFlash } from '@/hooks/feature/useRunLive3dPage';
import type { SceneTree3d, UeKpm } from '@/types/telemetry';

type UeState = Record<string, UeKpm & { cell: string }>;
interface Props {
  tree: SceneTree3d; simNow: () => number; ueState: UeState; flashes: Record<string, { kind: UeFlash; until: number }>;
  color: Record<string, string>; selected: string | null; onSelect: (ue: string | null) => void; showLabels: boolean;
}
const IDLE = new THREE.Color('#5b6778');
const RLF = new THREE.Color('#ff4d5a');
const HO = new THREE.Color('#ffffff');

/** 即時 3D:gNB / cell 靜態;UE 用一個 InstancedMesh 每幀依模擬時間更新位置,顏色 = 服務 cell、亮度 = SINR;UE→cell 連線同一批 LineSegments */
export function LiveScene3D(p: Props) {
  // 幾何邊界(掃描模型)—— 取到才知道整個場地多大,鏡頭才框得住
  const [geo, setGeo] = useState<{ x: number[]; z: number[] } | null>(null);
  useEffect(() => { let off = false;
    sceneBounds(p.tree.scene.scene_uuid)
      .then((b) => { if (!off && b.x_range && b.z_range) setGeo({ x: b.x_range, z: b.z_range }); })
      .catch(() => { /* 沒有掃描模型或 physics 不通 → 用 tree 的範圍 */ });
    return () => { off = true; };
  }, [p.tree.scene.scene_uuid]);
  const view = useMemo(() => sceneView(p.tree, geo), [p.tree, geo]);
  const { center, extent, scale } = view;
  const hasGeo = !!(p.tree.scene.geometry_source as { type?: string } | null)?.type;
  const [mesh, setMesh] = useState<MeshView>({ show: true, opacity: 0.3, clipY: 2.2 });
  // 覆蓋熱圖:GPU 光追一次算完後留在記憶體,不隨 run 更新(它是理想值,與即時量測不同)
  const [cov, setCov] = useState<CoverageResult | null>(null);
  const [covBusy, setCovBusy] = useState(false);
  const [covErr, setCovErr] = useState<string | null>(null);
  const [covShow, setCovShow] = useState(true);
  const [covMode, setCovMode] = useState<CoverageMode>('sinr');
  const [covOpacity, setCovOpacity] = useState(0.6);
  const [covHeight, setCovHeight] = useState(1.5);
  // 外擴:auto grid 只涵蓋 gNB 與 UE 軌跡,掃描模型的尺寸不在內(見後端 auto_grid 說明)
  const [covMargin, setCovMargin] = useState(5);
  const runCoverage = async () => {
    setCovBusy(true); setCovErr(null);
    try { setCov(await computeCoverage(p.tree.scene.scene_uuid, { sample_height_m: covHeight, margin_m: covMargin })); setCovShow(true); }
    catch (e) { setCovErr(e instanceof Error ? e.message : String(e)); }
    finally { setCovBusy(false); }
  };
  return (
    <>
    <Canvas key={geo ? 'geo' : 'base'} onCreated={({ gl }) => { gl.localClippingEnabled = true; }} camera={{ position: [center[0] + extent * 0.45, extent * 0.35, center[2] + extent * 0.45], fov: 45, near: Math.max(0.5, extent / 500), far: Math.max(2000, extent * 8) }}
      style={{ background: '#0b0f14' }} onPointerMissed={() => p.onSelect(null)}>
      <ambientLight intensity={0.6} /><directionalLight position={[50, 80, 30]} intensity={0.8} />
      {/* 2026-09-20:網格壓到 y=-0.05。原本 y=0 與建築底面、掃描模型地面共面,
          深度精度不足時每幀輪流勝出 -> 地板持續閃爍(z-fighting)。 */}
      <Grid position={[0, -0.05, 0]} args={[400, 400]} cellSize={1} sectionSize={10} cellColor="#1f2e40" sectionColor="#2f6f8a" sectionThickness={1} cellThickness={0.5} fadeDistance={600} infiniteGrid />
      {p.tree.buildings.filter((b) => b.size?.length === 3).map((b) => (
        <mesh key={b.building_uuid} position={[b.position[0], b.position[1] + b.size[1] / 2, b.position[2]]}>
          <boxGeometry args={[b.size[0], b.size[1], b.size[2]]} /><meshStandardMaterial color="#4fd1ff" transparent opacity={0.06} depthWrite={false} /><Edges color="#7fe3ff" />
        </mesh>))}
      <Gnbs tree={p.tree} color={p.color} scale={scale} />
      <Ues {...p} scale={scale} />
      {hasGeo && <SceneMeshes sceneUuid={p.tree.scene.scene_uuid} view={mesh} />}
      {cov && covShow && <CoverageLayer result={cov} mode={covMode} opacity={covOpacity} />}
      <OrbitControls makeDefault enableDamping target={center} />
    </Canvas>
    {hasGeo && <div className="meshctl">
      <label><input type="checkbox" checked={mesh.show} onChange={(e) => setMesh({ ...mesh, show: e.target.checked })} /> 場景模型</label>
      <label>透明度<input type="range" min={0.05} max={1} step={0.05} value={mesh.opacity} onChange={(e) => setMesh({ ...mesh, opacity: Number(e.target.value) })} /></label>
      <label><input type="checkbox" checked={mesh.clipY != null} onChange={(e) => setMesh({ ...mesh, clipY: e.target.checked ? 2.2 : null })} /> 剖面 {mesh.clipY != null ? `${mesh.clipY.toFixed(1)} m` : ''}</label>
      {mesh.clipY != null && <input type="range" min={0.2} max={20} step={0.1} value={mesh.clipY} onChange={(e) => setMesh({ ...mesh, clipY: Number(e.target.value) })} />}
    </div>}
    <div className="covctl">
      <div className="row">
        <button className="primary" disabled={covBusy} onClick={runCoverage}>{covBusy ? '計算中…' : cov ? '重新計算覆蓋' : '計算覆蓋熱圖'}</button>
        <label>高度<input type="number" step={0.1} value={covHeight} onChange={(e) => setCovHeight(Number(e.target.value))} /> m</label>
        <label title="auto 範圍只涵蓋 gNB 與 UE 軌跡;掃描模型要靠外擴才蓋得到">外擴<input type="number" step={5} min={0} value={covMargin} onChange={(e) => setCovMargin(Number(e.target.value))} /> m</label>
        {cov && <label><input type="checkbox" checked={covShow} onChange={(e) => setCovShow(e.target.checked)} /> 顯示</label>}
      </div>
      {covErr && <p className="err small">{covErr}</p>}
      {cov && <>
        <div className="chips">{([['sinr', 'SINR'], ['rsrp', 'RSRP'], ['cell', '最佳 cell']] as [CoverageMode, string][]).map(([k, l]) =>
          <button key={k} className={`chip ${covMode === k ? 'on' : ''}`} onClick={() => setCovMode(k)}>{l}</button>)}</div>
        <label>不透明度<input type="range" min={0.1} max={1} step={0.05} value={covOpacity} onChange={(e) => setCovOpacity(Number(e.target.value))} /></label>
        {covMode === 'cell'
          ? <div className="legend">{cov.summary.cell_names.map((n, i) => <span key={n}><i style={{ background: CELL_COLORS[i % CELL_COLORS.length] }} />{n}</span>)}</div>
          : <div className="ramp"><div style={{ background: RAMP_CSS }} /><span>{COVERAGE_SCALE[covMode].min}</span><span>{COVERAGE_SCALE[covMode].max} {COVERAGE_SCALE[covMode].unit}</span></div>}
        <p className="muted small">{cov.grid.n_cols}×{cov.grid.n_rows} 格 · {cov.grid.x_step} m · {(cov.compute_ms / 1000).toFixed(1)} s。
          熱圖假設所有 cell 同時滿載互相干擾(最壞情況),與畫面上即時量測到的 SINR 不同,用來看覆蓋形狀與重疊。</p>
      </>}
    </div>
    </>
  );
}

function Gnbs({ tree, color, scale }: { tree: SceneTree3d; color: Record<string, string>; scale: number }) {
  return <>{tree.gnbs.map((g) => { const h = Math.max(g.position[1], 0.5); return (
    <group key={g.gnb_uuid}>
      <mesh position={[g.position[0], h / 2, g.position[2]]}><cylinderGeometry args={[0.08 * scale, 0.2 * scale, h, 12]} /><meshStandardMaterial color="#9fb3c8" /></mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[g.position[0], 0.02, g.position[2]]}><ringGeometry args={[0.5 * scale, 0.7 * scale, 32]} /><meshBasicMaterial color="#9fb3c8" transparent opacity={0.7} /></mesh>
      {g.dus.flatMap((d) => d.cells).map((c) => { const pos = c.position ?? g.position; const az = (c.azimuth_deg * Math.PI) / 180; const col = color[c.name] ?? '#888';
        return (
          <group key={c.cell_uuid} position={[pos[0], pos[1], pos[2]]}>
            <mesh><cylinderGeometry args={[0.9 * scale, 0.9 * scale, 0.4 * scale, 24]} /><meshStandardMaterial color={col} emissive={col} emissiveIntensity={c.is_active ? 0.5 : 0.05} transparent opacity={c.is_active ? 1 : 0.35} /></mesh>
            <mesh position={[Math.sin(az) * 2 * scale, 0, -Math.cos(az) * 2 * scale]} rotation={[0, -az, 0]}><boxGeometry args={[0.2 * scale, 0.2 * scale, 4 * scale]} /><meshStandardMaterial color={col} /></mesh>
          </group>); })}
    </group>); })}</>;
}

function Ues({ tree, simNow, ueState, flashes, color, selected, onSelect, showLabels, scale }: Props & { scale: number }) {
  const n = tree.ues.length;
  const mesh = useRef<THREE.InstancedMesh>(null);
  const head = useRef<THREE.InstancedMesh>(null);
  const links = useRef<THREE.BufferGeometry>(null);
  const cellPos = useMemo(() => cellPositions(tree), [tree]);
  const [hover, setHover] = useState<number | null>(null);
  const labelRefs = useRef<(THREE.Group | null)[]>([]);
  const tmp = useMemo(() => ({ m: new THREE.Matrix4(), c: new THREE.Color(), q: new THREE.Quaternion(), s: new THREE.Vector3(), v: new THREE.Vector3() }), []);
  const linkPos = useMemo(() => new Float32Array(Math.max(1, n) * 6), [n]);
  const linkCol = useMemo(() => new Float32Array(Math.max(1, n) * 6), [n]);
  const baseR = 0.45 * Math.max(scale, 0.5);
  const cellColors = useMemo(() => Object.fromEntries(Object.entries(color).map(([k, v]) => [k, new THREE.Color(v)])), [color]);
  useEffect(() => { links.current?.setDrawRange(0, 0); }, [n]);

  useFrame(() => {
    const im = mesh.current; const hm = head.current; if (!im || !hm) return;
    const t = simNow(); const now = performance.now(); let li = 0;
    tree.ues.forEach((u, i) => {
      const pos = uePositionAt(u, t); const st = ueState[u.name];
      if (!pos) { tmp.m.makeScale(0, 0, 0); im.setMatrixAt(i, tmp.m); hm.setMatrixAt(i, tmp.m); return; }
      const lv = sinrLevel(st?.sinr_db);
      const f = flashes[u.name]; const blink = f && f.until > now && Math.floor(now / 200) % 2 === 0;
      // 人形(沿用 Omniverse 舊版造型):圓柱身體 + 球頭,腳踩地面(UE 高度視為手持高度)
      const k = baseR / 0.45 * (u.name === selected ? 1.4 : 1); const bodyH = 1.3 * k; const headR = 0.21 * k;
      const ground = Math.max(0, pos[1] - 1.7);
      tmp.v.set(pos[0], ground + bodyH / 2, pos[2]); tmp.s.set(0.23 * k, bodyH, 0.23 * k); tmp.m.compose(tmp.v, tmp.q, tmp.s); im.setMatrixAt(i, tmp.m);
      tmp.v.set(pos[0], ground + bodyH + headR, pos[2]); tmp.s.set(headR, headR, headR); tmp.m.compose(tmp.v, tmp.q, tmp.s); hm.setMatrixAt(i, tmp.m);
      const r = bodyH + 2 * headR - (pos[1] - ground);
      const base = st?.cell && cellColors[st.cell] ? cellColors[st.cell] : IDLE;
      tmp.c.copy(blink ? (f.kind === 'rlf' ? RLF : HO) : base).multiplyScalar(0.35 + 0.65 * lv); im.setColorAt(i, tmp.c);
      labelRefs.current[i]?.position.set(pos[0], pos[1] + r + 0.4 * scale, pos[2]);
      const cp = st?.cell ? cellPos[st.cell] : undefined;
      if (cp && st.sinr_db > -99) {
        linkPos.set([pos[0], pos[1], pos[2], cp[0], cp[1], cp[2]], li * 6);
        linkCol.set([base.r, base.g, base.b, base.r * 0.4, base.g * 0.4, base.b * 0.4], li * 6); li++;
      }
    });
    im.instanceMatrix.needsUpdate = true; hm.instanceMatrix.needsUpdate = true; if (im.instanceColor) im.instanceColor.needsUpdate = true;
    const g = links.current; if (g) { (g.attributes.position as THREE.BufferAttribute).needsUpdate = true; (g.attributes.color as THREE.BufferAttribute).needsUpdate = true; g.setDrawRange(0, li * 2); }
  });

  const pick = (e: ThreeEvent<PointerEvent | MouseEvent>) => (e.instanceId != null ? tree.ues[e.instanceId]?.name ?? null : null);
  const sel = tree.ues.find((u) => u.name === selected);
  const labelFor = (i: number) => showLabels || i === hover || tree.ues[i]?.name === selected;
  return (
    <>
      <instancedMesh ref={mesh} args={[undefined, undefined, Math.max(1, n)]}
        onPointerMove={(e) => { e.stopPropagation(); setHover(e.instanceId ?? null); }} onPointerOut={() => setHover(null)}
        onClick={(e) => { e.stopPropagation(); onSelect(pick(e)); }}>
        <cylinderGeometry args={[1, 1, 1, 12]} /><meshStandardMaterial toneMapped={false} />
      </instancedMesh>
      <instancedMesh ref={head} args={[undefined, undefined, Math.max(1, n)]}
        onPointerMove={(e) => { e.stopPropagation(); setHover(e.instanceId ?? null); }} onPointerOut={() => setHover(null)}
        onClick={(e) => { e.stopPropagation(); onSelect(pick(e)); }}>
        <sphereGeometry args={[1, 12, 12]} /><meshStandardMaterial color="#ffe6b3" />
      </instancedMesh>
      <lineSegments frustumCulled={false}>
        <bufferGeometry ref={links}>
          <bufferAttribute attach="attributes-position" args={[linkPos, 3]} />
          <bufferAttribute attach="attributes-color" args={[linkCol, 3]} />
        </bufferGeometry>
        <lineBasicMaterial vertexColors transparent opacity={0.55} />
      </lineSegments>
      {sel && sel.waypoints.length > 1 && <Line points={sel.waypoints.map((w) => [w[1], w[2], w[3]] as [number, number, number])} color="#ff8a3d" lineWidth={1} transparent opacity={0.6} />}
      {tree.ues.map((u, i) => labelFor(i) && (
        <group key={u.ue_uuid} ref={(el) => { labelRefs.current[i] = el; }}>
          <Html center distanceFactor={undefined} style={{ pointerEvents: 'none' }}><UeLabel name={u.name} st={ueState[u.name]} full={i === hover || u.name === selected} /></Html>
        </group>))}
    </>
  );
}

function UeLabel({ name, st, full }: { name: string; st?: UeKpm & { cell: string }; full: boolean }) {
  if (!full) return <div className="ue3d-tag">{name}</div>;
  return (
    <div className="ue3d-tip">
      <b>{name}</b> <span className="muted">{st?.cell || '未附著'}</span>
      {st && <div className="mono">RSRP {st.rsrp_dbm?.toFixed(1)} · SINR {st.sinr_db?.toFixed(1)} dB<br />DL {st.throughput_dl_mbps?.toFixed(2)} Mbps · MCS {st.mcs_dl}{st.beam_id != null ? ` · beam ${st.beam_id}` : ''}</div>}
    </div>
  );
}
