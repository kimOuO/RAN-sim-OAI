'use client';
import { useEffect, useRef, useState } from 'react';
import { loadSceneMesh } from '@/components/scene3d/SceneMeshes';
import { listSceneMeshes } from '@/services/api/runs';
import type { SceneTree3d } from '@/types/telemetry';

/** 場景網格的俯視投影:牆(近垂直面)投成線段 → 平面圖;屋頂 / 地板(近水平面)淡填色。 */
interface Footprint { walls: Float32Array; flats: Float32Array; box: [number, number, number, number] }
const MAX_TRI = 300_000;
const cache = new Map<string, Promise<Footprint | null>>();

async function buildFootprint(sceneUuid: string): Promise<Footprint | null> {
  const list = (await listSceneMeshes(sceneUuid)).filter((s) => !s.too_large);
  const walls: number[] = [], flats: number[] = [];
  let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
  for (const s of list) {
    let g;
    try { g = await loadSceneMesh(sceneUuid, s); } catch { continue; }
    const pos = g.attributes.position; if (!pos) continue;
    const idx = g.index; const n = idx ? idx.count / 3 : pos.count / 3;
    const step = Math.max(1, Math.ceil(n / MAX_TRI));
    const v = (k: number) => (idx ? idx.getX(k) : k);
    for (let t = 0; t < n; t += step) {
      const a = v(3 * t), b = v(3 * t + 1), c = v(3 * t + 2);
      const ax = pos.getX(a), ay = pos.getY(a), az = pos.getZ(a), bx = pos.getX(b), by = pos.getY(b), bz = pos.getZ(b), cx = pos.getX(c), cy = pos.getY(c), cz = pos.getZ(c);
      // 法向量的 y 分量(未正規化)判斷牆 / 水平面
      const ux = bx - ax, uy = by - ay, uz = bz - az, wx = cx - ax, wy = cy - ay, wz = cz - az;
      const nx = uy * wz - uz * wy, ny = uz * wx - ux * wz, nz = ux * wy - uy * wx;
      const len = Math.hypot(nx, ny, nz); if (!len) continue;
      if (Math.abs(ny) / len < 0.3) {
        // 牆:三個頂點投到 xz 後取最長的一邊
        const d1 = Math.hypot(bx - ax, bz - az), d2 = Math.hypot(cx - bx, cz - bz), d3 = Math.hypot(ax - cx, az - cz);
        if (d1 >= d2 && d1 >= d3) walls.push(ax, az, bx, bz); else if (d2 >= d3) walls.push(bx, bz, cx, cz); else walls.push(cx, cz, ax, az);
      } else flats.push(ax, az, bx, bz, cx, cz);
      x0 = Math.min(x0, ax, bx, cx); x1 = Math.max(x1, ax, bx, cx); z0 = Math.min(z0, az, bz, cz); z1 = Math.max(z1, az, bz, cz);
    }
    g.dispose();
  }
  if (!walls.length && !flats.length) return null;
  return { walls: new Float32Array(walls), flats: new Float32Array(flats), box: [x0, x1, z0, z1] };
}

function useFootprint(sceneUuid: string | undefined, enabled: boolean) {
  const [fp, setFp] = useState<Footprint | null>(null);
  useEffect(() => {
    if (!sceneUuid || !enabled) return;
    let alive = true;
    if (!cache.has(sceneUuid)) cache.set(sceneUuid, buildFootprint(sceneUuid).catch(() => null));
    cache.get(sceneUuid)!.then((f) => { if (alive) setFp(f); });
    return () => { alive = false; };
  }, [sceneUuid, enabled]);
  return fp;
}

