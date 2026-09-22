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
// 2026-09-22:分類改為資料(Scene.category),沒宣告才退回前綴規則 —— 外部 Agent 的 I-1 用同一套。
export const categoryOfScene = (s: { category?: string | null; legacy_scenario_id: string }) => s.category || categoryOf(s.legacy_scenario_id);
export const CATEGORY_OPTIONS = [...SCENE_CATEGORIES.map((c) => ({ key: c.key, label: c.label })), { key: 'other', label: '其他' }];
/** run_knob 可調鍵(§計畫 run knobs);值以字串存,型別由模擬端解析 */
export const RUN_KNOB_KEYS = ['inter_freq', 'cell_quotas', 'tx_power_dbm', 'discard_timer_ms', 'rlc_delay_model', 'antenna_pattern', 'default_serving_cell', 'trigger_config', 'anr_fixture', 'ric_purpose', 'anr_auto_add', 'anr_pci_lookup', 'anr_cgi_fail_rate'] as const;   // ric_purpose='validation' → RIC 端才會主動探測
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

/** 從地圖建立場景 */
export const MAP_TAIWAN = { lat: 23.7, lon: 120.95, zoom: 7 } as const;
/** 範圍上限(與後端 OsmMapEditor.MAX_AREA_M2 相同):超過 Overpass 與光追都太重 */
export const MAX_MAP_AREA_M2 = 1_000_000;
/** 底圖:深色(預設,配合編輯器)/ OSM 標準(地標文字較清楚) */
export const MAP_BASEMAPS = {
  dark: { url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', attribution: '&copy; OpenStreetMap contributors &copy; CARTO', label: '深色' },
  osm: { url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: '&copy; OpenStreetMap contributors', label: 'OSM' },
} as const;
/** 材質顯示色(與後端 osm_to_mitsuba.DISPLAY_RGB 一致;只影響畫面,傳播用 ITU 參數) */
export const MATERIAL_COLORS: Record<string, string> = {
  concrete: '#9e9e99', brick: '#a8543d', glass: '#73b8d9', metal: '#8c94a8', wood: '#9e7347', marble: '#d9d6cc',
  plasterboard: '#dbdbd1', ceiling_board: '#ccccc2', chipboard: '#b89466', floorboard: '#946b42',
  very_dry_ground: '#8a7a5c', medium_dry_ground: '#6e6048', wet_ground: '#4f4636',
};
export const MATERIAL_LABELS: Record<string, string> = {
  concrete: '混凝土', brick: '磚', glass: '玻璃', metal: '金屬', wood: '木材', marble: '大理石', plasterboard: '石膏板',
  ceiling_board: '天花板', chipboard: '塑合板', floorboard: '地板', very_dry_ground: '極乾地面', medium_dry_ground: '中乾地面', wet_ground: '濕地面',
};

/** DU 排程器(對應 DU 的 SIM_SCHEDULER) */
export const SCHEDULERS = [
  { key: 'pf', label: 'PF 比例公平(預設)' },
  { key: 'rr', label: 'Round Robin 輪流' },
  { key: 'max_thp', label: 'Max Throughput 最大吞吐' },
] as const;
