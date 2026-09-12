// ANR 劇本執行中的「事件時間線」——把散在三個地方的事件合成一條。
//
// 跑 ANR 題目時真正要看的是「誰在什麼時候做了什麼」,而不是滿屏 KPM:
//   CU  relationChangeEvents  → 鄰區關係被誰改了(xapp / gnb-xn / ANR)
//   adapter ControlAudit      → xApp 下了什麼命令、instId、結果碼、rtt
//   CU  HandoverEvent         → 換手成功/失敗與原因
// 三者時間軸對齊後,一眼看得出因果:偵測 → 下令 → 生效 → 指標回復。
import axios from 'axios';
import { CU_BASE_URL, E2_ADAPTER_BASE_URL } from '@/config';

export type TimelineKind = 'control' | 'relation' | 'handover';

export interface TimelineRow {
  ts: number;                 // epoch ms
  kind: TimelineKind;
  label: string;              // 主描述
  detail: string;             // 次要資訊
  ok: boolean | null;         // true=成功 / false=失敗或被拒 / null=中性
}

const cu = axios.create({ baseURL: CU_BASE_URL, headers: { 'Content-Type': 'application/json' } });
const ad = axios.create({ baseURL: E2_ADAPTER_BASE_URL, headers: { 'Content-Type': 'application/json' } });

export const fetchAnrTimeline = async (limit = 40): Promise<TimelineRow[]> => {
  const rows: TimelineRow[] = [];

  // 1) 下發命令(含 instId / 結果碼)—— 只有 adapter 這層看得到
  try {
    const r = await ad.post('/api/v0.1/E2Adapter/ControlAudit/ControlAuditReader/read',
      { limit }, { timeout: 4000 });
    for (const c of r.data?.data?.commands ?? []) {
      const rejected = String(c.result || '').includes('REJECT') || c.result === 'NOT_FOUND';
      rows.push({
        ts: c.ts_ms,
        kind: 'control',
        label: `${c.ranFuncName} ${c.command}`,
        detail: [
          c.instId != null ? `inst=${c.instId}` : '',
          Object.entries(c.params || {}).filter(([, v]) => v !== '' && v != null)
            .map(([k, v]) => `${k}=${v}`).join(' '),
          c.result || (c.acked ? 'ACK' : '等 ACK'),
          c.rttMs != null ? `${c.rttMs}ms` : '',
        ].filter(Boolean).join(' · '),
        ok: c.failure ? false : rejected ? false : c.acked ? true : null,
      });
    }
  } catch { /* adapter 拉不到就少一種事件,不影響其他兩種 */ }

  // 2) 鄰區關係變更(by=xapp / gnb-xn / ANR —— 誰動的手很關鍵)
  try {
    const r = await cu.post('/api/v0.1/CU/E2/NodeInfo/read', {}, { timeout: 4000 });
    for (const e of r.data?.data?.relationChangeEvents ?? []) {
      rows.push({
        ts: Date.parse(e.at),
        kind: 'relation',
        label: `${e.action} → ${e.targetCellGlobalId}`,
        detail: [`by=${e.by}`, e.reason || e.detail || ''].filter(Boolean).join(' · '),
        ok: String(e.action).endsWith('_REJECTED') ? false : true,
      });
    }
  } catch { /* ignore */ }

  return rows
    .filter((r) => Number.isFinite(r.ts))
    .sort((a, b) => b.ts - a.ts)      // 最新在最上
    .slice(0, limit);
};
