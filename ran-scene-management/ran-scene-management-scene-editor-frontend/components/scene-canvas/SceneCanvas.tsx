'use client';
import { Suspense, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { Grid, Line, OrbitControls, Text } from '@react-three/drei';
import { CANVAS } from '@/config';
import type { Selection } from '@/hooks/feature/useSceneEditorPage';
import type { Cell, Gnb, SceneTree } from '@/types/registry';
import { CellMarker } from '@/components/scene-canvas/CellMarker';
import { GnbGroupMarker } from '@/components/scene-canvas/GnbGroupMarker';

/** gNB 顏色:沿用 registry 的 color,沒有就依序給一個(呈現層決定,不寫回) */
const PALETTE: [number, number, number][] = [[0.13, 0.55, 0.85], [0.9, 0.45, 0.1], [0.2, 0.7, 0.4], [0.7, 0.3, 0.8], [0.85, 0.2, 0.3]];
export function gnbColor(g: Gnb, i: number): [number, number, number] { return (g.color && g.color.length === 3 ? (g.color as [number, number, number]) : PALETTE[i % PALETTE.length]); }

/** cell 位置 null → 沿用 gNB(共站);有值 → 獨立(DAS)。純呈現,不改資料。 */
export function cellWorldPos(c: Cell, g: Gnb): [number, number, number] {
  const p = c.position && c.position.length === 3 ? c.position : g.position;
  return [p[0] ?? 0, p[1] ?? 0, p[2] ?? 0];
}

export interface SceneCanvasProps {
  tree: SceneTree; selection: Selection;
  onSelect: (s: Selection) => void;
  onCellMoved: (c: Cell, pos: [number, number, number]) => void;
  onGnbMoved: (g: Gnb, pos: [number, number, number]) => void;
}

export function SceneCanvas({ tree, selection, onSelect, onCellMoved, onGnbMoved }: SceneCanvasProps) {
  const uePaths = useMemo(() => tree.ues.map((u) => ({ ue: u, pts: u.waypoints.map((w) => [w[1], w[2], w[3]] as [number, number, number]) })), [tree.ues]);
  return (
    <Canvas camera={{ position: [40, 40, 40], fov: 45, near: 0.1, far: 5000 }} style={{ background: '#f4f3f0' }}>
      <ambientLight intensity={0.9} />
      <directionalLight position={[50, 80, 30]} intensity={0.8} />
      <Grid args={[CANVAS.gridSize, CANVAS.gridSize]} cellSize={1} sectionSize={10} cellColor="#d9d6cf" sectionColor="#b9b5aa" fadeDistance={400} infiniteGrid />
      <Suspense fallback={null}>
        {tree.buildings.map((b, i) => {
          const s = b.size && b.size.length === 3 ? b.size : [4, 3, 4];
          const p = b.position && b.position.length === 3 ? b.position : [0, 0, 0];
          return (
            <mesh key={b.building_uuid} position={[p[0], p[1] + s[1] / 2, p[2]]} onClick={(e) => { e.stopPropagation(); onSelect({ kind: 'building', index: i }); }}>
              <boxGeometry args={[s[0], s[1], s[2]]} />
              <meshStandardMaterial color={selection?.kind === 'building' && selection.index === i ? '#c8b58a' : '#e6e2d8'} transparent opacity={0.85} />
            </mesh>
          );
        })}
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
            {pts.length > 1 && <Line points={pts} color={selection?.kind === 'ue' && selection.ue.ue_uuid === ue.ue_uuid ? '#c2410c' : '#7c7c7c'} lineWidth={1} />}
            <mesh position={pts[0]}>
              <sphereGeometry args={[CANVAS.ueMarkerRadius, 12, 12]} />
              <meshStandardMaterial color={selection?.kind === 'ue' && selection.ue.ue_uuid === ue.ue_uuid ? '#c2410c' : '#5b5b5b'} />
            </mesh>
            <Text position={[pts[0][0], pts[0][1] + 1, pts[0][2]]} fontSize={0.7} color="#333" anchorX="center">{ue.name}</Text>
          </group>
        ))}
      </Suspense>
      <OrbitControls makeDefault enableDamping />
    </Canvas>
  );
}
