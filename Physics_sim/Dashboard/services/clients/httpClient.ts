import axios, { AxiosInstance } from 'axios';
import {
  API_BASE_URL,
  CU_BASE_URL,
  DU_BASE_URL,
  RU_BASE_URL,
  PHYSICS_BASE_URL,
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

// 舊 default client 預設指 Physics（多數既有 endpoint 還在那）
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: DEFAULT_FETCH_TIMEOUT_MS,
  headers,
});

export default apiClient;
