'use client';
import { useCallback, useEffect, useState } from 'react';

/** 本機記住「使用者關掉了哪些分頁」。只影響這台瀏覽器,不動後端狀態。
 *  localStorage 在無痕視窗 / 停用 cookie 時會丟例外,所以每次存取都包起來;
 *  讀不到就當成沒有關過任何一個,不影響畫面。 */
export function useDismissed(key: string) {
  const [ids, setIds] = useState<string[]>([]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(key);
      if (raw) setIds(JSON.parse(raw) as string[]);
    } catch { /* 讀不到就維持空集合 */ }
  }, [key]);

  const write = useCallback((next: string[]) => {
    setIds(next);
    try { window.localStorage.setItem(key, JSON.stringify(next)); } catch { /* 存不了就只在本次工作階段生效 */ }
  }, [key]);

  const dismiss = useCallback((id: string) => {
    setIds((prev) => { const next = prev.includes(id) ? prev : [...prev, id]; 
      try { window.localStorage.setItem(key, JSON.stringify(next)); } catch { /* 同上 */ }
      return next; });
  }, [key]);

  const restore = useCallback((keep: string[]) => {
    // 只留下仍然存在的 id,避免清單無限長大
    setIds((prev) => { const next = prev.filter((i) => keep.includes(i));
      if (next.length !== prev.length) { try { window.localStorage.setItem(key, JSON.stringify(next)); } catch { /* 同上 */ } }
      return next; });
  }, [key]);

  return { ids, dismiss, restore, write };
}
