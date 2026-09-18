'use client';
import { createContext, useContext, useRef, useState } from 'react';
import { useThree, type ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';

/** 可放置 / 貼齊的表面(場景模型、建築盒)在 userData 標這個旗標 */
export const SURFACE_FLAG = 'placeSurface';
/** gNB 放下時在表面上方的高度(屋頂桅杆 / 室內吸頂);UE 手持高度 */
export const GNB_ABOVE_SURFACE_M = 3;
export const UE_ABOVE_SURFACE_M = 1.5;

/** 目前的剖面高度:開剖面時只貼齊剖面以下的幾何(室內場景才會落在地板而不是天花板) */
export const SurfaceClip = createContext<number | null>(null);

function surfaces(scene: THREE.Object3D): THREE.Object3D[] {
  const out: THREE.Object3D[] = [];
  scene.traverse((o) => { if (o.userData?.[SURFACE_FLAG] && o.visible) out.push(o); });
  return out;
}

const caster = new THREE.Raycaster();
/** 沿射線找第一個表面點(剖面以上的忽略);沒打到任何表面 → 落在 y = 0 地面 */
export function pickSurface(ray: THREE.Ray, scene: THREE.Object3D, clipY: number | null): THREE.Vector3 | null {
  caster.ray.copy(ray);
  const hit = caster.intersectObjects(surfaces(scene), false).find((h) => clipY == null || h.point.y <= clipY + 1e-3);
  if (hit) return hit.point.clone();
  const p = new THREE.Vector3();
  return ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), p) ? p : null;
}

/** (x, z) 正下方的表面高度(從剖面或高空往下打) */
export function surfaceBelow(x: number, z: number, scene: THREE.Object3D, clipY: number | null): number {
  const top = clipY ?? 1e4;
  const p = pickSurface(new THREE.Ray(new THREE.Vector3(x, top, z), new THREE.Vector3(0, -1, 0)), scene, clipY);
  return p ? p.y : 0;
}

/** 拖曳貼齊表面:拖動時 x/z 跟著滑鼠落點,y = 落點表面高度 + 拖曳開始時離表面的高度(天線掛高不變)。放開才回呼。 */
export function useSurfaceDrag(position: [number, number, number], onMoved: (p: [number, number, number]) => void) {
  const { camera, gl, scene, controls } = useThree();
  const clipY = useContext(SurfaceClip);
  const [drag, setDrag] = useState<[number, number, number] | null>(null);
  const offset = useRef(0);
  const ndcRay = (e: ThreeEvent<PointerEvent>) => {
    const r = gl.domElement.getBoundingClientRect();
    caster.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
    return caster.ray.clone();
  };
  const setControls = (on: boolean) => { if (controls) (controls as unknown as { enabled: boolean }).enabled = on; };
  const handlers = {
    onPointerDown: (e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation(); (e.target as Element).setPointerCapture?.(e.pointerId);
      offset.current = position[1] - surfaceBelow(position[0], position[2], scene, clipY);
      setControls(false); setDrag(position);
    },
    onPointerMove: (e: ThreeEvent<PointerEvent>) => {
      if (!drag) return;
      const p = pickSurface(ndcRay(e), scene, clipY);
      if (p) setDrag([p.x, p.y + offset.current, p.z]);
    },
    onPointerUp: (e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation(); setControls(true);
      if (drag) { const moved = Math.hypot(drag[0] - position[0], drag[2] - position[2]) > 0.05 || Math.abs(drag[1] - position[1]) > 0.05; if (moved) onMoved(drag); setDrag(null); }
    },
  };
  return { pos: drag ?? position, dragging: drag != null, handlers };
}
