import type { SceneRun } from '@/types/registry';

/** 場次三種狀態的中文(2026-09-28)。 */
export const STATUS_LABEL: Record<SceneRun['status'], string> = { idle: '閒置', precomputing: '預算中', running: '執行中' };
const RESULT_LABEL: Record<string, string> = { done: '上次跑完', stopped: '上次停止', failed: '上次失敗' };

export const statusLabel = (r: SceneRun) => STATUS_LABEL[r.status] ?? r.status;
export const lastResultLabel = (r: SceneRun) => (r.status === 'idle' && r.last_result ? RESULT_LABEL[r.last_result] ?? '' : '');
export const precomputed = (r: SceneRun) => !!r.cache_path;
/** 啟動時實際會用的模式與倍速:cached 但沒預算 → live 1×(orchestrator 同一規則)。 */
export const effectiveRun = (r: SceneRun) => (r.mode === 'cached' && !r.cache_path
  ? { mode: 'live' as const, speed_x: 1, note: '未預算 → live 1×' }
  : { mode: r.mode, speed_x: r.speed_x, note: '' });
