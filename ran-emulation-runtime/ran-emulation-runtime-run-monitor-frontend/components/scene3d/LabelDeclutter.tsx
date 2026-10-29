'use client';
import { useEffect } from 'react';
import { useThree } from '@react-three/fiber';

/** 3D 標籤去重疊:定期量每個標籤在螢幕上的實際框,依優先序放置,和已放置的框(或畫面上的浮動面板)重疊就隱藏。
 *  標籤用 data-declutter="<優先序>"(大者先放);浮動面板用 data-declutter-obstacle。
 *  用 visibility 而非 display 隱藏,被藏的標籤仍保有框,下一輪可以重新判斷。 */
export function LabelDeclutter({ intervalMs = 150, gap = 2 }: { intervalMs?: number; gap?: number }) {
  const { gl } = useThree();
  useEffect(() => {
    const root = gl.domElement.closest('.live3d') ?? gl.domElement.parentElement?.parentElement;
    if (!root) return;
    const tick = () => {
      const placed: DOMRect[] = [...root.querySelectorAll<HTMLElement>('[data-declutter-obstacle]')]
        .filter((el) => el.offsetParent !== null).map((el) => el.getBoundingClientRect());
      const labels = [...root.querySelectorAll<HTMLElement>('[data-declutter]')]
        .map((el) => ({ el, prio: Number(el.dataset.declutter) || 0, r: el.getBoundingClientRect() }))
        .sort((a, b) => b.prio - a.prio);
      const hit = (r: DOMRect) => placed.some((p) => r.left < p.right + gap && r.right > p.left - gap && r.top < p.bottom + gap && r.bottom > p.top - gap);
      for (const { el, r } of labels) {
        const show = !r.width || !hit(r);
        el.style.visibility = show ? '' : 'hidden';
        if (show && r.width) placed.push(r);
      }
    };
    const id = window.setInterval(tick, intervalMs);
    return () => window.clearInterval(id);
  }, [gl, intervalMs, gap]);
  return null;
}
