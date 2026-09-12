'use client';
import { useEffect } from 'react';
/** 每 ms 呼叫一次 refetch;enabled=false 時不輪詢(run 停了就不用一直打) */
export function usePolling(refetch: () => void, ms: number, enabled: boolean) {
  useEffect(() => { if (!enabled) return; const t = setInterval(refetch, ms); return () => clearInterval(t); }, [refetch, ms, enabled]);
}
