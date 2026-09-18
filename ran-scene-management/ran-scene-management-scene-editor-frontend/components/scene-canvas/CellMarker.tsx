'use client';
import { Text } from '@react-three/drei';
import * as THREE from 'three';
import { CANVAS } from '@/config';
import { useSurfaceDrag } from '@/components/scene-canvas/surface';
import type { Cell, Gnb } from '@/types/registry';

interface Props { cell: Cell; gnb: Gnb; color: [number, number, number]; position: [number, number, number]; selected: boolean; onSelect: () => void; onMoved: (p: [number, number, number]) => void; scale?: number; }

/** Cell = 畫布上可拖的節點:拖動貼齊滑鼠下的表面(地面 / 屋頂 / 掃描模型),離表面的高度不變;放開才寫回。方位角用一根短棒示意。 */
export function CellMarker({ cell, gnb, color, position, selected, onSelect, onMoved, scale = 1 }: Props) {
  const { pos, handlers } = useSurfaceDrag(position, onMoved);
  const az = (cell.azimuth_deg * Math.PI) / 180;
  const c = new THREE.Color(...color);
  return (
    <group position={pos}>
      <mesh
        onClick={(e) => { e.stopPropagation(); onSelect(); }} {...handlers}>
        <cylinderGeometry args={[CANVAS.cellMarkerRadius * scale, CANVAS.cellMarkerRadius * scale, 0.5 * scale, 24]} />
        <meshStandardMaterial color={c} emissive={c} emissiveIntensity={selected ? 0.9 : 0.35} />
      </mesh>
      {pos[1] > 0.05 && (   // 落地細柱:不然 cell 看起來浮在空中
        <mesh position={[0, -pos[1] / 2, 0]}>
          <cylinderGeometry args={[0.04 * scale, 0.04 * scale, pos[1], 8]} />
          <meshStandardMaterial color={c} transparent opacity={0.6} />
        </mesh>)}
      <mesh position={[Math.sin(az) * 2 * scale, 0, -Math.cos(az) * 2 * scale]} rotation={[0, -az, 0]}>
        <boxGeometry args={[0.2 * scale, 0.2 * scale, 4 * scale]} />
        <meshStandardMaterial color={c} />
      </mesh>
      <Text position={[0, 1.2 * scale, 0]} fontSize={0.6 * scale} color="#ffffff" outlineWidth={0.04 * scale} outlineColor="#0b0f14" anchorX="center">{`${gnb.name} / ${cell.name}  pci ${cell.pci}`}</Text>
    </group>
  );
}
