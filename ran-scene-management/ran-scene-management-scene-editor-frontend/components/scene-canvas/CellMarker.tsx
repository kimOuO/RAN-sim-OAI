'use client';
import { useRef, useState } from 'react';
import { useThree, type ThreeEvent } from '@react-three/fiber';
import { Text } from '@react-three/drei';
import * as THREE from 'three';
import { CANVAS } from '@/config';
import type { Cell, Gnb } from '@/types/registry';

interface Props { cell: Cell; gnb: Gnb; color: [number, number, number]; position: [number, number, number]; selected: boolean; onSelect: () => void; onMoved: (p: [number, number, number]) => void; }

/** Cell = 畫布上真正可拖的節點(§3):拖動只改 x/z,y 沿用;放開才寫回。方位角用一根短棒示意。 */
export function CellMarker({ cell, gnb, color, position, selected, onSelect, onMoved }: Props) {
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
        <cylinderGeometry args={[CANVAS.cellMarkerRadius, CANVAS.cellMarkerRadius, 0.6, 24]} />
        <meshStandardMaterial color={c} emissive={selected ? c : '#000'} emissiveIntensity={selected ? 0.5 : 0} />
      </mesh>
      <mesh position={[Math.sin(az) * 2, 0.3, -Math.cos(az) * 2]} rotation={[0, -az, 0]}>
        <boxGeometry args={[0.25, 0.25, 4]} />
        <meshStandardMaterial color={c} />
      </mesh>
      <Text position={[0, 1.6, 0]} fontSize={0.8} color="#222" anchorX="center">{`${gnb.name} / ${cell.name}  pci ${cell.pci}`}</Text>
    </group>
  );
}
