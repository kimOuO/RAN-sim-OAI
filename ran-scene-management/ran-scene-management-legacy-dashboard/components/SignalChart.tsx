'use client';

import dynamic from 'next/dynamic';
import styles from './SignalChart.module.css';

const LineChart = dynamic(() => import('recharts').then(mod => mod.LineChart), { ssr: false });
const Line = dynamic(() => import('recharts').then(mod => mod.Line), { ssr: false });
const XAxis = dynamic(() => import('recharts').then(mod => mod.XAxis), { ssr: false });
const YAxis = dynamic(() => import('recharts').then(mod => mod.YAxis), { ssr: false });
const CartesianGrid = dynamic(() => import('recharts').then(mod => mod.CartesianGrid), { ssr: false });
const Tooltip = dynamic(() => import('recharts').then(mod => mod.Tooltip), { ssr: false });
const Legend = dynamic(() => import('recharts').then(mod => mod.Legend), { ssr: false });
const ResponsiveContainer = dynamic(() => import('recharts').then(mod => mod.ResponsiveContainer), { ssr: false });

interface ChartData {
  tick: number;
  [key: string]: number | string;
}

interface Props {
  data: ChartData[];
  height?: number;
}

export function SignalChart({ data, height = 300 }: Props) {
  if (data.length === 0) {
    return (
      <div className={styles.chartContainer}>
        <div style={{ textAlign: 'center', padding: '32px', color: '#999' }}>
          No data
        </div>
      </div>
    );
  }

  const colors = ['#0070f3', '#ec4899', '#10b981', '#f59e0b', '#6366f1'];

  return (
    <div className={styles.chartContainer}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="tick" />
          <YAxis />
          <Tooltip />
          <Legend />
          {/* 由「最新一個 point」決定要畫哪些線 — 不要用 data[0]，
              否則被刪掉的 UE 因為還在最舊的 100 點裡會永遠出現「鬼魂線」。*/}
          {Object.keys(data[data.length - 1])
            .filter((key) => key !== 'tick')
            .map((key, idx) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[idx % colors.length]}
                dot={false}
                isAnimationActive={false}
              />
            ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
