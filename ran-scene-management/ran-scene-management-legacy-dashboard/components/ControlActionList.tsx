import type { ControlActionRecord } from '@/types';
import styles from './ControlActionList.module.css';

interface Props {
  actions?: ControlActionRecord[];
  title?: string;
}

function fmtTs(iso: string | null): string {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString(undefined, { hour12: false });
  } catch {
    return iso;
  }
}

function summarize(a: ControlActionRecord): string {
  const p = a.payload_json ?? {};
  if (a.action_label === 'HANDOVER') {
    return `${p.source_cell ?? '?'} → ${p.target_cell ?? '?'}`;
  }
  if (a.action_label === 'PRB_QUOTA') {
    return `min=${p.min_prb ?? '?'}% max=${p.max_prb ?? '?'}% ded=${p.dedicated_prb ?? '?'}%`;
  }
  if (a.action_label?.startsWith('CELL_')) {
    return String(p.action ?? '');
  }
  if (a.action_label === 'QOS_FLOW_MAPPING') {
    return `drb=${p.drb_id ?? '?'}`;
  }
  return '';
}

export function ControlActionList({ actions, title = 'RIC Control Actions' }: Props) {
  const rows = actions ?? [];
  return (
    <div className={styles.box}>
      <h3>{title} <span className={styles.count}>({rows.length})</span></h3>
      {rows.length === 0 ? (
        <div className={styles.empty}>沒有 control action 落在此 frame window</div>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Time</th>
              <th>Action</th>
              <th>Style/Act</th>
              <th>UE / Cell</th>
              <th>Detail</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => {
              const isErr = !!a.error || /REJECT|FAIL/i.test(a.outcome);
              return (
                <tr key={a.id} className={isErr ? styles.errRow : undefined}>
                  <td>{fmtTs(a.action_ts)}</td>
                  <td className={styles.label}>{a.action_label}</td>
                  <td>
                    ({a.control_style},{a.control_action_id})
                  </td>
                  <td>
                    {a.ue_name ? <span className={styles.tag}>ue:{a.ue_name}</span> : null}
                    {a.cell_id ? <span className={styles.tag}>cell:{a.cell_id}</span> : null}
                  </td>
                  <td className={styles.summary}>{summarize(a)}</td>
                  <td>
                    <span className={isErr ? styles.outcomeErr : styles.outcomeOk}>
                      {a.outcome}
                    </span>
                    {a.error ? (
                      <div className={styles.errText} title={a.error}>{a.error}</div>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
