import type { ReactNode } from 'react';
import Link from 'next/link';
import '@/styles/globals.css';
export const metadata = { title: 'RAN Run Monitor' };
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-Hant"><body>
      <nav className="topnav"><div className="shell"><Link href="/runs" className="brand">RAN Run Monitor</Link><Link href="/runs">Runs</Link><Link href="/compare">並看</Link><span className="muted right">只讀 · 啟停在管理平台</span></div></nav>
      <main className="shell">{children}</main>
    </body></html>
  );
}
