'use client';
import { Text } from '@react-three/drei';
import * as THREE from 'three';
import { useContext } from 'react';
import { useThree } from '@react-three/fiber';
import { SurfaceClip, surfaceBelow, useSurfaceDrag } from '@/components/scene-canvas/surface';
import type { Gnb } from '@/types/registry';

interface Props { gnb: Gnb; color: [number, number, number]; selected: boolean; onSelect: () => void; onMoved: (p: [number, number, number]) => void; scale?: number; }

/** gNB = 群組中心(邏輯網元),畫成細塔;拖塔底圓環移動整座站(共站 cell 跟著走),貼齊滑鼠下的表面。 */
export function GnbGroupMarker({ gnb, color, selected, onSelect, onMoved, scale = 1 }: Props) {
  const raw = gnb.position && gnb.position.length === 3 ? gnb.position : [0, 0, 0];
  const { pos: p, handlers } = useSurfaceDrag([raw[0], raw[1], raw[2]], onMoved);
  const c = new THREE.Color(...color);
  const { scene } = useThree(); const clip = useContext(SurfaceClip);
  // 塔從正下方的表面(地面 / 屋頂)立到天線高度 p[1];拖曳把手在塔底
  const base = Math.min(surfaceBelow(p[0], p[2], scene, clip), p[1]);
  const h = Math.max(p[1] - base, 0.5);
  return (
    <group position={[p[0], base, p[2]]} onClick={(e) => { e.stopPropagation(); onSelect(); }}>
      <mesh position={[0, h / 2, 0]}>
        <cylinderGeometry args={[0.08 * scale, 0.2 * scale, h, 12]} />
        <meshStandardMaterial color={c} emissive={c} emissiveIntensity={selected ? 1 : 0.4} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]} {...handlers}>
        <circleGeometry args={[0.9 * scale, 32]} />
        <meshBasicMaterial color={c} transparent opacity={0.8} />
      </mesh>
      <Text position={[0, h + 1.8 * scale, 0]} fontSize={0.9 * scale} color="#ffffff" outlineWidth={0.05 * scale} outlineColor="#0b0f14" anchorX="center">{gnb.name}</Text>
    </group>
  );
}
