import type { ReactNode } from 'react';
import Link from 'next/link';
import '@/styles/globals.css';
export const metadata = { title: 'RAN Run Monitor' };
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-Hant"><body>
      <nav className="topnav"><Link href="/runs" className="brand">RAN Run Monitor</Link><Link href="/runs">Runs</Link><Link href="/compare">並看</Link><span className="muted right">只讀 · 起停在管理平台</span></nav>
      <main>{children}</main>
    </body></html>
  );
}
