import type { KpmSample } from '@/types/telemetry';

export interface BeamCell { cell: string; beams: { id: number; n: number; sinr: number | null; share: number }[]; total: number }

/** 每 cell 每波束的使用次數與平均 SINR(O-RAN WG1 §4.6.4.1 的每波束統計)。 */
export function beamUsage(samples: KpmSample[]): BeamCell[] {
  const acc = new Map<string, Map<number, { n: number; s: number; sn: number }>>();
  for (const w of samples) {
    for (const u of Object.values(w.per_ue)) {
      if (u.beam_id == null) continue;
      const cell = u.serving_cell || '—';
      if (!acc.has(cell)) acc.set(cell, new Map());
      const m = acc.get(cell)!;
      const e = m.get(u.beam_id) ?? { n: 0, s: 0, sn: 0 };
      e.n += 1;
      if (Number.isFinite(u.sinr_db)) { e.s += u.sinr_db; e.sn += 1; }
      m.set(u.beam_id, e);
    }
  }
  return [...acc.entries()].map(([cell, m]) => {
    const total = [...m.values()].reduce((a, b) => a + b.n, 0);
    const beams = [...m.entries()]
      .map(([id, e]) => ({ id, n: e.n, sinr: e.sn ? e.s / e.sn : null, share: total ? e.n / total : 0 }))
      .sort((a, b) => b.n - a.n);
    return { cell, beams, total };
  }).sort((a, b) => a.cell.localeCompare(b.cell));
}
