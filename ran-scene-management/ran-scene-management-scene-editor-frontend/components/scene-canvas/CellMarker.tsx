'use client';
import { Text } from '@react-three/drei';
import * as THREE from 'three';
import { CANVAS } from '@/config';
import { useSurfaceDrag } from '@/components/scene-canvas/surface';
import { ANTENNA_KIND_LABEL, AntennaGlyph, antennaKind } from '@/components/scene-canvas/AntennaGlyph';
import type { AntennaPreset, Cell, Gnb } from '@/types/registry';

interface Props { cell: Cell; gnb: Gnb; /** 生效的天線範本(cell 的 RU 範本,沒有則用場景預設) */ preset?: AntennaPreset | null; color: [number, number, number]; position: [number, number, number]; selected: boolean; onSelect: () => void; onMoved: (p: [number, number, number]) => void; scale?: number; }

/** Cell = 畫布上可拖的節點:拖動貼齊滑鼠下的表面(地面 / 屋頂 / 掃描模型),離表面的高度不變;放開才寫回。方位角用一根短棒示意。 */
export function CellMarker({ cell, gnb, preset, color, position, selected, onSelect, onMoved, scale = 1 }: Props) {
  const kind = antennaKind(preset);
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
      <AntennaGlyph kind={kind} az={az} color={c} scale={scale} rows={preset?.rows} cols={preset?.cols} />
      <Text position={[0, (kind === 'mmimo' ? 2.9 : 2.4) * scale, 0]} fontSize={0.6 * scale} color="#ffffff" outlineWidth={0.04 * scale} outlineColor="#0b0f14" anchorX="center">{`${gnb.name} / ${cell.name}  pci ${cell.pci} · ${ANTENNA_KIND_LABEL[kind]}`}</Text>
    </group>
  );
}
