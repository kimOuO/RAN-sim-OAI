'use client';

// 共享 DU MAC cells snapshot — useSystemOverview + useCellStatus 之前各 poll 一次, 重複。
import { DU_BASE_URL } from '@/config';
import { makePoller } from './_sharedPoller';

export interface DuMacCell {
  cell_id: string;
  pci?: number;
  total_prb?: number;
  freq_ghz?: number;
  bw_mhz?: number;
  is_active: boolean;
  gnb_id?: string;
  // 2026-05-16 P4.2: OAI 真實 nr_cellid (來自 CellStateReadSerializer);null → SHA-1 hash fallback
  nr_cellid?: number | null;
}

async function fetchDuMacCells(): Promise<DuMacCell[]> {
  const r = await fetch(
    `${DU_BASE_URL}/api/v0.1/DU/MAC/MacCellController/read`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  // 同 endpoint 兩種 shape: {cells:[...]} 或直接 [...]
  return (j?.data?.cells || j?.data || []) as DuMacCell[];
}

const poller = makePoller<DuMacCell[]>(fetchDuMacCells, 2000);
export const useDuMacCells = poller.use;