/** 場景俯視縮圖(回放清單用):建築 / 掃描模型輪廓、UE 路徑、gNB 位置。 */
export function SceneThumb({ tree, w = 360, h = 150 }: { tree: SceneTree3d | null | undefined; w?: number; h?: number }) {
  const hasGeo = !!(tree?.scene.geometry_source as { type?: string } | null)?.type;
  const fp = useFootprint(tree?.scene.scene_uuid, hasGeo);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const xs: number[] = [], zs: number[] = [];
  tree?.gnbs.forEach((g) => { xs.push(g.position[0]); zs.push(g.position[2]); });
  tree?.ues.forEach((u) => u.waypoints.forEach((p) => { xs.push(p[1]); zs.push(p[3]); }));
  tree?.buildings.forEach((b) => { if (b.size?.length === 3) { xs.push(b.position[0] - b.size[0] / 2, b.position[0] + b.size[0] / 2); zs.push(b.position[2] - b.size[2] / 2, b.position[2] + b.size[2] / 2); } });
  let x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs);
  if (fp) {
    // 模型可能比 UE / gNB 範圍大很多(OSM 一整片街區):往外最多擴到元件範圍的一倍
    const sp = Math.max(x1 - x0, z1 - z0, 20);
    const [mx0, mx1, mz0, mz1] = fp.box;
    if (!xs.length) { x0 = mx0; x1 = mx1; z0 = mz0; z1 = mz1; }
    else { x0 = Math.max(Math.min(x0, mx0), x0 - sp); x1 = Math.min(Math.max(x1, mx1), x1 + sp); z0 = Math.max(Math.min(z0, mz0), z0 - sp); z1 = Math.min(Math.max(z1, mz1), z1 + sp); }
  }
  const ok = Number.isFinite(x0) && Number.isFinite(z0);
  const span = ok ? Math.max(x1 - x0, z1 - z0, 1) : 1, pad = 8;
  const k = ok ? Math.min((w - 2 * pad) / Math.max(x1 - x0, span * 0.2), (h - 2 * pad) / Math.max(z1 - z0, span * 0.2)) : 1;
  const X = (x: number) => pad + (x - x0) * k + ((w - 2 * pad) - (x1 - x0) * k) / 2;
  const Z = (z: number) => pad + (z - z0) * k + ((h - 2 * pad) - (z1 - z0) * k) / 2;

  useEffect(() => {
    const cv = canvasRef.current; if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = w * dpr; cv.height = h * dpr;
    const ctx = cv.getContext('2d'); if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
    if (!fp) return;
    ctx.fillStyle = 'rgba(79,209,255,0.05)';
    const f = fp.flats;
    for (let i = 0; i < f.length; i += 6) {
      ctx.beginPath(); ctx.moveTo(X(f[i]), Z(f[i + 1])); ctx.lineTo(X(f[i + 2]), Z(f[i + 3])); ctx.lineTo(X(f[i + 4]), Z(f[i + 5])); ctx.fill();
    }
    ctx.strokeStyle = 'rgba(127,227,255,0.45)'; ctx.lineWidth = 0.7; ctx.beginPath();
    const ww = fp.walls;
    for (let i = 0; i < ww.length; i += 4) { ctx.moveTo(X(ww[i]), Z(ww[i + 1])); ctx.lineTo(X(ww[i + 2]), Z(ww[i + 3])); }
    ctx.stroke();
  });

  if (!tree) return <div className="thumb empty" style={{ aspectRatio: `${w} / ${h}` }}><span className="muted small">載入場景…</span></div>;
  if (!ok) return <div className="thumb empty" style={{ aspectRatio: `${w} / ${h}` }}><span className="muted small">無場景元件</span></div>;
  return (
    <div className="thumb thumb-stack" style={{ aspectRatio: `${w} / ${h}` }}>
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label="場景俯視圖">
        {tree.buildings.filter((b) => b.size?.length === 3).map((b) => <rect key={b.building_uuid} x={X(b.position[0] - b.size[0] / 2)} y={Z(b.position[2] - b.size[2] / 2)} width={Math.max(1, b.size[0] * k)} height={Math.max(1, b.size[2] * k)} className="bld" />)}
        {tree.ues.filter((u) => u.waypoints.length > 1).map((u) => <polyline key={u.ue_uuid} points={u.waypoints.map((p) => `${X(p[1]).toFixed(1)},${Z(p[3]).toFixed(1)}`).join(' ')} className="path" />)}
        {tree.ues.filter((u) => u.waypoints.length === 1).map((u) => <circle key={u.ue_uuid} cx={X(u.waypoints[0][1])} cy={Z(u.waypoints[0][3])} r={1.8} className="ue" />)}
        {tree.gnbs.map((g) => <g key={g.gnb_uuid}><circle cx={X(g.position[0])} cy={Z(g.position[2])} r={4.5} className="gnb" /><text x={X(g.position[0]) + 6} y={Z(g.position[2]) + 3} className="lbl">{g.name}</text></g>)}
      </svg>
    </div>
  );
}
