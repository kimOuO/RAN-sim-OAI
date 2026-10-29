'use client';
import * as THREE from 'three';
import type { AntennaPresetLite as AntennaPreset } from '@/types/telemetry';

export type AntennaKind = 'omni' | 'sector' | 'mmimo';
/** 天線外觀分類:iso / dipole = 全向;TR 38.901 方向圖 = 扇區;元件數 ≥ 32(8×4 以上)= mMIMO 面板 */
export function antennaKind(p: Pick<AntennaPreset, 'pattern' | 'rows' | 'cols'> | null | undefined): AntennaKind {
  if (!p || p.pattern !== 'tr38901') return p ? 'omni' : 'sector';   // 沒指定時 physics 預設 TR 38.901 扇區
  return (p.rows ?? 1) * (p.cols ?? 1) >= 32 ? 'mmimo' : 'sector';
}
export const ANTENNA_KIND_LABEL: Record<AntennaKind, string> = { omni: '全向', sector: '扇區', mmimo: 'mMIMO' };

/** cell 的天線外觀:全向 = 直立偶極 + 水平環(無方向);扇區 = 朝方位角的直立面板;mMIMO = 較大面板 + 元件格點。
 *  az 為方位角(弧度,0 = 北 = −z,順時針);面板法線朝方位角方向。 */
export function AntennaGlyph({ kind, az, color, scale = 1, rows = 1, cols = 1 }: { kind: AntennaKind; az: number; color: THREE.Color; scale?: number; rows?: number; cols?: number }) {
  const dir: [number, number, number] = [Math.sin(az), 0, -Math.cos(az)];
  if (kind === 'omni') return (
    <group>
      <mesh position={[0, 1.0 * scale, 0]}><cylinderGeometry args={[0.07 * scale, 0.07 * scale, 1.6 * scale, 8]} /><meshStandardMaterial color={color} /></mesh>
      <mesh position={[0, 1.85 * scale, 0]}><sphereGeometry args={[0.16 * scale, 12, 12]} /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.6} /></mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.05, 0]}><ringGeometry args={[1.6 * scale, 1.9 * scale, 48]} /><meshBasicMaterial color={color} transparent opacity={0.45} side={THREE.DoubleSide} /></mesh>
    </group>);
  const big = kind === 'mmimo'; const w = (big ? 2.2 : 1.0) * scale, h = (big ? 2.2 : 1.8) * scale, off = 0.6 * scale;
  const n1 = big ? Math.min(cols, 8) : 0, n2 = big ? Math.min(rows, 8) : 0;
  return (
    <group position={[dir[0] * off, h / 2, dir[2] * off]} rotation={[0, -az, 0]}>
      <mesh><boxGeometry args={[w, h, 0.18 * scale]} /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.25} /></mesh>
      {big && Array.from({ length: n1 * n2 }, (_, k) => { const i = k % n1, j = Math.floor(k / n1);
        // 元件格點兩面都畫(不論從哪一側看都認得出是陣列面板)
        return <mesh key={k} position={[(-w / 2) + (w * (i + 0.5)) / n1, (-h / 2) + (h * (j + 0.5)) / n2, 0]}><boxGeometry args={[w / n1 * 0.55, h / n2 * 0.55, 0.22 * scale]} /><meshStandardMaterial color="#0b0f14" /></mesh>; })}
      <mesh position={[0, 0, -1.6 * scale]}><boxGeometry args={[0.12 * scale, 0.12 * scale, 2.6 * scale]} /><meshStandardMaterial color={color} /></mesh>
    </group>);
}
