import axios, { AxiosInstance } from 'axios';
import { API_BASE_URL, DEFAULT_FETCH_TIMEOUT_MS } from '@/config';

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: DEFAULT_FETCH_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default apiClient;
