'use client';

import { useEffect, useRef, useState } from 'react';
import { CU_BASE_URL, DU_BASE_URL } from '@/config';

export interface CellInfo {
  cell_id: string;
  pci?: number;
  total_prb?: number;
  freq_ghz?: number;
  bw_mhz?: number;
  is_active: boolean;
}

export interface UeMacState {
  ue_id: string;
  rrc_state?: string;
  serving_cell_id?: string;
  last_mcs_dl?: number;
  last_cqi?: number;
  last_sinr_db?: number;
  last_rsrp_dbm?: number;
  last_rank?: number;
  last_allocated_prb_dl?: number;     // = rb_width_dl
  last_throughput_dl_mbps?: number;
  last_pdcp_sdu_volume_dl?: number;
  last_rlc_sdu_delay_dl_ms?: number;
}

export interface HarqEntry {
  ue_id: string;
  direction: 'DL' | 'UL';
  harq_pid: number;
  state?: string;
  retx_count: number;
}

export interface CellAggregate {
  cell: CellInfo;
  ueCount: number;
  prbUsedSum: number;
  prbUsedPct: number;
  avgSinrDb: number | null;
  retxRatePct: number;
  sinrHistory: number[];
}

interface State {
  aggregates: CellAggregate[];
  ueStates: UeMacState[];     // only CONNECTED UE，IDLE / stale 的會被過濾掉
  cells: CellInfo[];
  harq: HarqEntry[];
  loading: boolean;
}

const POLL_MS = 2000;
const SINR_HISTORY_LEN = 30;

// 38.214 Table 5.2.2.1-2 簡化版 — SINR(dB) → CQI(0..15)
const _CQI_TH = [-Infinity, -6, -4, -2, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22];

export function sinrToCqi(sinrDb: number | null | undefined): number | undefined {
  if (sinrDb === null || sinrDb === undefined || !Number.isFinite(sinrDb)) return undefined;
  let cqi = 0;
  for (let i = 0; i < _CQI_TH.length; i++) {
    if (sinrDb >= _CQI_TH[i]) cqi = i;
    else break;
  }
  return Math.min(15, cqi);
}

export function useCellStatus(): State {
  const [state, setState] = useState<State>({
    aggregates: [], ueStates: [], cells: [], harq: [], loading: true,
  });
  const sinrHistoryRef = useRef<Map<string, number[]>>(new Map());

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      const [cellR, kpmR, harqR] = await Promise.allSettled([
        // Cell topology — DB 落盤 OK
        fetch(`${DU_BASE_URL}/api/v0.1/DU/MAC/MacCellController/read`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        }).then(r => r.json()),
        // RAN runtime UE state — 即時值
        fetch(`${CU_BASE_URL}/api/v0.1/CU/E2/E2KpmReporter/read`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        }).then(r => r.json()),
        // HARQ — 即時值（仍從 MAC，假設 HARQ controller 比 MacUeState 即時）
        fetch(`${DU_BASE_URL}/api/v0.1/DU/MAC/MacHarqController/read`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        }).then(r => r.json()),
      ]);
      if (stop) return;

      // Cells
      const cellsRaw = cellR.status === 'fulfilled'
        ? (cellR.value?.data?.cells || cellR.value?.data || [])
        : [];
      const cells: CellInfo[] = (Array.isArray(cellsRaw) ? cellsRaw : []).map((c: any) => ({
        cell_id: c.cell_id || c.name || '',
        pci: c.pci,
        total_prb: c.total_prb,
        freq_ghz: c.freq_ghz ?? c.frequency_ghz,
        bw_mhz: c.bw_mhz ?? c.bandwidth_mhz,
        is_active: c.is_active !== false,
      }));

      // UE states from KPM — only CONNECTED + has serving_cell
      const kpmUes = kpmR.status === 'fulfilled'
        ? (kpmR.value?.data?.ue_status || [])
        : [];
      const ueStates: UeMacState[] = (Array.isArray(kpmUes) ? kpmUes : [])
        .filter((u: any) => u?.rrc_state === 'CONNECTED' && u?.serving_cell)
        .map((u: any) => ({
          ue_id: u.ue_id,
          rrc_state: u.rrc_state,
          serving_cell_id: u.serving_cell,
          last_sinr_db: u.sinr_db ?? undefined,
          last_rsrp_dbm: u.rsrp_dbm ?? undefined,
          last_mcs_dl: u.mcs_dl ?? undefined,
          last_cqi: sinrToCqi(u.sinr_db),
          last_rank: u.mimo_rank ?? undefined,
          last_allocated_prb_dl: u.rb_width_dl ?? 0,
          last_throughput_dl_mbps: u.throughput_dl_mbps ?? 0,
          last_pdcp_sdu_volume_dl: u.pdcp_sdu_volume_dl ?? 0,
          last_rlc_sdu_delay_dl_ms: u.rlc_sdu_delay_dl_ms ?? 0,
        }));

      // HARQ
      const harqRaw = harqR.status === 'fulfilled'
        ? (harqR.value?.data?.entries || harqR.value?.data || [])
        : [];
      const harq: HarqEntry[] = (Array.isArray(harqRaw) ? harqRaw : []).map((h: any) => ({
        ue_id: h.ue_id,
        direction: (h.direction || 'DL') as 'DL' | 'UL',
        harq_pid: h.harq_pid ?? 0,
        state: h.state,
        retx_count: h.retx_count ?? 0,
      }));

      // ── per-cell aggregate ──
      const aggregates: CellAggregate[] = cells.map(cell => {
        const ues = ueStates.filter(u => u.serving_cell_id === cell.cell_id);
        const prbUsedSum = ues.reduce((acc, u) => acc + (u.last_allocated_prb_dl || 0), 0);
        const prbCap = cell.total_prb || 273;
        const prbUsedPct = Math.min(100, (prbUsedSum / prbCap) * 100);
        const sinrSamples = ues.map(u => u.last_sinr_db).filter((v): v is number => v !== undefined && Number.isFinite(v));
        const avgSinrDb = sinrSamples.length > 0
          ? sinrSamples.reduce((a, b) => a + b, 0) / sinrSamples.length
          : null;
        const cellHarqs = harq.filter(h => ues.some(u => u.ue_id === h.ue_id));
        const totalRetx = cellHarqs.reduce((a, h) => a + h.retx_count, 0);
        const totalHarq = cellHarqs.length || 1;
        const retxRatePct = (totalRetx / (totalHarq * 4)) * 100;

        const histKey = cell.cell_id;
        const prev = sinrHistoryRef.current.get(histKey) || [];
        const next = avgSinrDb !== null
          ? [...prev, avgSinrDb].slice(-SINR_HISTORY_LEN)
          : prev;
        sinrHistoryRef.current.set(histKey, next);

        return {
          cell, ueCount: ues.length,
          prbUsedSum, prbUsedPct,
          avgSinrDb, retxRatePct,
          sinrHistory: next,
        };
      });

      setState({ aggregates, ueStates, cells, harq, loading: false });
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { stop = true; clearInterval(id); };
  }, []);

  return state;
}
