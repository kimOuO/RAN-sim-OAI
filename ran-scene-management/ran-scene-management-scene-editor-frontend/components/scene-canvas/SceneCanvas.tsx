'use client';
import { Suspense, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { Edges, Grid, Line, OrbitControls, Text } from '@react-three/drei';
import { CANVAS } from '@/config';
import type { Selection } from '@/hooks/feature/useSceneEditorPage';
import type { Building, Cell, Gnb, SceneTree } from '@/types/registry';
import { CellMarker } from '@/components/scene-canvas/CellMarker';
import { GnbGroupMarker } from '@/components/scene-canvas/GnbGroupMarker';

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
  /** 放置模式下點地面(公尺,Y-up) */
  onGroundClick: (pos: [number, number, number]) => void;
  onCellMoved: (c: Cell, pos: [number, number, number]) => void;
  onGnbMoved: (g: Gnb, pos: [number, number, number]) => void;
}

export function SceneCanvas({ tree, selection, placing, onSelect, onGroundClick, onCellMoved, onGnbMoved }: SceneCanvasProps) {
  const uePaths = useMemo(() => tree.ues.map((u) => ({ ue: u, pts: u.waypoints.map((w) => [w[1], w[2], w[3]] as [number, number, number]) })), [tree.ues]);
  return (
    <Canvas camera={{ position: [40, 40, 40], fov: 45, near: 0.1, far: 5000 }} style={{ background: '#0b0f14', cursor: placing ? 'crosshair' : 'default' }}>
      {/* 地面:放置模式時接點擊;平常點空白處取消選取 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]} onClick={(e) => { e.stopPropagation(); if (placing) onGroundClick([e.point.x, 0, e.point.z]); else onSelect(null); }}><planeGeometry args={[CANVAS.gridSize * 4, CANVAS.gridSize * 4]} /><meshBasicMaterial visible={false} /></mesh>
      <ambientLight intensity={0.6} />
      <directionalLight position={[50, 80, 30]} intensity={0.8} />
      <Grid args={[CANVAS.gridSize, CANVAS.gridSize]} cellSize={1} sectionSize={10} cellColor="#1f2e40" sectionColor="#4fd1ff" sectionThickness={1.2} cellThickness={0.6} fadeDistance={600} fadeStrength={1} infiniteGrid />
      <Suspense fallback={null}>
        {tree.buildings.map((b) => <BuildingMesh key={b.building_uuid} b={b} selected={selection?.kind === 'building' && selection.building.building_uuid === b.building_uuid} onSelect={() => onSelect({ kind: 'building', building: b })} />)}
        {tree.gnbs.map((g, gi) => (
          <group key={g.gnb_uuid}>
            <GnbGroupMarker gnb={g} color={gnbColor(g, gi)} selected={selection?.kind === 'gnb' && selection.gnb.gnb_uuid === g.gnb_uuid}
              onSelect={() => onSelect({ kind: 'gnb', gnb: g })} onMoved={(p) => onGnbMoved(g, p)} />
            {g.dus.flatMap((d) => d.cells).map((c) => (
              <CellMarker key={c.cell_uuid} cell={c} gnb={g} color={gnbColor(g, gi)} position={cellWorldPos(c, g)}
                selected={selection?.kind === 'cell' && selection.cell.cell_uuid === c.cell_uuid}
                onSelect={() => onSelect({ kind: 'cell', cell: c, gnb: g })} onMoved={(p) => onCellMoved(c, p)} />
            ))}
          </group>
        ))}
        {uePaths.map(({ ue, pts }) => pts.length > 0 && (
          <group key={ue.ue_uuid} onClick={(e) => { e.stopPropagation(); onSelect({ kind: 'ue', ue }); }}>
            {pts.length > 1 && <Line points={pts} color={selection?.kind === 'ue' && selection.ue.ue_uuid === ue.ue_uuid ? '#ff8a3d' : '#8b9bb0'} lineWidth={1} />}
            <mesh position={pts[0]}>
              <sphereGeometry args={[CANVAS.ueMarkerRadius, 12, 12]} />
              <meshStandardMaterial color={selection?.kind === 'ue' && selection.ue.ue_uuid === ue.ue_uuid ? '#ff8a3d' : '#c9d4e0'} />
            </mesh>
            <Text position={[pts[0][0], pts[0][1] + 1, pts[0][2]]} fontSize={0.7} color="#e6edf3" outlineWidth={0.04} outlineColor="#0b0f14" anchorX="center">{ue.name}</Text>
          </group>
        ))}
      </Suspense>
      <OrbitControls makeDefault enableDamping />
    </Canvas>
  );
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
    <mesh position={[p[0], p[1] + s[1] / 2, p[2]]} onClick={(e) => { e.stopPropagation(); onSelect(); }}>
      <boxGeometry args={[s[0], s[1], s[2]]} />
      <meshStandardMaterial color={selected ? '#ff8a3d' : '#4fd1ff'} transparent opacity={0.08} depthWrite={false} />
      <Edges color={col} threshold={15} />
    </mesh>);
}
