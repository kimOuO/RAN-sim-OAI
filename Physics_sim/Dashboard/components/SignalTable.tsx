import { Fragment, useState } from 'react';
import type { HandoverEventRecord, UESignalData } from '@/types';
import styles from './SignalTable.module.css';

interface Props {
  data: UESignalData[];
  handovers?: HandoverEventRecord[];
}

function hasNeighbors(ue: UESignalData): boolean {
  return !!ue.rsrp_map && Object.keys(ue.rsrp_map).length > 0;
}

function NeighborList({ ue }: { ue: UESignalData }) {
  const map = ue.rsrp_map ?? {};
  const serving = ue.serving_gnb ?? ue.serving_cell ?? '';
  const servingRsrp = ue.rsrp_dbm;

  const rows = Object.entries(map)
    .map(([name, rsrp]) => ({ name, rsrp: Number(rsrp) }))
    .sort((a, b) => b.rsrp - a.rsrp);

  if (rows.length === 0) {
    return <div className={styles.neighborEmpty}>No neighbor measurements</div>;
  }

  return (
    <table className={styles.neighborTable}>
      <thead>
        <tr>
          <th>Cell / gNB</th>
          <th>RSRP (dBm)</th>
          <th>Δ vs serving</th>
          <th>Role</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const isServing = r.name === serving;
          const diff =
            typeof servingRsrp === 'number' ? r.rsrp - servingRsrp : null;
          return (
            <tr key={r.name} className={isServing ? styles.servingRow : undefined}>
              <td>{r.name}</td>
              <td>{r.rsrp.toFixed(1)}</td>
              <td>
                {diff === null
                  ? '-'
                  : diff === 0
                  ? '±0.0'
                  : `${diff > 0 ? '+' : ''}${diff.toFixed(1)}`}
              </td>
              <td>{isServing ? 'serving' : 'neighbor'}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function SignalTable({ data, handovers }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const hoByUe = new Map<string, HandoverEventRecord[]>();
  for (const h of handovers ?? []) {
    const k = h.ue_name;
    if (!hoByUe.has(k)) hoByUe.set(k, []);
    hoByUe.get(k)!.push(h);
  }

  const toggle = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className={styles.tableContainer}>
      <h3>Signal Metrics</h3>
      <table className={styles.table}>
        <thead>
          <tr>
            <th></th>
            <th>UE</th>
            <th>Position (X, Y, Z)</th>
            <th>RSRP (dBm)</th>
            <th>SINR (dB)</th>
            <th>Serving Cell</th>
            <th>Rank</th>
            <th>Stream SINR</th>
            <th>DL (Mbps)</th>
            <th>UL (Mbps)</th>
            <th>MCS</th>
            <th>PRB</th>
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={12} style={{ textAlign: 'center', color: '#999' }}>
                No data
              </td>
            </tr>
          ) : (
            data.map((ue) => {
              const key = ue.ue_name ?? ue.name ?? '';
              const isOpen = expanded.has(key);
              const canExpand = hasNeighbors(ue);
              return (
                <Fragment key={key}>
                  <tr>
                    <td>
                      {canExpand ? (
                        <button
                          type="button"
                          className={styles.expandBtn}
                          onClick={() => toggle(key)}
                          aria-label={isOpen ? 'Collapse' : 'Expand'}
                        >
                          {isOpen ? '▼' : '▶'}
                        </button>
                      ) : (
                        <span className={styles.expandPlaceholder}>·</span>
                      )}
                    </td>
                    <td>
                      {ue.ue_name ?? ue.name}
                      {(hoByUe.get(key) ?? []).map((h) => (
                        <span
                          key={h.ho_uuid}
                          className={styles.hoBadge}
                          title={`HO ${h.source_cell} → ${h.target_cell}  (${h.trigger}, ${h.status})`}
                        >
                          ⚡HO
                        </span>
                      ))}
                    </td>
                    <td>
                      {ue.position
                        ? `(${ue.position[0]?.toFixed(1)}, ${ue.position[1]?.toFixed(1)}, ${ue.position[2]?.toFixed(1)})`
                        : '-'}
                    </td>
                    <td>{ue.rsrp_dbm?.toFixed(2) ?? '-'}</td>
                    <td>{ue.sinr_db?.toFixed(2) ?? '-'}</td>
                    <td>{ue.serving_cell ?? '-'}</td>
                    <td>{ue.mimo_rank ?? '-'}</td>
                    <td>
                      {ue.mimo_streams_sinr_db && ue.mimo_streams_sinr_db.length > 0
                        ? ue.mimo_streams_sinr_db.map((s) => s.toFixed(1)).join(' / ')
                        : '-'}
                    </td>
                    <td>{ue.throughput_dl_mbps?.toFixed?.(0) ?? '-'}</td>
                    <td>{ue.throughput_ul_mbps?.toFixed?.(0) ?? '-'}</td>
                    <td>{ue.mcs_dl ?? '-'}</td>
                    <td>{ue.prb_used_dl ?? '-'}</td>
                  </tr>
                  {isOpen && canExpand && (
                    <tr className={styles.detailRow}>
                      <td></td>
                      <td colSpan={11}>
                        <div className={styles.detailWrap}>
                          <div className={styles.detailTitle}>
                            Neighbor measurements ({Object.keys(ue.rsrp_map ?? {}).length})
                          </div>
                          <NeighborList ue={ue} />
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
