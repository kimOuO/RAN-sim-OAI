'use client';

import { useState, type ReactNode } from 'react';

/**
 * 可摺疊區塊 — 預設收合,點 header 展開。
 * 收合時 children 不 mount,完全節省 polling/render 開銷。
 */
export function CollapsibleSection({
  title,
  subtitle,
  defaultOpen = false,
  badge,
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  badge?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section style={{ marginBottom: 12 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          textAlign: 'left',
          padding: '8px 12px',
          background: open ? '#0f172a' : '#0b1220',
          border: '1px solid #1e293b',
          borderRadius: 4,
          color: '#cbd5e1',
          cursor: 'pointer',
          fontSize: 12,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span style={{ fontSize: 10, color: '#64748b', width: 12 }}>
          {open ? '▼' : '▶'}
        </span>
        <span style={{ fontWeight: 600 }}>{title}</span>
        {badge && (
          <span style={{
            padding: '1px 6px', background: '#1e3a8a', color: '#dbeafe',
            borderRadius: 3, fontSize: 10,
          }}>{badge}</span>
        )}
        {subtitle && (
          <span style={{ marginLeft: 'auto', color: '#64748b', fontSize: 10 }}>
            {subtitle}
          </span>
        )}
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          {children}
        </div>
      )}
    </section>
  );
}
