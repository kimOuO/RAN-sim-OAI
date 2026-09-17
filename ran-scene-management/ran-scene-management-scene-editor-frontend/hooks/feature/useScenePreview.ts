'use client';
import { useEffect, useRef, useState } from 'react';

/** 路徑預覽播放:t(模擬秒)依倍率前進,約 15 fps 更新;到尾端自動停 */
export function useScenePreview(duration: number) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(10);
  const last = useRef<number | null>(null);
  useEffect(() => {
    if (!playing) { last.current = null; return; }
    const id = setInterval(() => {
      const now = performance.now(); const dt = last.current == null ? 0 : (now - last.current) / 1000; last.current = now;
      setT((v) => { const n = v + dt * rate; if (n >= duration) { setPlaying(false); return duration; } return n; });
    }, 66);
    return () => clearInterval(id);
  }, [playing, rate, duration]);
  return { t, setT: (v: number) => setT(Math.max(0, Math.min(duration, v))), playing, toggle: () => { if (!playing && t >= duration) setT(0); setPlaying((p) => !p); }, rate, setRate, duration };
}
export type ScenePreview = ReturnType<typeof useScenePreview>;
