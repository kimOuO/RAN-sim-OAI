'use client';

import { useMemo } from 'react';
import type { UeMacState } from './useCellStatus';

export interface Histogram {
  bins: { label: string; count: number }[];
  total: number;
  mean: number | null;
}

/** Build CQI/MCS/rank distributions from a snapshot of MAC UE states. */
export function useDistributionsSnapshot(ueStates: UeMacState[]): {
  cqi: Histogram; mcs: Histogram; rank: Histogram;
} {
  return useMemo(() => {
    const bin = (
      values: (number | undefined)[],
      labels: string[],
      bucketize: (v: number) => number,
    ): Histogram => {
      const bins = labels.map(label => ({ label, count: 0 }));
      let sum = 0;
      let n = 0;
      for (const v of values) {
        if (v === undefined || !Number.isFinite(v)) continue;
        const idx = bucketize(v);
        if (idx < 0 || idx >= bins.length) continue;
        bins[idx].count += 1;
        sum += v;
        n += 1;
      }
      return { bins, total: n, mean: n > 0 ? sum / n : null };
    };

    const cqiLabels = Array.from({ length: 16 }, (_, i) => `${i}`);
    const cqi = bin(
      ueStates.map(u => u.last_cqi),
      cqiLabels,
      v => Math.max(0, Math.min(15, Math.round(v))),
    );

    const mcsLabels = Array.from({ length: 32 }, (_, i) => `${i}`);
    const mcs = bin(
      ueStates.map(u => u.last_mcs_dl),
      mcsLabels,
      v => Math.max(0, Math.min(31, Math.round(v))),
    );

    const rankLabels = ['1', '2', '3', '4'];
    const rank = bin(
      ueStates.map(u => u.last_rank),
      rankLabels,
      v => Math.max(0, Math.min(3, Math.round(v) - 1)),
    );

    return { cqi, mcs, rank };
  }, [ueStates]);
}
