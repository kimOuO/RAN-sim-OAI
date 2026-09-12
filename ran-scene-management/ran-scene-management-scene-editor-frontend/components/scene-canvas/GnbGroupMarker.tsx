'use client';
import { Text } from '@react-three/drei';
import * as THREE from 'three';
import type { Gnb } from '@/types/registry';

interface Props { gnb: Gnb; color: [number, number, number]; selected: boolean; onSelect: () => void; onMoved: (p: [number, number, number]) => void; }

/** gNB = 群組中心(邏輯網元),畫成細塔;拖動 gNB 由屬性面板改座標(P3-1 先不做拖曳,避免與 cell 拖曳衝突)。 */
export function GnbGroupMarker({ gnb, color, selected, onSelect }: Props) {
  const p = gnb.position && gnb.position.length === 3 ? gnb.position : [0, 0, 0];
  const c = new THREE.Color(...color);
  return (
    <group position={[p[0], p[1], p[2]]} onClick={(e) => { e.stopPropagation(); onSelect(); }}>
      <mesh position={[0, 4, 0]}>
        <cylinderGeometry args={[0.15, 0.3, 8, 12]} />
        <meshStandardMaterial color={c} emissive={selected ? c : '#000'} emissiveIntensity={selected ? 0.6 : 0} />
      </mesh>
      <Text position={[0, 9, 0]} fontSize={1} color="#111" anchorX="center">{gnb.name}</Text>
    </group>
  );
}
