'use client';

// 2026-05-16 P4.1 — 共享 fetch /CU/E2/E2NodeId/read。
// 內容:globalE2node-ID (PLMN, gNB_ID) + RAN functions + F1 components (cells with nr_cellid/tac/s_nssai)。

import { CU_BASE_URL } from '@/config';
import { makePoller } from './_sharedPoller';

export interface PlmnId {
  mcc: string;
  mnc: string;
  mnc_digit_count: number;
}

export interface GnbId {
  value_hex: string;
  value_int: number;
  bit_length: number;
}

export interface RanFunction {
  ran_function_id: number;
  oid: string;
  description?: string;
}

export interface CellPayload {
  cell_id: string;
  nr_cell_id?: string;
  nr_cellid?: number | null;   // 2026-05-16 P2.6: explicit OAI 真值,null 時 e2adapter 走 SHA-1 hash
  pci: number;
  tac: number;
  served_plmn: string;
  s_nssai?: { sst: number; sd?: string };
  is_active: boolean;
}

export interface E2NodeComponent {
  interface_type: string;
  gnb_du_id: number;
  du_name: string;
  cells: CellPayload[];
}

export interface E2NodeIdSnapshot {
  global_e2_node_id: {
    plmn_id: PlmnId;
    gnb_id: GnbId;
  };
  ran_functions: RanFunction[];
  // 對齊後端 serializer key 名(2026-05-17 修:原本誤寫 e2_node_components)
  components: E2NodeComponent[];
  expected_ran_name?: string;
}

async function fetchE2NodeId(): Promise<E2NodeIdSnapshot> {
  const r = await fetch(
    `${CU_BASE_URL}/api/v0.1/CU/E2/E2NodeId/read`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  return j.data;
}

const poller = makePoller<E2NodeIdSnapshot>(fetchE2NodeId, 5000);
export const useE2NodeId = poller.use;
