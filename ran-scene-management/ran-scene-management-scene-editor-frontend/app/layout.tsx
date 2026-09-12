import type { ReactNode } from 'react';
import Link from 'next/link';
import '@/styles/globals.css';

export const metadata = { title: 'RAN Scene Editor' };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-Hant"><body>
      <nav className="topnav">
        <Link href="/scenes" className="brand">RAN Scene Editor</Link>
        <Link href="/scenes">場景</Link><Link href="/presets">資源庫</Link><Link href="/imports">匯入</Link>
      </nav>
      <main>{children}</main>
    </body></html>
  );
}
