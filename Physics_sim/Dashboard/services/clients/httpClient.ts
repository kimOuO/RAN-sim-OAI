import axios, { AxiosInstance } from 'axios';
import {
  API_BASE_URL,
  CU_BASE_URL,
  DU_BASE_URL,
  E2_ADAPTER_BASE_URL,
  RU_BASE_URL,
  PHYSICS_BASE_URL,
  UE_BASE_URL,
  DEFAULT_FETCH_TIMEOUT_MS,
} from '@/config';

const headers = { 'Content-Type': 'application/json' };

// ── 平台 4-system 拆分後的 client：每個 backend 一個 ──────
export const cuClient: AxiosInstance = axios.create({
  baseURL: CU_BASE_URL,
  timeout: DEFAULT_FETCH_TIMEOUT_MS,
  headers,
});

export const duClient: AxiosInstance = axios.create({
  baseURL: DU_BASE_URL,
  timeout: DEFAULT_FETCH_TIMEOUT_MS,
  headers,
});

export const ruClient: AxiosInstance = axios.create({
  baseURL: RU_BASE_URL,
  timeout: DEFAULT_FETCH_TIMEOUT_MS,
  headers,
});

export const physicsClient: AxiosInstance = axios.create({
  baseURL: PHYSICS_BASE_URL,
  timeout: DEFAULT_FETCH_TIMEOUT_MS,
  headers,
});

// UE container (RANsim-UE, port 8105) — active UE object 跑 traffic + measurement
export const ueClient: AxiosInstance = axios.create({
  baseURL: UE_BASE_URL,
  timeout: DEFAULT_FETCH_TIMEOUT_MS,
  headers,
});

// E2 adapter (RANsim-E2Adapter, port 8201) — SCTP-out 給 RIC,Dashboard 用來
// 同步 KPM 加速 + 讀 snapshot
export const e2AdapterClient: AxiosInstance = axios.create({
  baseURL: E2_ADAPTER_BASE_URL,
  timeout: DEFAULT_FETCH_TIMEOUT_MS,
  headers,
});

// 舊 default client 預設指 Physics（多數既有 endpoint 還在那）
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: DEFAULT_FETCH_TIMEOUT_MS,
  headers,
});

export default apiClient;
