'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { AsyncState, AsyncStatus } from '@/types';

/** 增量累積:第一次拉最近一批,之後只拉 id > 上次最後一筆,接在尾端並保留最多 cap 筆。
 *  (2026-09-17:以前每 3 秒整包重拉 15 MB,瀏覽器與後端都被拖慢) */
export function useIncremental<T extends { id: number }>(fetchAfter: (afterId: number) => Promise<T[]>, key: string, cap: number): AsyncState<T[]> {
  const [data, setData] = useState<T[] | null>(null);
  const [status, setStatus] = useState<AsyncStatus>('idle');
  const [error, setError] = useState<Error | null>(null);
  const last = useRef(0); const busy = useRef(false); const gen = useRef(0);
  useEffect(() => { gen.current++; last.current = 0; setData(null); }, [key]);
  const run = useCallback(() => {
    if (busy.current) return;   // 上一輪還沒回來就跳過,不疊請求
    busy.current = true; const my = gen.current;
    if (!last.current) setStatus('loading');
    fetchAfter(last.current).then((rows) => {
      if (my !== gen.current) return;
      if (rows.length) last.current = Math.max(last.current, ...rows.map((r) => r.id));
      setData((prev) => { if (!rows.length && prev) return prev; const all = (prev ?? []).concat(rows); return all.length > cap ? all.slice(-cap) : all; });
      setError(null); setStatus('success');
    }).catch((e: unknown) => { if (my === gen.current) { setError(e instanceof Error ? e : new Error(String(e))); setStatus('error'); } })
      .finally(() => { busy.current = false; });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => { run(); }, [run]);
  return { data, status, error, refetch: run };
}
