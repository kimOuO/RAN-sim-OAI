'use client';
import { Suspense, useMemo, useState, type ReactNode } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { Edges, Grid, Line, OrbitControls, Text } from '@react-three/drei';
import { CANVAS } from '@/config';
import type { Selection } from '@/hooks/feature/useSceneEditorPage';
import type { Building, Cell, Gnb, SceneTree, Ue } from '@/types/registry';
import { CellMarker } from '@/components/scene-canvas/CellMarker';
import { GnbGroupMarker } from '@/components/scene-canvas/GnbGroupMarker';
import { ueActiveAt, uePositionAt } from '@/hooks/feature/sceneGeometry';
import { SceneMeshes, type MeshView } from '@/components/scene-canvas/SceneMeshes';
import { SURFACE_FLAG, SurfaceClip, pickSurface, useSurfaceDrag } from '@/components/scene-canvas/surface';

/** gNB 顏色:沿用 registry 的 color,沒有就依序給一個(呈現層決定,不寫回) */
const PALETTE: [number, number, number][] = [[0.31, 0.82, 1.0], [1.0, 0.54, 0.24], [0.45, 0.9, 0.55], [0.8, 0.55, 1.0], [1.0, 0.45, 0.5]];
export function gnbColor(g: Gnb, i: number): [number, number, number] { return (g.color && g.color.length === 3 ? (g.color as [number, number, number]) : PALETTE[i % PALETTE.length]); }

/** cell 位置 null → 沿用 gNB(共站);有值 → 獨立(DAS)。純呈現,不改資料。 */
export function cellWorldPos(c: Cell, g: Gnb): [number, number, number] {
  const p = c.position && c.position.length === 3 ? c.position : g.position;
  return [p[0] ?? 0, p[1] ?? 0, p[2] ?? 0];
}

export interface SceneCanvasProps {
  tree: SceneTree; selection: Selection; placing: boolean;
  onSelect: (s: Selection) => void;
  /** 放置模式下點畫布:滑鼠下第一個表面點(地面 / 屋頂 / 掃描模型;公尺,Y-up) */
  onGroundClick: (pos: [number, number, number]) => void;
  /** UE 被拖到新位置(整條路徑平移 dx/dy/dz) */
  onUeMoved?: (u: Ue, delta: [number, number, number]) => void;
  onCellMoved: (c: Cell, pos: [number, number, number]) => void;
  onGnbMoved: (g: Gnb, pos: [number, number, number]) => void;
  /** 路徑預覽時間(秒);給值時 UE 畫在該時間的位置,不在場的 UE 隱藏 */
  previewT?: number | null;
  /** 疊在場景上的額外 3D 物件(例如覆蓋熱圖) */
  overlay?: ReactNode;
}

