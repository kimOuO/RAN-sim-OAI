'use client';
import { useEffect, useRef, useState } from 'react';
/** 量容器寬度給 SVG 圖表用(圖表寬度跟容器走,文字不被拉伸) */
export function useElementWidth<T extends HTMLElement>(fallback = 600) {
  const ref = useRef<T | null>(null); const [w, setW] = useState(fallback);
  useEffect(() => { const el = ref.current; if (!el) return; const ro = new ResizeObserver(([e]) => setW(Math.max(120, e.contentRect.width))); ro.observe(el); setW(el.clientWidth || fallback); return () => ro.disconnect(); }, [fallback]);
  return { ref, width: w };
}
