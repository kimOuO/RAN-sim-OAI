/** UE 的 serving cell 色帶(換手一眼看出),色跟 cell 走 */
export function ServingStrip({ strip, color, height = 8 }: { strip: { x: number; cell: string }[]; color: Record<string, string>; height?: number }) {
  const n = strip.length; if (!n) return null;
  const segs: { from: number; to: number; cell: string }[] = [];
  for (let i = 0; i < n; i++) { const c = strip[i].cell; const last = segs[segs.length - 1]; if (last && last.cell === c) last.to = i + 1; else segs.push({ from: i, to: i + 1, cell: c }); }
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${n} 1`} preserveAspectRatio="none" role="img" aria-label="serving cell strip">
      {segs.map((s, i) => <rect key={i} x={s.from} y="0" width={s.to - s.from} height="1" fill={s.cell ? color[s.cell] ?? '#666' : 'transparent'}><title>{s.cell || '未附著'}</title></rect>)}
    </svg>
  );
}