export function SceneCanvas({ tree, selection, placing, onSelect, onGroundClick, onCellMoved, onGnbMoved, onUeMoved, previewT = null, overlay }: SceneCanvasProps) {
  const hasGeo = !!(tree.scene.geometry_source as { type?: string } | null)?.type || tree.buildings.some((b) => b.geometry_ref?.endsWith('.xml'));
  const [meshView, setMeshView] = useState<MeshView>({ show: true, opacity: 0.35, clipY: 2.2 });
  const [meshInfo, setMeshInfo] = useState('');
  // 場景範圍(gNB / cell / UE 路徑 / 建築)→ 標記比例與鏡頭。大型戶外場景 scale=1,走廊這種十幾公尺的場景自動縮小
  const view = useMemo(() => {
    const xs: number[] = [], zs: number[] = [];
    const add = (p?: number[] | null) => { if (p && p.length === 3) { xs.push(p[0]); zs.push(p[2]); } };
    tree.gnbs.forEach((g) => { add(g.position); g.dus.forEach((d) => d.cells.forEach((c) => add(c.position))); });
    tree.ues.forEach((u) => u.waypoints.forEach((w) => { xs.push(w[1]); zs.push(w[3]); }));
    tree.buildings.forEach((b) => add(b.position));
    if (!xs.length) return { center: [0, 0, 0] as [number, number, number], extent: 80, scale: 1 };
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cz = (Math.min(...zs) + Math.max(...zs)) / 2;
    const extent = Math.max(10, Math.max(...xs) - Math.min(...xs), Math.max(...zs) - Math.min(...zs));
    return { center: [cx, 0, cz] as [number, number, number], extent, scale: Math.max(0.4, Math.min(6, extent / 120)) };
  }, [tree]);
  const uePaths = useMemo(() => tree.ues.map((u) => ({ ue: u, pts: u.waypoints.map((w) => [w[1], w[2], w[3]] as [number, number, number]) })), [tree.ues]);
  return (
    <>
    <Canvas onCreated={({ gl }) => { gl.localClippingEnabled = true; }} camera={{ position: [view.center[0] + view.extent * 0.45, view.extent * 0.35, view.center[2] + view.extent * 0.45], fov: 45, near: Math.max(0.5, view.extent / 500), far: Math.max(2000, view.extent * 8) }} style={{ background: '#0b0f14', cursor: placing ? 'crosshair' : 'default' }}>
      <SurfaceClip.Provider value={hasGeo && meshView.show ? meshView.clipY : null}>
      {/* 地面:放置模式時接點擊,落點貼齊滑鼠下的表面(屋頂 / 掃描模型);平常點空白處取消選取 */}
      <PlaceCatcher placing={placing} onPlace={onGroundClick} onEmpty={() => onSelect(null)} clipY={hasGeo && meshView.show ? meshView.clipY : null} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[50, 80, 30]} intensity={0.8} />
      {/* y=-0.05:避免與建築底面 / 掃描模型地面共面造成 z-fighting(2026-09-20) */}
      <Grid position={[0, -0.05, 0]} args={[CANVAS.gridSize, CANVAS.gridSize]} cellSize={1} sectionSize={10} cellColor="#1f2e40" sectionColor="#4fd1ff" sectionThickness={1.2} cellThickness={0.6} fadeDistance={600} fadeStrength={1} infiniteGrid />
      <Suspense fallback={null}>
        {tree.buildings.map((b) => <BuildingMesh key={b.building_uuid} b={b} selected={selection?.kind === 'building' && selection.building.building_uuid === b.building_uuid} onSelect={() => onSelect({ kind: 'building', building: b })} />)}
        {tree.gnbs.map((g, gi) => (
          <group key={g.gnb_uuid}>
            <GnbGroupMarker gnb={g} color={gnbColor(g, gi)} selected={selection?.kind === 'gnb' && selection.gnb.gnb_uuid === g.gnb_uuid}
              onSelect={() => onSelect({ kind: 'gnb', gnb: g })} onMoved={(p) => onGnbMoved(g, p)} scale={view.scale} />
            {g.dus.flatMap((d) => d.cells).map((c) => (
              <CellMarker key={c.cell_uuid} cell={c} gnb={g} color={gnbColor(g, gi)} position={cellWorldPos(c, g)}
                selected={selection?.kind === 'cell' && selection.cell.cell_uuid === c.cell_uuid}
                onSelect={() => onSelect({ kind: 'cell', cell: c, gnb: g })} onMoved={(p) => onCellMoved(c, p)} scale={view.scale} />
            ))}
          </group>
        ))}
        {uePaths.map(({ ue, pts: path }) => { if (!path.length) return null;
          const at = previewT == null ? path[0] : (ueActiveAt(ue, previewT) ? uePositionAt(ue, previewT) : null);
          if (!at) return null;
          return <UeMarker key={ue.ue_uuid} ue={ue} path={path} at={at} dim={previewT != null} selected={selection?.kind === 'ue' && selection.ue.ue_uuid === ue.ue_uuid}
            scale={view.scale} draggable={previewT == null && !!onUeMoved} onSelect={() => onSelect({ kind: 'ue', ue })} onMoved={(d) => onUeMoved?.(ue, d)} />; })}
      </Suspense>
      {hasGeo && <SceneMeshes sceneUuid={tree.scene.scene_uuid} view={meshView} onInfo={setMeshInfo} />}
      {overlay}
      </SurfaceClip.Provider>
      <OrbitControls makeDefault enableDamping target={view.center} />
    </Canvas>
    {hasGeo && <div className="meshctl">
      <label><input type="checkbox" checked={meshView.show} onChange={(e) => setMeshView({ ...meshView, show: e.target.checked })} /> 場景模型</label>
      <label>透明度<input type="range" min={0.05} max={1} step={0.05} value={meshView.opacity} onChange={(e) => setMeshView({ ...meshView, opacity: Number(e.target.value) })} /></label>
      <label><input type="checkbox" checked={meshView.clipY != null} onChange={(e) => setMeshView({ ...meshView, clipY: e.target.checked ? 2.2 : null })} /> 剖面</label>
      {meshView.clipY != null && <label>高度 {meshView.clipY.toFixed(1)} m<input type="range" min={0.2} max={20} step={0.1} value={meshView.clipY} onChange={(e) => setMeshView({ ...meshView, clipY: Number(e.target.value) })} /></label>}
      {meshInfo && <span className="muted small">{meshInfo}</span>}
    </div>}
    </>
  );
}

