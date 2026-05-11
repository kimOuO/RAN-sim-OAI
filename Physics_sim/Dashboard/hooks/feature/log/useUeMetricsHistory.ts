'use client';

import { useEffect, useState } from 'react';
import { E2_ADAPTER_BASE_URL } from '@/config';

export type MetricName =
  | 'RSRP' | 'SINR'
  | 'DRB.UEThpDl' | 'DRB.UEThpUl'
  | 'DRB.PdcpSduVolumeDL' | 'DRB.PdcpSduVolumeUL'
  | 'DRB.RlcSduDelayDl'
  | 'RRU.PrbTotDl' | 'RRU.PrbTotUl';

export interface MetricPoint {
  ts_ms: number;
  value: number | null;
}

export interface MetricSeries {
  metric: MetricName;
  unit: string;
  points: MetricPoint[];
}

const POLL_MS = 2000;
const HISTORY_LIMIT = 60;

const UNIT_BY_METRIC: Record<string, string> = {
  RSRP: 'dBm', SINR: 'dB',
  'DRB.UEThpDl': 'kbps', 'DRB.UEThpUl': 'kbps',
  'DRB.PdcpSduVolumeDL': 'bytes', 'DRB.PdcpSduVolumeUL': 'bytes',
  'DRB.RlcSduDelayDl': 'ms',
  'RRU.PrbTotDl': '%', 'RRU.PrbTotUl': '%',
};

interface State {
  series: MetricSeries[];
  loading: boolean;
  error: string;
}

/** Pull per-UE per-metric history (60 points) from e2adapter HistoryReader. */
export function useUeMetricsHistory(
  ueId: string | null,
  metrics: MetricName[],
): State {
  const [state, setState] = useState<State>({
    series: [], loading: true, error: '',
  });

  useEffect(() => {
    if (!ueId || metrics.length === 0) {
      setState({ series: [], loading: false, error: '' });
      return;
    }
    let stop = false;
    const tick = async () => {
      const fetches = await Promise.allSettled(
        metrics.map(m =>
          fetch(`${E2_ADAPTER_BASE_URL}/api/v0.1/E2Adapter/KpmSnapshot/HistoryReader/read`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ue_id: ueId, metric: m, limit: HISTORY_LIMIT }),
          }).then(r => r.json()).then(j => ({ metric: m, data: j?.data })).catch(() => ({ metric: m, data: null }))
        )
      );
      if (stop) return;

      const series: MetricSeries[] = [];
      let errorMsg = '';
      for (const f of fetches) {
        if (f.status !== 'fulfilled') continue;
        const { metric, data } = f.value;
        const points = (data?.points || []) as any[];
        series.push({
          metric: metric as MetricName,
          unit: UNIT_BY_METRIC[metric] || data?.unit || '',
          points: points.map(p => ({
            ts_ms: typeof p === 'object' ? (p.ts_ms ?? p[0]) : 0,
            value: typeof p === 'object' ? (p.value ?? p[1]) : null,
          })),
        });
      }
      setState({ series, loading: false, error: errorMsg });
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { stop = true; clearInterval(id); };
  }, [ueId, metrics.join(',')]);

  return state;
}
