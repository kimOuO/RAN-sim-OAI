export const REGISTRY_API = `${process.env.NEXT_PUBLIC_REGISTRY_BASE_URL ?? 'http://localhost:8301'}/api/v0.1/Network_element_registry`;
export const ORCHESTRATOR_API = `${process.env.NEXT_PUBLIC_ORCHESTRATOR_BASE_URL ?? 'http://localhost:8302'}/api/v0.1/Run_orchestrator`;
export const DU_API = `${process.env.NEXT_PUBLIC_DU_BASE_URL ?? 'http://localhost:8102'}/api/v0.1/DU`;
export const E2ADAPTER_API = `${process.env.NEXT_PUBLIC_E2ADAPTER_BASE_URL ?? 'http://localhost:8201'}/api/v0.1/E2Adapter`;
export const POLL_MS = 3000;
/** KPM 欄位的顯示定義(名稱、單位、小數) */
export const CELL_METRICS = [
  { key: 'prb_pct_dl', label: 'RRU.PrbTotDl', unit: '%', digits: 1 },
  { key: 'prb_pct_ul', label: 'RRU.PrbTotUl', unit: '%', digits: 1 },
] as const;
export const UE_METRICS = [
  { key: 'rsrp_dbm', label: 'RSRP', unit: 'dBm', digits: 1 }, { key: 'sinr_db', label: 'SINR', unit: 'dB', digits: 1 },
  { key: 'mcs_dl', label: 'MCS', unit: '', digits: 0 }, { key: 'rb_width_dl', label: 'PRB', unit: '', digits: 0 },
  { key: 'throughput_dl_mbps', label: 'Thp DL', unit: 'Mbps', digits: 2 }, { key: 'rlc_sdu_delay_dl_ms', label: 'RlcSduDelayDl', unit: 'ms', digits: 1 },
  { key: 'pdcp_sdu_volume_dl', label: 'PdcpSduVolumeDL', unit: 'B', digits: 0 }, { key: 'mimo_rank', label: 'rank', unit: '', digits: 0 },
] as const;
