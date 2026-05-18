'use client';

// 共享 poller — 多 component 訂閱同一 endpoint,只跑一條 fetch 迴圈。
// 替代「每個 component / hook 自己 setInterval」造成的同 endpoint 重複 poll。
import { useEffect, useState } from 'react';

type Listener<T> = (snap: { data: T | null; error: string }) => void;

export interface SharedSnapshot<T> { data: T | null; error: string; }

export function makePoller<T>(
  fetchFn: () => Promise<T>,
  intervalMs: number,
) {
  let data: T | null = null;
  let error = '';
  let listeners: Listener<T>[] = [];
  let timer: ReturnType<typeof setInterval> | null = null;
  let busy = false;

  const tick = async () => {
    if (busy) return;
    busy = true;
    try {
      data = await fetchFn();
      error = '';
    } catch (e: any) {
      error = e?.message || String(e);
    } finally {
      busy = false;
      listeners.forEach(fn => fn({ data, error }));
    }
  };

  const subscribe = (fn: Listener<T>) => {
    listeners.push(fn);
    if (listeners.length === 1) {
      tick();
      timer = setInterval(tick, intervalMs);
    }
    return () => {
      listeners = listeners.filter(l => l !== fn);
      if (listeners.length === 0 && timer) {
        clearInterval(timer); timer = null;
      }
    };
  };

  function use(): SharedSnapshot<T> {
    const [snap, setSnap] = useState<SharedSnapshot<T>>({ data, error });
    useEffect(() => {
      // 訂閱前先 sync 最新值
      setSnap({ data, error });
      return subscribe(setSnap);
    }, []);
    return snap;
  }

  return { use, subscribe };
}
