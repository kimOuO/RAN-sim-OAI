/**
 * A3 handover runtime control — talks to sim CU /Mobility/A3Controller.
 * AK11: runtime config (sim CU 不需 restart).
 */
import { CU_BASE_URL } from '@/config';

export interface A3Config {
  enabled: boolean;
  offset_db: number;
  hys_db: number;
  ttt_ms: number;
}

export const readA3 = async (): Promise<A3Config> => {
  const r = await fetch(`${CU_BASE_URL}/api/v0.1/CU/Mobility/A3Controller/read`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!r.ok) throw new Error(`A3 read failed: HTTP ${r.status}`);
  const j = await r.json();
  return j.data as A3Config;
};

export const setA3 = async (cfg: Partial<A3Config>): Promise<A3Config> => {
  const r = await fetch(`${CU_BASE_URL}/api/v0.1/CU/Mobility/A3Controller/set`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg),
  });
  if (!r.ok) throw new Error(`A3 set failed: HTTP ${r.status}`);
  const j = await r.json();
  return j.data as A3Config;
};
