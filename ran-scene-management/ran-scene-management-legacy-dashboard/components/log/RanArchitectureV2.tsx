'use client';

import { useMemo } from 'react';
import { useSystemOverview } from '@/hooks/feature/log/useSystemOverview';
import { useCellStatus } from '@/hooks/feature/log/useCellStatus';
import { useHandoverEventApi } from '@/hooks/feature/log/useHandoverEventApi';

const C_CARD = '#111827';
const C_BORDER = '#374151';
const C_TEXT = '#cbd5e1';
const C_MUTED = '#6b7280';

const C_CU = '#3b82f6';
const C_DU = '#10b981';
const C_RU = '#f59e0b';
const C_RIC = '#a855f7';

/**
 * 三層 RAN 拓樸圖：xApp/RIC ↔ CU ↔ DU ↔ RU。
 * 每個方塊內顯示 RAN KPI（不是 msg/s rate）。連線顯示業務協定名 + 該層當前活動 KPI。
 */
export function RanArchitectureV2() {
  const overview = useSystemOverview();
  const cellStatus = useCellStatus();
  const ho = useHandoverEventApi(60);

  const avgPrbPct = useMemo(() => {
    if (cellStatus.aggregates.length === 0) return null;
    const sum = cellStatus.aggregates.reduce((a, c) => a + c.prbUsedPct, 0);
    return sum / cellStatus.aggregates.length;
  }, [cellStatus.aggregates]);

  const avgSinr = useMemo(() => {
    const samples = cellStatus.aggregates
      .map(c => c.avgSinrDb)
      .filter((v): v is number => v !== null);
    if (samples.length === 0) return null;
    return samples.reduce((a, b) => a + b, 0) / samples.length;
  }, [cellStatus.aggregates]);

  return (
    <div style={{
      background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 10,
      padding: 16, marginBottom: 16,
    }}>
      <h3 style={{
        margin: 0, color: C_TEXT, fontSize: 14, fontWeight: 600,
        marginBottom: 12,
      }}>
        🏗 RAN Architecture · live KPI
      </h3>

      <div style={{
        display: 'grid', gridTemplateColumns: 'auto 1fr auto 1fr auto 1fr auto',
        alignItems: 'center', gap: 0, fontSize: 12,
      }}>
        {/* xApp/RIC node */}
        <NodeBox color={C_RIC} label="xApp / Near-RT RIC" sub="(external)">
          <KvRow k="E2 link" v={overview.e2.connected ? '✓ up' : '✗ down'} />
          <KvRow k="setup" v={overview.e2.setup_ok ? 'OK' : '—'} />
          <KvRow k="ind sent" v={`${overview.e2.sent.toLocaleString()}`} />
        </NodeBox>

        {/* RIC ↔ CU edge */}
        <Edge label="E2AP" sublabel={`${overview.e2.recv} acks recv`} />

        <NodeBox color={C_CU} label="CU :8101" sub="control plane">
          <KvRow k="UE conn" v={`${overview.ue.connected}/${overview.ue.total}`} />
          <KvRow k="HO 60s" v={`${ho.length}`} />
          <KvRow k="A3 / xApp"
                 v={`${ho.filter(h => h.trigger === 'A3_TTT').length} / ${ho.filter(h => h.trigger === 'E2_RIC_CONTROL').length}`} />
        </NodeBox>

        {/* CU ↔ DU edge */}
        <Edge label="F1AP" sublabel={`UE Context, RRC, Meas`} />

        <NodeBox color={C_DU} label="DU :8102" sub="MAC scheduling">
          <KvRow k="cells" v={`${overview.cells.active}/${overview.cells.total}`} />
          <KvRow k="avg PRB" v={avgPrbPct !== null ? `${avgPrbPct.toFixed(1)}%` : '—'} />
          <KvRow k="tick" v={overview.tick ? `sfn ${overview.tick.sfn}` : '—'} />
        </NodeBox>

        {/* DU ↔ RU edge */}
        <Edge label="FAPI" sublabel={`DL/UL TTI per slot`} />

        <NodeBox color={C_RU} label="RU :8103" sub="PHY low">
          <KvRow k="avg SINR"
                 v={avgSinr !== null ? `${avgSinr.toFixed(1)} dB` : '—'} />
          <KvRow k="ant cfg" v="14 dBi" />
          <KvRow k="cache" v="50 cm" />
        </NodeBox>
      </div>
    </div>
  );
}


function NodeBox(props: {
  color: string; label: string; sub: string; children: React.ReactNode;
}) {
  return (
    <div style={{
      background: '#0f172a', border: `2px solid ${props.color}`, borderRadius: 8,
      padding: '10px 12px', minWidth: 180,
    }}>
      <div style={{
        fontWeight: 700, color: props.color, fontSize: 13, marginBottom: 2,
      }}>
        {props.label}
      </div>
      <div style={{ fontSize: 10, color: C_MUTED, marginBottom: 8 }}>
        {props.sub}
      </div>
      <div style={{ fontFamily: 'monospace', fontSize: 11, color: C_TEXT }}>
        {props.children}
      </div>
    </div>
  );
}

function KvRow({ k, v }: { k: string; v: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
      <span style={{ color: C_MUTED }}>{k}</span>
      <span>{v}</span>
    </div>
  );
}

function Edge(props: { label: string; sublabel: string }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '0 8px', minWidth: 100,
    }}>
      <div style={{
        height: 2, background: C_BORDER, width: '100%', position: 'relative',
      }}>
        <div style={{
          position: 'absolute', right: -4, top: -4,
          width: 0, height: 0,
          borderTop: '5px solid transparent',
          borderBottom: '5px solid transparent',
          borderLeft: `6px solid ${C_BORDER}`,
        }} />
      </div>
      <div style={{
        fontSize: 11, fontWeight: 600, color: C_TEXT, marginTop: 4,
      }}>
        {props.label}
      </div>
      <div style={{ fontSize: 9, color: C_MUTED, marginTop: 1 }}>
        {props.sublabel}
      </div>
    </div>
  );
}