/** 放置用的地面接收面:點擊時沿滑鼠射線找第一個表面(剖面以上忽略),沒有就落在 y = 0 */
function PlaceCatcher({ placing, onPlace, onEmpty, clipY }: { placing: boolean; onPlace: (p: [number, number, number]) => void; onEmpty: () => void; clipY: number | null }) {
  const { scene } = useThree();
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]} onClick={(e) => {
      e.stopPropagation();
      if (!placing) { onEmpty(); return; }
      const p = pickSurface(e.ray, scene, clipY) ?? e.point;
      onPlace([p.x, Math.max(0, p.y), p.z]);
    }}><planeGeometry args={[CANVAS.gridSize * 4, CANVAS.gridSize * 4]} /><meshBasicMaterial visible={false} /></mesh>);
}

/** UE:標記 + 落地線 + 路徑;拖標記 = 整條路徑平移(貼齊表面,手持高度不變) */
function UeMarker({ ue, path, at, dim, selected, scale, draggable, onSelect, onMoved }: {
  ue: Ue; path: [number, number, number][]; at: [number, number, number]; dim: boolean; selected: boolean; scale: number; draggable: boolean;
  onSelect: () => void; onMoved: (d: [number, number, number]) => void;
}) {
  const { pos, dragging, handlers } = useSurfaceDrag(at, (p) => onMoved([p[0] - at[0], p[1] - at[1], p[2] - at[2]]));
  const d: [number, number, number] = [pos[0] - at[0], pos[1] - at[1], pos[2] - at[2]];
  const shown = dragging ? path.map((q) => [q[0] + d[0], q[1] + d[1], q[2] + d[2]] as [number, number, number]) : path;
  const col = selected ? '#ff8a3d' : '#c9d4e0';
  return (
    <group onClick={(e) => { e.stopPropagation(); onSelect(); }}>
      {shown.length > 1 && <Line points={shown} transparent opacity={dim ? 0.35 : 1} color={selected ? '#ff8a3d' : '#8b9bb0'} lineWidth={1} />}
      {/* 落地線 + 地面圓:UE 在天線高度(約 1.5 m),不加會看起來浮空 */}
      <Line points={[pos, [pos[0], pos[1] - 1.5, pos[2]]]} color="#8b9bb0" lineWidth={1} transparent opacity={0.6} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[pos[0], pos[1] - 1.48, pos[2]]}>
        <ringGeometry args={[CANVAS.ueMarkerRadius * scale * 0.8, CANVAS.ueMarkerRadius * scale * 1.3, 20]} />
        <meshBasicMaterial color="#c9d4e0" transparent opacity={0.7} />
      </mesh>
      <mesh position={pos} {...(draggable ? handlers : {})}>
        <sphereGeometry args={[CANVAS.ueMarkerRadius * Math.max(scale, 0.5), 12, 12]} />
        <meshStandardMaterial color={col} />
      </mesh>
      <Text position={[pos[0], pos[1] + 0.8 * Math.max(scale, 0.5), pos[2]]} fontSize={0.7 * Math.max(scale, 0.5)} color="#e6edf3" outlineWidth={0.04} outlineColor="#0b0f14" anchorX="center">{ue.name}</Text>
    </group>);
}

/** 建築:manual_box / glb 有 size 就畫線框盒;osm footprint 沒 size 時畫一個標記平面(footprint 渲染:Omniverse 階段) */
function BuildingMesh({ b, selected, onSelect }: { b: Building; selected: boolean; onSelect: () => void }) {
  const s = b.size && b.size.length === 3 ? b.size : null;
  const p = b.position && b.position.length === 3 ? b.position : [0, 0, 0];
  const col = selected ? '#ff8a3d' : '#7fe3ff';
  if (!s) return (
    <group position={[p[0], 0.05, p[2]]} onClick={(e) => { e.stopPropagation(); onSelect(); }}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[6, 7, 48]} /><meshBasicMaterial color={col} transparent opacity={0.8} /></mesh>
      <Text position={[0, 1.2, 0]} fontSize={1.2} color="#ffffff" outlineWidth={0.06} outlineColor="#0b0f14" anchorX="center">{`${b.name} (${b.source})`}</Text>
    </group>);
  return (
    <mesh position={[p[0], p[1] + s[1] / 2, p[2]]} userData={{ [SURFACE_FLAG]: true }} onClick={(e) => { e.stopPropagation(); onSelect(); }}>
      <boxGeometry args={[s[0], s[1], s[2]]} />
      <meshStandardMaterial color={selected ? '#ff8a3d' : '#4fd1ff'} transparent opacity={0.08} depthWrite={false} />
      <Edges color={col} threshold={15} />
    </mesh>);
}
