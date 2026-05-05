import type { UESignalData } from '@/types';
import styles from './SignalTable.module.css';

interface Props {
  data: UESignalData[];
}

export function SignalTable({ data }: Props) {
  return (
    <div className={styles.tableContainer}>
      <h3>Signal Metrics</h3>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>UE</th>
            <th>Position (X, Y, Z)</th>
            <th>RSRP (dBm)</th>
            <th>SINR (dB)</th>
            <th>Serving Cell</th>
            <th>Rank</th>
            <th>Stream SINR</th>
            <th>DL (Mbps)</th>
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={8} style={{ textAlign: 'center', color: '#999' }}>
                No data
              </td>
            </tr>
          ) : (
            data.map((ue) => (
              <tr key={ue.ue_name ?? ue.name}>
                <td>{ue.ue_name ?? ue.name}</td>
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
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
