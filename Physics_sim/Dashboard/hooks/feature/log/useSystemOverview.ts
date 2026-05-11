'use client';

import { useEffect, useState } from 'react';
import { CU_BASE_URL, DU_BASE_URL, E2_ADAPTER_BASE_URL } from '@/config';

export interface SystemOverview {
  tick: { sfn: number; slot: number; tick_count: number; is_running: boolean } | null;
  ue: { connected: number; total: number };
  cells: { active: number; total: number };
  e2: { connected: boolean; setup_ok: boolean; sent: number; recv: number };
  loading: boolean;
}

const POLL_MS = 2000;

export function useSystemOverview(): SystemOverview {
  const [state, setState] = useState<SystemOverview>({
    tick: null,
    ue: { connected: 0, total: 0 },
    cells: { active: 0, total: 0 },
    e2: { connected: false, setup_ok: false, sent: 0, recv: 0 },
    loading: true,
  });

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      const [tickR, sessR, cellR, adapterR] = await Promise.allSettled([
        fetch(`${DU_BASE_URL}/api/v0.1/DU/Tick/TickController/read`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        }).then(r => r.json()),
        fetch(`${CU_BASE_URL}/api/v0.1/CU/Session/SessionController/list`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        }).then(r => r.json()),
        fetch(`${DU_BASE_URL}/api/v0.1/DU/MAC/MacCellController/read`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        }).then(r => r.json()),
        fetch(`${E2_ADAPTER_BASE_URL}/api/v0.1/E2Adapter/Status/AdapterStatusReader/read`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        }).then(r => r.json()),
      ]);
      if (stop) return;

      const tickData = tickR.status === 'fulfilled' ? tickR.value?.data : null;
      const sessions: any[] = sessR.status === 'fulfilled' ? (sessR.value?.data || []) : [];
      const cellsArr: any[] = cellR.status === 'fulfilled'
        ? (cellR.value?.data?.cells || cellR.value?.data || [])
        : [];
      const adapter = adapterR.status === 'fulfilled' ? adapterR.value?.data : null;

      const connectedUe = sessions.filter(u => u.rrc_state === 'CONNECTED' || u.rrc_state === 'SETUP').length;
      const activeCells = cellsArr.filter((c: any) => c.is_active).length;

      setState({
        tick: tickData ? {
          sfn: tickData.sfn ?? 0, slot: tickData.slot ?? 0,
          tick_count: tickData.tick_count ?? 0,
          is_running: !!tickData.is_running,
        } : null,
        ue: { connected: connectedUe, total: sessions.length },
        cells: { active: activeCells, total: cellsArr.length },
        e2: {
          connected: !!adapter?.sctp_link?.connected,
          setup_ok: !!adapter?.e2_setup?.completed,
          sent: adapter?.sctp_link?.pdu_sent_count ?? 0,
          recv: adapter?.sctp_link?.pdu_recv_count ?? 0,
        },
        loading: false,
      });
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { stop = true; clearInterval(id); };
  }, []);

  return state;
}
