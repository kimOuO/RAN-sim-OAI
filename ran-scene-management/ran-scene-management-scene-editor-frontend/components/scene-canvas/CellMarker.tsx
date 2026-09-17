'use client';
import { useRef, useState } from 'react';
import { useThree, type ThreeEvent } from '@react-three/fiber';
import { Text } from '@react-three/drei';
import * as THREE from 'three';
import { CANVAS } from '@/config';
import type { Cell, Gnb } from '@/types/registry';

interface Props { cell: Cell; gnb: Gnb; color: [number, number, number]; position: [number, number, number]; selected: boolean; onSelect: () => void; onMoved: (p: [number, number, number]) => void; scale?: number; }

/** Cell = 畫布上真正可拖的節點(§3):拖動只改 x/z,y 沿用;放開才寫回。方位角用一根短棒示意。 */
export function CellMarker({ cell, gnb, color, position, selected, onSelect, onMoved, scale = 1 }: Props) {
  const [drag, setDrag] = useState<[number, number, number] | null>(null);
  const { camera, gl } = useThree();
  const plane = useRef(new THREE.Plane(new THREE.Vector3(0, 1, 0), -position[1]));
  const ray = useRef(new THREE.Raycaster());
  const hit = useRef(new THREE.Vector3());
  function toGround(e: ThreeEvent<PointerEvent>): [number, number, number] | null {
    const rect = gl.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    ray.current.setFromCamera(ndc, camera);
    return ray.current.ray.intersectPlane(plane.current, hit.current) ? [hit.current.x, position[1], hit.current.z] : null;
  }
  const pos = drag ?? position;
  const az = (cell.azimuth_deg * Math.PI) / 180;
  const c = new THREE.Color(...color);
  return (
    <group position={pos}>
      <mesh
        onClick={(e) => { e.stopPropagation(); onSelect(); }}
        onPointerDown={(e) => { e.stopPropagation(); (e.target as Element).setPointerCapture?.(e.pointerId); setDrag(position); }}
        onPointerMove={(e) => { if (drag) { const p = toGround(e); if (p) setDrag(p); } }}
        onPointerUp={(e) => { e.stopPropagation(); if (drag) { onMoved(drag); setDrag(null); } }}
      >
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
