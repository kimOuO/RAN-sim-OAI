'use client';
import { useEffect, useMemo, useState } from 'react';
import * as THREE from 'three';
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader.js';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import { SURFACE_FLAG } from '@/components/scene-canvas/surface';
import { fetchSceneMeshFile, listSceneMeshes, type SceneMesh, type SceneMeshOp } from '@/services/api/scenes';

/** ITU 材質 → 顯示色(Mitsuba 場景的 reflectance 多半是預設灰,不能拿來分辨) */
const MAT_COLOR: [RegExp, string][] = [[/glass/, '#7fd3ff'], [/wood|floorboard/, '#b98a5a'], [/metal/, '#c0c8d0'], [/brick/, '#b0574a'], [/marble/, '#e0ddd5'], [/plaster|ceiling/, '#d8d4c8'], [/concrete/, '#8f98a3']];
const matColor = (m: string) => MAT_COLOR.find(([r]) => r.test(m))?.[1] ?? '#8f98a3';

function toMatrix(ops: SceneMeshOp[]) {
  const m = new THREE.Matrix4(); const t = new THREE.Matrix4();
  for (const o of ops) {   // Mitsuba:後面的 op 套在前面的結果上 → 左乘
    if (o.op === 'translate' && o.v) t.makeTranslation(o.v[0], o.v[1], o.v[2]);
    else if (o.op === 'scale' && o.v) t.makeScale(o.v[0], o.v[1], o.v[2]);
    else if (o.op === 'rotate' && o.axis) t.makeRotationAxis(new THREE.Vector3(...o.axis).normalize(), THREE.MathUtils.degToRad(o.deg ?? 0));
    else if (o.op === 'matrix' && o.v?.length === 16) t.fromArray(o.v).transpose();   // Mitsuba 列優先
    else continue;
    m.premultiply(t);
  }
  return m;
}

async function load(sceneUuid: string, s: SceneMesh): Promise<THREE.BufferGeometry> {
  const buf = await fetchSceneMeshFile(sceneUuid, s.shape_id);
  let g: THREE.BufferGeometry;
  if (s.format === 'ply') g = new PLYLoader().parse(buf);
  else { const obj = new OBJLoader().parse(new TextDecoder().decode(buf)); const first = obj.children.find((c): c is THREE.Mesh => (c as THREE.Mesh).isMesh); g = first ? first.geometry : new THREE.BufferGeometry(); }
  g.applyMatrix4(toMatrix(s.transform));
  if (!g.attributes.normal) g.computeVertexNormals();
  return g;
}

export interface MeshView { show: boolean; opacity: number; clipY: number | null }

/** 場景幾何(掃描模型 / OSM 建築):半透明 + 邊線;clipY = 只畫這個高度以下(看得到室內) */
export function SceneMeshes({ sceneUuid, view, onInfo }: { sceneUuid: string; view: MeshView; onInfo?: (s: string) => void }) {
  const [meshes, setMeshes] = useState<{ s: SceneMesh; g: THREE.BufferGeometry }[]>([]);
  useEffect(() => {
    let alive = true; setMeshes([]);
    listSceneMeshes(sceneUuid).then(async (list) => {
      const ok = list.filter((s) => !s.too_large);
      if (list.length) onInfo?.(`載入模型 ${ok.length}/${list.length} 個網格…`);
      const out = [];
      for (const s of ok) { try { out.push({ s, g: await load(sceneUuid, s) }); } catch (e) { onInfo?.(`網格 ${s.name} 載入失敗:${e instanceof Error ? e.message : e}`); } if (!alive) return; }
      if (alive) { setMeshes(out); onInfo?.(list.length ? `模型 ${out.length} 個網格${list.length > ok.length ? `(${list.length - ok.length} 個太大略過)` : ''}` : ''); }
    }).catch(() => onInfo?.(''));
    return () => { alive = false; };
  }, [sceneUuid]);   // eslint-disable-line react-hooks/exhaustive-deps
  const plane = useMemo(() => new THREE.Plane(new THREE.Vector3(0, -1, 0), 0), []);
  plane.constant = view.clipY ?? 1e6;
  const clip = view.clipY != null ? [plane] : [];
  if (!view.show) return null;
  return <>{meshes.map(({ s, g }) => (
    <group key={s.shape_id}>
      <mesh geometry={g} userData={{ [SURFACE_FLAG]: true }}>
        <meshStandardMaterial color={matColor(s.material)} transparent opacity={view.opacity} side={THREE.DoubleSide} depthWrite={view.opacity > 0.9} clippingPlanes={clip} />
      </mesh>
      <lineSegments>
        <edgesGeometry args={[g, 30]} />
        <lineBasicMaterial color={matColor(s.material)} transparent opacity={Math.min(1, view.opacity + 0.3)} clippingPlanes={clip} />
      </lineSegments>
    </group>))}</>;
}
