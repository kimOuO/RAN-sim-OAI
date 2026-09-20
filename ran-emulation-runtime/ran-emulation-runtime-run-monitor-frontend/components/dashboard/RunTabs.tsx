'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useMemo } from 'react';
import { POLL_MS } from '@/config';
import { useAsync } from '@/hooks/base/useAsync';
import { useDismissed } from '@/hooks/base/useDismissed';
import { usePolling } from '@/hooks/base/usePolling';
import { listRuns, listScenes } from '@/services/api/runs';

const DISMISS_KEY = 'monitor.dismissedRunTabs';

/** 頂欄:Runs + 每個執行中 / 最近結束的 run 一個分頁(以模擬名稱標示)。
 *  已結束的 run 可以按 × 關掉(只記在這台瀏覽器);重新開跑會自動回來。 */
export function RunTabs() {
  const runs = useAsync(listRuns, []); const scenes = useAsync(listScenes, []); const path = usePathname();
  usePolling(runs.refetch, POLL_MS * 2, true);
  const { ids: dismissed, dismiss, restore } = useDismissed(DISMISS_KEY);

  const candidates = useMemo(
    () => (runs.data ?? []).filter((r) => r.status === 'running' || r.status === 'stopped'),
    [runs.data],
  );

  // 又開跑的 run 要自己回來;已經不在清單上的 id 也不必再記著
  useEffect(() => {
    if (!runs.data) return;
    const keep = candidates.filter((r) => r.status !== 'running').map((r) => r.scene_run_uuid);
    restore(keep);
  }, [runs.data, candidates, restore]);

  const tabs = useMemo(() => {
    const name = new Map((scenes.data ?? []).map((s) => [s.scene_uuid, s.legacy_scenario_id || s.name]));
    return candidates
      // 正在看的那一頁即使關掉也要留著,否則畫面上會沒有對應的分頁
      .filter((r) => !dismissed.includes(r.scene_run_uuid) || path.startsWith(`/runs/${r.scene_run_uuid}`))
      .sort((a, b) => (a.status === 'running' ? -1 : 1) - (b.status === 'running' ? -1 : 1)
        || (b.started_at ?? '').localeCompare(a.started_at ?? ''))
      .slice(0, 6)
      .map((r) => ({ id: r.scene_run_uuid, label: name.get(r.f_scene_uuid) ?? r.scene_run_uuid.slice(-6), live: r.status === 'running' }));
  }, [candidates, scenes.data, dismissed, path]);

  return (
    <div className="runtabs">
      <Link href="/runs" className={path === '/runs' ? 'on' : ''}>Runs</Link>
      {tabs.map((t) => (
        <span key={t.id} className={`runtab${path.startsWith(`/runs/${t.id}`) ? ' on' : ''}`}>
          <Link href={`/runs/${t.id}`} className={path.startsWith(`/runs/${t.id}`) ? 'on' : ''}>
            {t.live && <i className="dot ok" />}{t.label}
          </Link>
          {!t.live && (
            <button type="button" className="tabx" title="關掉這個分頁(只影響這台瀏覽器)"
              aria-label={`關掉 ${t.label}`} onClick={() => dismiss(t.id)}>×</button>
          )}
        </span>
      ))}
      <Link href="/compare" className={path === '/compare' ? 'on' : ''}>對照</Link>
    </div>
  );
}
