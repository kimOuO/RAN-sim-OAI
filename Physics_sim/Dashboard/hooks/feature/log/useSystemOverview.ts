'use client';

// AG16: 從 4 個獨立 poll 改成「2 個 shared poller + 2 個 local poll」.
// E2Adapter Status 跟 DU MAC Cells 改用 shared (跟 E2AdapterCard, useCellStatus 共用同條 fetch).
import { useEffect, useState } from 'react';
import { CU_BASE_URL, DU_BASE_URL } from '@/config';
import { useE2AdapterStatus } from './useE2AdapterStatus';
import { useDuMacCells } from './useDuMacCells';

export interface SystemOverview {
  tick: { sfn: number; slot: number; tick_count: number; is_running: boolean } | null;
  ue: { connected: number; total: number };
  cells: { active: number; total: number };
  e2: { connected: boolean; setup_ok: boolean; sent: number; recv: number };
  loading: boolean;
}

const POLL_MS = 2000;

export function useSystemOverview(): SystemOverview {
  const adapter = useE2AdapterStatus();
  const cellsSnap = useDuMacCells();

  const [local, setLocal] = useState<{
    tick: SystemOverview['tick'];
    ue: SystemOverview['ue'];
  }>({
    tick: null, ue: { connected: 0, total: 0 },
  });

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      const [tickR, sessR] = await Promise.allSettled([
        fetch(`${DU_BASE_URL}/api/v0.1/DU/Tick/TickController/read`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        }).then(r => r.json()),
        fetch(`${CU_BASE_URL}/api/v0.1/CU/Session/SessionController/list`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        }).then(r => r.json()),
      ]);
      if (stop) return;

      const tickData = tickR.status === 'fulfilled' ? tickR.value?.data : null;
      const sessions: any[] = sessR.status === 'fulfilled' ? (sessR.value?.data || []) : [];

      // AG13: total 只算 active (CONNECTED + SETUP), IDLE 不算.
      const activeUes = sessions.filter(u =>
        u.rrc_state === 'CONNECTED' || u.rrc_state === 'SETUP',
      );

      setLocal({
        tick: tickData ? {
          sfn: tickData.sfn ?? 0, slot: tickData.slot ?? 0,
          tick_count: tickData.tick_count ?? 0,
          is_running: !!tickData.is_running,
        } : null,
        ue: { connected: activeUes.length, total: activeUes.length },
      });
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { stop = true; clearInterval(id); };
  }, []);

  const cellsArr = cellsSnap.data || [];
  const activeCells = cellsArr.filter(c => c.is_active).length;
  const adp = adapter.data;

  return {
    tick: local.tick,
    ue: local.ue,
    cells: { active: activeCells, total: cellsArr.length },
    e2: {
      connected: !!adp?.sctp_link?.connected,
      setup_ok: !!adp?.e2_setup?.completed,
      sent: adp?.sctp_link?.pdu_sent_count ?? 0,
      recv: adp?.sctp_link?.pdu_recv_count ?? 0,
    },
    loading: !adp && !local.tick,
  };
}
