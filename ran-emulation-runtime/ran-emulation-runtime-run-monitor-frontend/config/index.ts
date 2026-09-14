export const REGISTRY_API = `${process.env.NEXT_PUBLIC_REGISTRY_BASE_URL ?? 'http://localhost:8301'}/api/v0.1/Network_element_registry`;
export const ORCHESTRATOR_API = `${process.env.NEXT_PUBLIC_ORCHESTRATOR_BASE_URL ?? 'http://localhost:8302'}/api/v0.1/Run_orchestrator`;
export const DU_API = `${process.env.NEXT_PUBLIC_DU_BASE_URL ?? 'http://localhost:8102'}/api/v0.1/DU`;
export const UE_API = `${process.env.NEXT_PUBLIC_UE_BASE_URL ?? 'http://localhost:8105'}/api/v0.1/UE`;
export const E2ADAPTER_API = `${process.env.NEXT_PUBLIC_E2ADAPTER_BASE_URL ?? 'http://localhost:8201'}/api/v0.1/E2Adapter`;
/** per-run 容器對外的 host(orchestrator 動態配 host port,寫在 registry run_instance) */
export const RUNTIME_HOST = process.env.NEXT_PUBLIC_RUNTIME_HOST ?? 'localhost';
export const POLL_MS = 3000;
/** 時間範圍選項(視窗數;1 視窗 = 1 s sim-time)。0 = 全部 */
export const RANGE_OPTIONS = [{ label: '1m', windows: 60 }, { label: '5m', windows: 300 }, { label: '15m', windows: 900 }, { label: '全部', windows: 0 }] as const;
/** 類別色:固定順序、不循環(dataviz 規則);cell 依名稱排序後對應 slot */
export const SERIES = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'] as const;
export const STATUS = { good: '#0ca30c', warning: '#fab219', serious: '#ec835a', critical: '#d03b3b' } as const;
/** per-UE 指標定義:哪些能畫、單位、量程 */
export const UE_METRICS = [
  { key: 'sinr_db', label: 'SINR', unit: 'dB', min: -10, max: 40 }, { key: 'rsrp_dbm', label: 'RSRP', unit: 'dBm', min: -130, max: -60 },
  { key: 'throughput_dl_mbps', label: 'Thp DL', unit: 'Mbps', min: 0 }, { key: 'mcs_dl', label: 'MCS DL', unit: '', min: 0, max: 28 },
  { key: 'ul_sinr_db', label: 'UL SINR', unit: 'dB', min: -10, max: 40 }, { key: 'mcs_ul', label: 'MCS UL', unit: '', min: 0, max: 28 }, { key: 'rb_width_ul', label: 'PRB UL', unit: '', min: 0 },
  { key: 'rb_width_dl', label: 'PRB DL', unit: '', min: 0 }, { key: 'rlc_sdu_delay_dl_ms', label: 'RLC delay', unit: 'ms', min: 0 },
  { key: 'throughput_ul_mbps', label: 'Thp UL', unit: 'Mbps', min: 0 }, { key: 'pdcp_sdu_volume_dl', label: 'PDCP vol DL', unit: 'B', min: 0 }, { key: 'pdcp_sdu_volume_ul', label: 'PDCP vol UL', unit: 'B', min: 0 },
] as const;
export type UeMetricKey = (typeof UE_METRICS)[number]['key'];
