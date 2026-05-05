import type { SceneConfig } from '@/types';
import styles from './SceneStats.module.css';

interface Props {
  sceneConfig: SceneConfig | null;
}

export function SceneStats({ sceneConfig }: Props) {
  if (!sceneConfig) {
    return <div>Loading...</div>;
  }

  return (
    <div className={styles.stats}>
      <h2>Scene Configuration</h2>
      <dl className={styles.details}>
        <dt>Buildings:</dt>
        <dd>{sceneConfig.buildings?.length || 0}</dd>

        <dt>gNBs:</dt>
        <dd>{sceneConfig.gnbs?.length || 0}</dd>

        <dt>UEs:</dt>
        <dd>{sceneConfig.ues?.length || 0}</dd>
      </dl>
    </div>
  );
}
