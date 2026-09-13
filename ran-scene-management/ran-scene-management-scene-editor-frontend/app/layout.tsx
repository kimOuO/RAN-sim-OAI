import type { ReactNode } from 'react';
import Link from 'next/link';
import { MONITOR_BASE_URL } from '@/config';
import '@/styles/globals.css';
export const metadata = { title: 'RAN Scene Editor' };
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-Hant"><body>
      <nav className="topnav"><div className="shell"><Link href="/scenes" className="brand">RAN Scene Editor</Link><Link href="/scenes">場景</Link><Link href="/network-elements">網路元件</Link><Link href="/imports">匯入</Link><a className="right" href={MONITOR_BASE_URL} target="_blank" rel="noreferrer">監控平台 ↗</a></div></nav>
      <main>{children}</main>
    </body></html>
  );
}
