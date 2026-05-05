import { useState, useCallback, useEffect, useRef } from 'react';
import type { AsyncState, AsyncStatus } from '@/types';

export function useAsync<T>(
  asyncFn: () => Promise<T>,
  immediate = true
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<AsyncStatus>('idle');
  const [error, setError] = useState<Error | null>(null);
  const asyncFnRef = useRef(asyncFn);

  useEffect(() => {
    asyncFnRef.current = asyncFn;
  }, [asyncFn]);

  const refetch = useCallback(async () => {
    setStatus('loading');
    setError(null);
    try {
      const result = await asyncFnRef.current();
      setData(result);
      setStatus('success');
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    if (immediate) {
      refetch();
    }
  }, [immediate, refetch]);

  return { data, status, error, refetch };
}
