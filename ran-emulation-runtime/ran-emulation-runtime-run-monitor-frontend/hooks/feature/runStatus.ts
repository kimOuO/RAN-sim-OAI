import type { SceneRun } from '@/types/telemetry';

/** 場次三種狀態(2026-09-28):idle / precomputing / running;上一次怎麼結束另存 last_result。 */
export const STATUS_LABEL: Record<string, string> = { idle: '閒置', precomputing: '預算中', running: '執行中' };
const RESULT_LABEL: Record<string, string> = { done: '上次跑完', stopped: '上次停止', failed: '上次失敗' };
export const statusLabel = (r: Pick<SceneRun, 'status'>) => STATUS_LABEL[r.status] ?? r.status;
export const lastResultLabel = (r: Pick<SceneRun, 'status' | 'last_result'>) =>
  (r.status === 'idle' && r.last_result ? RESULT_LABEL[r.last_result] ?? '' : '');
/** 跑過(有資料可看)或正在跑的場次 */
export const hasRunData = (r: Pick<SceneRun, 'status' | 'last_result'>) => r.status === 'running' || !!r.last_result;
