'use client';
import { Text } from '@react-three/drei';
import * as THREE from 'three';
import type { Gnb } from '@/types/registry';

interface Props { gnb: Gnb; color: [number, number, number]; selected: boolean; onSelect: () => void; onMoved: (p: [number, number, number]) => void; scale?: number; }

/** gNB = 群組中心(邏輯網元),畫成細塔;拖動 gNB 由屬性面板改座標(P3-1 先不做拖曳,避免與 cell 拖曳衝突)。 */
export function GnbGroupMarker({ gnb, color, selected, onSelect, scale = 1 }: Props) {
  const p = gnb.position && gnb.position.length === 3 ? gnb.position : [0, 0, 0];
  const c = new THREE.Color(...color);
  // 塔從地面(y=0)立到天線高度 p[1];以前是從 p[1] 再往上畫 8 m,整根浮在空中
  const h = Math.max(p[1], 0.5);
  return (
    <group position={[p[0], 0, p[2]]} onClick={(e) => { e.stopPropagation(); onSelect(); }}>
      <mesh position={[0, h / 2, 0]}>
        <cylinderGeometry args={[0.08 * scale, 0.2 * scale, h, 12]} />
        <meshStandardMaterial color={c} emissive={c} emissiveIntensity={selected ? 1 : 0.4} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <ringGeometry args={[0.5 * scale, 0.7 * scale, 32]} />
        <meshBasicMaterial color={c} transparent opacity={0.8} />
      </mesh>
      <Text position={[0, h + 1.8 * scale, 0]} fontSize={0.9 * scale} color="#ffffff" outlineWidth={0.05 * scale} outlineColor="#0b0f14" anchorX="center">{gnb.name}</Text>
    </group>
  );
}
