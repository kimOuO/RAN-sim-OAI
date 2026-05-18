import type { CellStateSnapshot } from '@/types';
import styles from './CellStatePanel.module.css';

interface Props {
  cells?: CellStateSnapshot[];
  title?: string;
}

function fmtQuota(q: CellStateSnapshot['prb_quota']): string {
  if (!q) return '—';
  const min = q.min_prb ?? '-';
  const max = q.max_prb ?? '-';
  const ded = q.dedicated_prb ?? '-';
  return `${min}/${max}/${ded}%`;
}

export function CellStatePanel({ cells, title = 'Cell State (at frame)' }: Props) {
  const rows = cells ?? [];
  return (
    <div className={styles.box}>
      <h3>{title} <span className={styles.count}>({rows.length})</span></h3>
      {rows.length === 0 ? (
        <div className={styles.empty}>沒有 cell 資訊</div>
      ) : (
        <div className={styles.grid}>
          {rows.map((c) => (
            <div
              key={c.cell_id}
              className={`${styles.card} ${c.is_active ? styles.active : styles.inactive}`}
            >
              <div className={styles.row1}>
                <span className={styles.cellId}>{c.cell_id}</span>
                <span className={c.is_active ? styles.badgeOn : styles.badgeOff}>
                  {c.is_active ? 'ACTIVE' : 'DISABLED'}
                </span>
              </div>
              <div className={styles.row2}>
                <span className={styles.meta}>
                  {c.gnb_id ? `gnb=${c.gnb_id}` : ''}
                  {c.pci !== undefined && c.pci !== null ? `  pci=${c.pci}` : ''}
                </span>
              </div>
              <div className={styles.row3}>
                <span className={styles.metaLabel}>PRB(min/max/ded):</span>{' '}
                <span className={styles.metaValue}>{fmtQuota(c.prb_quota)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
