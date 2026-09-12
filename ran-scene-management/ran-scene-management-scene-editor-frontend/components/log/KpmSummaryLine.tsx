'use client';

import { useEffect, useState } from 'react';
import { fetchDuPm, type DuPmSnapshot } from '@/services/api/scenarioMonitor';

/**
 * 單行即時 KPM 摘要。所有 cell / UE 聚合成 6 個數字,讓運維一眼看完整健康度,
 * 不用展開每個 per-UE / per-cell 細項。資料源 DuPm 已含 last_cell_stats /
 * last_ue_stats,額外開銷只多一條 polling。
 */
export function KpmSummaryLine() {
  const [pm, setPm] = useState<DuPmSnapshot | null>(null);
  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const d = await fetchDuPm();
        if (!stop) setPm(d);
      } catch {
        /* tick 失敗忽略,下次重試 */
      }
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => { stop = true; clearInterval(id); };
  }, []);

  const cells = pm?.last_cell_stats ?? {};
  const ues = pm?.last_ue_stats ?? {};
  const cellList = Object.values(cells);
  const ueList = Object.values(ues);
  const activeCells = cellList.filter(c => c.is_active);
  const ueCount = ueList.length;
  const cellCount = activeCells.length;

  const avgPrbPct = activeCells.length
    ? activeCells.reduce((s, c) => s + (c.prb_pct_this_tick ?? 0), 0) / activeCells.length
    : 0;
  const totalDlMbps = activeCells.reduce(
    (s, c) => s + (c.dl_aggregate_mbps_this_tick ?? 0), 0,
  );
  const avgSinr = ueList.length
    ? ueList.reduce((s, u) => s + (u.sinr_db ?? 0), 0) / ueList.length
    : 0;
  const avgMcs = ueList.length
    ? ueList.reduce((s, u) => s + (u.mcs_dl ?? 0), 0) / ueList.length
    : 0;
  const avgDelay = ueList.length
    ? ueList.reduce((s, u) => s + (u.rlc_delay_ms_avg_this_tick ?? 0), 0) / ueList.length
    : 0;

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(7, 1fr)',
      gap: 8,
      padding: '10px 14px',
      marginBottom: 12,
      background: 'linear-gradient(90deg, #0f1729 0%, #0b1220 100%)',
      border: '1px solid #1e293b',
      borderRadius: 6,
      fontSize: 11,
      color: '#94a3b8',
    }}>
      <Stat label="UE" value={ueCount} unit="" color="#67e8f9" />
      <Stat label="Active cell" value={cellCount} unit="" color="#a7f3d0" />
      <Stat label="Avg PRB" value={avgPrbPct.toFixed(1)} unit="%" color="#fbbf24" />
      <Stat label="Σ DL" value={totalDlMbps.toFixed(2)} unit="Mbps" color="#22c55e" />
      <Stat label="Avg SINR" value={avgSinr.toFixed(1)} unit="dB" color="#0ea5e9" />
      <Stat label="Avg MCS" value={avgMcs.toFixed(1)} unit="" color="#c084fc" />
      <Stat label="Avg Delay" value={avgDelay.toFixed(1)} unit="ms" color="#f87171" />
    </div>
  );
}

function Stat({ label, value, unit, color }: {
  label: string; value: number | string; unit: string; color: string;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: '#64748b', letterSpacing: 0.3 }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 600, color, fontFamily: 'ui-monospace, monospace' }}>
        {value}
        {unit && <span style={{ fontSize: 10, color: '#64748b', marginLeft: 3 }}>{unit}</span>}
      </span>
    </div>
  );
}
