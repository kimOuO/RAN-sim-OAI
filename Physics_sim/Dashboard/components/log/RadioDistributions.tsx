'use client';

import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell,
} from 'recharts';
import { useCellStatus } from '@/hooks/feature/log/useCellStatus';
import { useDistributionsSnapshot, type Histogram } from '@/hooks/feature/log/useDistributionsSnapshot';

const C_CARD = '#111827';
const C_BORDER = '#374151';
const C_TEXT = '#cbd5e1';
const C_MUTED = '#6b7280';

export function RadioDistributions() {
  const { ueStates } = useCellStatus();
  const { cqi, mcs, rank } = useDistributionsSnapshot(ueStates);

  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{
        margin: 0, color: C_TEXT, fontSize: 14, fontWeight: 600,
        marginBottom: 12,
      }}>
        📈 Radio Health Distributions （所有 UE 當下分布）
      </h2>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12,
      }}>
        <DistCard
          title="CQI" hist={cqi}
          colorFor={i => i >= 11 ? '#10b981' : i >= 6 ? '#f59e0b' : '#ef4444'}
          subtitle="0..15 (38.214 Table 5.2.2.1-2)"
        />
        <DistCard
          title="MCS DL" hist={mcs}
          colorFor={i => i >= 20 ? '#10b981' : i >= 9 ? '#f59e0b' : '#ef4444'}
          subtitle="0..31 (link adaptation)"
        />
        <DistCard
          title="Rank" hist={rank}
          colorFor={i => i === 0 ? '#a855f7' : i === 1 ? '#3b82f6' : '#06b6d4'}
          subtitle="MIMO layers (current mock: rank=1 only)"
        />
      </div>
    </section>
  );
}


function DistCard(props: {
  title: string; hist: Histogram; subtitle: string;
  colorFor: (binIdx: number) => string;
}) {
  const data = props.hist.bins.map((b, i) => ({ ...b, i }));
  return (
    <div style={{
      background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8,
      padding: 12,
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        marginBottom: 4,
      }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: C_TEXT }}>{props.title}</span>
        <span style={{ fontSize: 11, color: C_MUTED }}>
          n={props.hist.total} · μ={props.hist.mean !== null ? props.hist.mean.toFixed(1) : '—'}
        </span>
      </div>
      <div style={{ fontSize: 10, color: C_MUTED, marginBottom: 8 }}>
        {props.subtitle}
      </div>
      <div style={{ height: 140 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <XAxis dataKey="label" tick={{ fontSize: 9, fill: C_MUTED }}
                   interval={0} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: C_MUTED }}
                   axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background: '#0b1220', border: `1px solid ${C_BORDER}`, fontSize: 11 }}
              labelFormatter={(v: any) => `${props.title}=${v}`}
              formatter={(v: any) => [`${v} UE`, 'count']}
              cursor={{ fill: 'rgba(168,85,247,0.1)' }}
            />
            <Bar dataKey="count">
              {data.map((d, i) => (
                <Cell key={i} fill={props.colorFor(d.i)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
