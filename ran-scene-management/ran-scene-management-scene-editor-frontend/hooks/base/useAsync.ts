'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { AsyncState, AsyncStatus } from '@/types';

/** frontend_rule 的 async 形狀:{ data, status, error, refetch } */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<AsyncStatus>('idle');
  const [error, setError] = useState<Error | null>(null);
  const seq = useRef(0);
  const run = useCallback(async () => {
    const my = ++seq.current;
    setStatus('loading');
    try { const d = await fn(); if (my === seq.current) { setData(d); setError(null); setStatus('success'); } return d; }
    catch (e: unknown) { if (my === seq.current) { setError(e instanceof Error ? e : new Error(String(e))); setStatus('error'); } return null; }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { run(); }, [run]);
  return { data, status, error, refetch: run };
}
