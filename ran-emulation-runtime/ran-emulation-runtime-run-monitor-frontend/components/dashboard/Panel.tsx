'use client';
import { useState, type ReactNode } from 'react';
/** Grafana 式 panel:標題列 + 內容;可收合;可切「表格檢視」(圖形化的退路) */
export function Panel({ title, sub, span = 6, table, defaultOpen = true, children }: { title: string; sub?: string; span?: 3 | 4 | 6 | 8 | 12; table?: ReactNode; defaultOpen?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen); const [showTable, setShowTable] = useState(false);
  return (
    <section className={`panel span-${span}`}>
      <header><h2 onClick={() => setOpen(!open)}>{title}</h2>{sub && <span className="muted">{sub}</span>}
        <span className="sp" />{table && open && <button className="ghost" onClick={() => setShowTable(!showTable)}>{showTable ? '圖' : '表'}</button>}<button className="ghost" onClick={() => setOpen(!open)}>{open ? '−' : '+'}</button></header>
      {open && <div className="body">{showTable && table ? table : children}</div>}
    </section>
  );
}
