'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useMemo } from 'react';
import { POLL_MS } from '@/config';
import { useAsync } from '@/hooks/base/useAsync';
import { usePolling } from '@/hooks/base/usePolling';
import { listRuns, listScenes } from '@/services/api/runs';
/** 頂欄:Runs + 每個執行中 / 最近結束的 run 一個分頁(以模擬名稱標示) */
export function RunTabs() {
  const runs = useAsync(listRuns, []); const scenes = useAsync(listScenes, []); const path = usePathname();
  usePolling(runs.refetch, POLL_MS * 2, true);
  const tabs = useMemo(() => { const name = new Map((scenes.data ?? []).map((s) => [s.scene_uuid, s.legacy_scenario_id || s.name]));
    return (runs.data ?? []).filter((r) => r.status === 'running' || r.status === 'stopped').sort((a, b) => (a.status === 'running' ? -1 : 1) - (b.status === 'running' ? -1 : 1) || (b.started_at ?? '').localeCompare(a.started_at ?? '')).slice(0, 6)
      .map((r) => ({ id: r.scene_run_uuid, label: name.get(r.f_scene_uuid) ?? r.scene_run_uuid.slice(-6), live: r.status === 'running' })); }, [runs.data, scenes.data]);
  return (
    <div className="runtabs">
      <Link href="/runs" className={path === '/runs' ? 'on' : ''}>Runs</Link>
      {tabs.map((t) => <Link key={t.id} href={`/runs/${t.id}`} className={path.startsWith(`/runs/${t.id}`) ? 'on' : ''}>{t.live && <i className="dot ok" />}{t.label}</Link>)}
      <Link href="/compare" className={path === '/compare' ? 'on' : ''}>對照</Link>
    </div>
  );
}
