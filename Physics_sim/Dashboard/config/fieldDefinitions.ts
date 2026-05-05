/**
 * 可编辑字段定义 - 基于 EDITABLE_FIELDS.md
 */

// Sionna 支持的材质类型（对应 mitsuba_builder.py 的 MATERIAL_MAP）
export const SIONNA_MATERIALS = [
  { value: 'concrete', label: 'Concrete（混凝土）', isDefault: true },
  { value: 'brick', label: 'Brick（砖）' },
  { value: 'glass', label: 'Glass（玻璃）' },
  { value: 'metal', label: 'Metal（金属）' },
  { value: 'wood', label: 'Wood（木材）' },
];

// ITU-R P.2040 材质合法频率范围（GHz）。
// 来源：sionna/rt/radio_materials/itu.py:ITU_MATERIALS_PROPERTIES
// 後端 scene_frequency.py 用同一份事實做 server-side 驗證。
// 同一材质可能有多段不连续的合法区间（例 glass: 0.1–100 ∪ 220–450）。
export const ITU_MATERIAL_RANGES: Record<string, [number, number][]> = {
  concrete: [[1.0, 100.0]],
  brick: [[1.0, 40.0]],
  glass: [[0.1, 100.0], [220.0, 450.0]],
  metal: [[1.0, 100.0]],
  wood: [[0.001, 100.0]],
};

export function isFrequencyValidForMaterial(freqGhz: number, material: string): boolean {
  const ranges = ITU_MATERIAL_RANGES[material];
  if (!ranges) return true; // 自訂或未知材質,前端不擋,交給後端
  return ranges.some(([lo, hi]) => freqGhz >= lo && freqGhz <= hi);
}

export function isFrequencyValidForMaterials(freqGhz: number, materials: string[]): boolean {
  return materials.every(m => isFrequencyValidForMaterial(freqGhz, m));
}

export function isMaterialValidForFrequencies(material: string, freqsGhz: number[]): boolean {
  return freqsGhz.every(f => isFrequencyValidForMaterial(f, material));
}

export function formatRangesForMaterial(material: string): string {
  const ranges = ITU_MATERIAL_RANGES[material];
  if (!ranges) return 'unknown';
  return ranges.map(([lo, hi]) => `${lo}–${hi} GHz`).join(', ');
}

// 5G NR 频段预设 (gNB)
export const GNB_FREQUENCY_PRESETS = [
  { value: 0.617, label: 'n71 (617 MHz) - Broadband' },
  { value: 2.5, label: 'n41 (2.5 GHz) - Midband' },
  { value: 3.5, label: 'n78 (3.5 GHz) - Urban (default)', isDefault: true },
  { value: 3.8, label: 'n77 (3.8 GHz) - Urban' },
  { value: 4.7, label: 'n79 (4.7 GHz) - mmWave' },
];

// GNB 带宽预设
export const GNB_BANDWIDTH_PRESETS = [
  { frequency: 0.617, bandwidth: 20, label: 'n71 Standard' },
  { frequency: 2.5, bandwidth: 100, label: 'n41 Standard' },
  { frequency: 3.5, bandwidth: 100, label: 'n78 Standard' },
  { frequency: 3.8, bandwidth: 100, label: 'n77 Standard' },
  { frequency: 4.7, bandwidth: 200, label: 'n79 Standard' },
];

// 每个对象类型的可编辑字段定义
// NOTE: position, size, color, rotation, material, usd_path 都由 preset 决定，用户在 ObjectForm 不能调整
// 位置通过 canvas 拖放设置，其他默认值由 UsdAsset 提供
export const EDITABLE_FIELDS_BY_TYPE = {
  building: [
    { name: 'name', label: 'Name', type: 'text', required: true },
    { name: 'material', label: 'Material', type: 'select', required: false, options: SIONNA_MATERIALS },
    // Size, color, rotation, usd_path 由 preset 决定 → 不开放编辑
  ] as FieldDefinition[],

  gnb: [
    { name: 'name', label: 'Name', type: 'text', required: true },
    { name: 'frequency_ghz', label: 'Frequency (GHz)', type: 'select', required: true, options: GNB_FREQUENCY_PRESETS },
    { name: 'power_dbm', label: 'Power (dBm)', type: 'number', required: false, min: 0, max: 46 },
    { name: 'cells', label: 'Cells', type: 'cells', required: false },
    // bandwidth_mhz 由 frequency 自动计算 → 不开放编辑
    // position 通过 canvas 拖放设置
  ] as FieldDefinition[],

  ue: [
    { name: 'name', label: 'Name', type: 'text', required: true },
    { name: 'speed_mps', label: 'Speed (m/s)', type: 'number', required: false, min: 0.1, max: 30 },
    // position 通过 canvas 拖放设置
    // color 由 preset 决定
  ] as FieldDefinition[],

  obstacle: [
    { name: 'name', label: 'Name', type: 'text', required: true },
    { name: 'material', label: 'Material', type: 'select', required: false, options: SIONNA_MATERIALS },
    // position, size, color, usd_path 由 preset 决定 → 不开放编辑
  ] as FieldDefinition[],
};

export interface FieldDefinition {
  name: string;
  label: string;
  type: 'text' | 'number' | 'vector3' | 'color' | 'select' | 'checkbox' | 'cells';
  required: boolean;
  options?: Array<{ value: string | number; label: string; isDefault?: boolean }>;
  min?: number;
  max?: number;
}

// 获取指定类型的可编辑字段
export function getEditableFields(objectType: 'building' | 'gnb' | 'ue' | 'obstacle'): FieldDefinition[] {
  return EDITABLE_FIELDS_BY_TYPE[objectType] || [];
}

// 获取GNB的推荐带宽
export function getRecommendedBandwidth(frequencyGhz: number): number {
  const preset = GNB_BANDWIDTH_PRESETS.find(p => p.frequency === frequencyGhz);
  return preset?.bandwidth || 100; // default to 100 MHz
}
