'use client';
import { useState, type ReactNode } from 'react';
export function Section({ title, sub, defaultOpen = true, children }: { title: string; sub?: string; defaultOpen?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="sec">
      <header onClick={() => setOpen(!open)}><h2>{title}</h2>{sub && <span className="muted">{sub}</span>}<span className="tog">{open ? '▾' : '▸'}</span></header>
      {open && <div className="body">{children}</div>}
    </section>
  );
}
