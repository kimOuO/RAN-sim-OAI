'use client';
import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import type { CoverageResult } from '@/services/api/coverage';

export type CoverageMode = 'rsrp' | 'sinr' | 'cell';

/** 監控端的覆蓋熱圖圖層 —— 與編輯器 components/scene-canvas/CoverageLayer.tsx 同源。
 *  兩個 app 沒有共用套件,改動要兩邊一起。 */
/** 色階範圍與配色:RSRP / SINR 用連續色(暗紫→黃),最佳 cell 用類別色 */
export const COVERAGE_SCALE: Record<Exclude<CoverageMode, 'cell'>, { min: number; max: number; unit: string }> = {
  rsrp: { min: -120, max: -30, unit: 'dBm' }, sinr: { min: -10, max: 30, unit: 'dB' },
};
export const CELL_COLORS = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'];
const STOPS = ['#30123b', '#4662d7', '#36aaf9', '#1ae4b6', '#72fe5e', '#c7ef34', '#fbb938', '#f56918', '#c92903'];
const stops = STOPS.map((c) => new THREE.Color(c));
export const rampColor = (f: number, out = new THREE.Color()) => {
  const x = Math.max(0, Math.min(1, f)) * (stops.length - 1); const i = Math.min(stops.length - 2, Math.floor(x));
  return out.copy(stops[i]).lerp(stops[i + 1], x - i);
};
export const RAMP_CSS = `linear-gradient(90deg, ${STOPS.join(', ')})`;

/** 覆蓋熱圖:一張 DataTexture 鋪在取樣高度的水平面上 */
export function CoverageLayer({ result, mode, opacity }: { result: CoverageResult; mode: CoverageMode; opacity: number }) {
  const { grid, summary } = result;
  const texture = useMemo(() => {
    const src = mode === 'rsrp' ? summary.best_rsrp_dbm : mode === 'sinr' ? summary.sinr_db : summary.best_cell;
    const rows = src.length, cols = src[0]?.length ?? 0;
    const data = new Uint8Array(rows * cols * 4); const c = new THREE.Color(); const cellCols = CELL_COLORS.map((x) => new THREE.Color(x));
    for (let r = 0; r < rows; r++) for (let k = 0; k < cols; k++) {
      const v = src[r][k]; const o = ((rows - 1 - r) * cols + k) * 4;   // 貼圖第 0 列在平面下緣 = z 最大 → 列要反過來
      if (v == null) { data[o + 3] = 0; continue; }
      if (mode === 'cell') c.copy(cellCols[v % cellCols.length]);
      else { const s = COVERAGE_SCALE[mode]; rampColor((v - s.min) / (s.max - s.min), c); }
      data[o] = c.r * 255; data[o + 1] = c.g * 255; data[o + 2] = c.b * 255; data[o + 3] = 255;
    }
    const t = new THREE.DataTexture(data, cols, rows, THREE.RGBAFormat);
    t.magFilter = mode === 'cell' ? THREE.NearestFilter : THREE.LinearFilter; t.needsUpdate = true;
    return t;
  }, [summary, mode]);
  useEffect(() => () => texture.dispose(), [texture]);
  const [x0, x1] = grid.x_range, [z0, z1] = grid.z_range;
  return (
    <mesh position={[(x0 + x1) / 2, grid.sample_height_m, (z0 + z1) / 2]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={2}>
      <planeGeometry args={[x1 - x0, z1 - z0]} />
      <meshBasicMaterial map={texture} transparent opacity={opacity} side={THREE.DoubleSide} depthWrite={false} toneMapped={false} />
    </mesh>
  );
}
