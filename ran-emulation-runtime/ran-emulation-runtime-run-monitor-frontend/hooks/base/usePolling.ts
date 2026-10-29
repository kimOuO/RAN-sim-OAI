'use client';
import { useEffect, useRef } from 'react';
/** 每 ms 呼叫一次 refetch;enabled=false 時不輪詢(run 停了就不用一直打) */
export function usePolling(refetch: () => void, ms: number, enabled: boolean) {
  const latest = useRef(refetch);
  useEffect(() => { latest.current = refetch; }, [refetch]);
  useEffect(() => { if (!enabled) return; const t = setInterval(() => latest.current(), ms); return () => clearInterval(t); }, [ms, enabled]);
}
