export const REGISTRY_BASE_URL = process.env.NEXT_PUBLIC_REGISTRY_BASE_URL ?? 'http://localhost:8301';
export const INGEST_BASE_URL = process.env.NEXT_PUBLIC_INGEST_BASE_URL ?? 'http://localhost:8303';
export const ORCHESTRATOR_BASE_URL = process.env.NEXT_PUBLIC_ORCHESTRATOR_BASE_URL ?? 'http://localhost:8302';
export const MONITOR_BASE_URL = process.env.NEXT_PUBLIC_MONITOR_BASE_URL ?? 'http://localhost:3012';
export const REGISTRY_API = `${REGISTRY_BASE_URL}/api/v0.1/Scene_management_backend`;
export const ORCHESTRATOR_API = `${ORCHESTRATOR_BASE_URL}/api/v0.1/Run_orchestrator`;
export const INGEST_API = `${INGEST_BASE_URL}/api/v0.1/Scene_management_backend`;
/** 畫布:1 單位 = 1 公尺;registry 座標 Y-up(x 東、y 上、z 南),與 Sionna/場景檔一致 */
export const CANVAS = { gridSize: 400, cellMarkerRadius: 1.2, ueMarkerRadius: 0.4 } as const;
/** 劇本分類:由 legacy_scenario_id 前綴推導(呈現層),沒有舊 id 的是手動建立 */
export const SCENE_CATEGORIES: { key: string; label: string; test: (id: string) => boolean }[] = [
  { key: 'anr', label: 'ANR', test: (id) => id.startsWith('anr_') },
  { key: 'corridor', label: '走廊 / 室內', test: (id) => id.startsWith('corridor') || id.startsWith('indoor') },
  { key: 'intent', label: '意圖(CCO / IM / ES)', test: (id) => /^(cco|im|es|recover)/.test(id) },
  { key: 'scale', label: '規模 / 全天', test: (id) => /^(dt_|full_day|multi)/.test(id) },
  { key: 'manual', label: '手動建立', test: (id) => !id },
];
export const categoryOf = (legacyId: string) => SCENE_CATEGORIES.find((c) => c.test(legacyId))?.key ?? 'other';
/** run_knob 可調鍵(§計畫 run knobs);值以字串存,型別由模擬端解析 */
export const RUN_KNOB_KEYS = ['inter_freq', 'cell_quotas', 'tx_power_dbm', 'discard_timer_ms', 'rlc_delay_model', 'antenna_pattern', 'default_serving_cell', 'trigger_config', 'anr_fixture'] as const;
export const ANTENNA_PATTERNS = ['iso', 'dipole', 'hw_dipole', 'tr38901'] as const;
export const POLARIZATIONS = ['V', 'H', 'VH', 'cross'] as const;
/** O-RAN WG4 CUS-plane O-RU 類別:A = O-DU 做 precoding;B = O-RU 自己做 beamforming(mMIMO 必須) */
export const RU_CATEGORIES = ['A', 'B'] as const;
/** Cat B 的 beamforming 方法(O-RAN WG4 CUS-plane) */
export const BF_METHODS = ['', 'predefined', 'attribute', 'weight', 'channel_info'] as const;
/** 場景建置四步驟(路由段 / 標題 / 說明) */
export const EDITOR_STEPS = [
  { key: 'environment', label: '1 場景與環境', hint: '地圖 / 匯入 / 建築盒、材質' },
  { key: 'network', label: '2 網路元件', hint: 'gNB / cell / 天線 / 模板' },
  { key: 'ue', label: '3 UE', hint: '路徑 / 流量 / 隨機產生' },
  { key: 'launch', label: '4 模擬與啟動', hint: '模式 / 倍速 / Precompute' },
] as const;
export type EditorStep = (typeof EDITOR_STEPS)[number]['key'];
/** UE 隨機產生器的預設值與情境範本(數值單位:m/s、秒、kbps) */
export interface UeGenParams {
  seed: number; count: number; namePrefix: string; duration: number; speedMin: number; speedMax: number; dwellMax: number;
  dlMin: number; dlMax: number; heavyRatio: number; heavyMin: number; heavyMax: number; ulMin: number; ulMax: number; trafficStep: number;
  qos5qi: number; height: number; xMin: number; xMax: number; zMin: number; zMax: number;
}
export const UE_GEN_DEFAULT: Omit<UeGenParams, 'xMin' | 'xMax' | 'zMin' | 'zMax'> = {
  seed: 1, count: 8, namePrefix: 'u', duration: 600, speedMin: 0.8, speedMax: 1.5, dwellMax: 20,
  dlMin: 50, dlMax: 300, heavyRatio: 0.5, heavyMin: 500, heavyMax: 5000, ulMin: 20, ulMax: 500, trafficStep: 30, qos5qi: 9, height: 1.5,
};
export const UE_SCENARIOS: { key: string; label: string; hint: string; params: Partial<UeGenParams> }[] = [
  { key: 'walk', label: '一般走動', hint: '步行、偶爾停留、中等流量', params: {} },
  { key: 'commute', label: '通勤人流', hint: '連續快走、幾乎不停、瀏覽為主', params: { speedMin: 1.2, speedMax: 1.8, dwellMax: 3, heavyRatio: 0.2 } },
  { key: 'meeting', label: '會議室', hint: '幾乎不動、長時間視訊', params: { speedMin: 0.05, speedMax: 0.3, dwellMax: 120, heavyRatio: 0.8, heavyMin: 1500, heavyMax: 4000 } },
  { key: 'peak', label: '尖峰時段', hint: '人多、流量大', params: { count: 20, heavyRatio: 0.8, heavyMin: 2000, heavyMax: 8000, ulMax: 1500 } },
];
