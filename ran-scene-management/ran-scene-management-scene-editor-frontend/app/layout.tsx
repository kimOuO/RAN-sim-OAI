import type { ReactNode } from 'react';
import Link from 'next/link';
import { MONITOR_BASE_URL } from '@/config';
import '@/styles/globals.css';
export const metadata = { title: 'RAN Scene Editor' };
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // 瀏覽器翻譯擴充(沉浸式翻譯等)會在 React 接手前改 <html>/<body> 屬性 → hydration 警告;只忽略這兩層的屬性差異
    <html lang="zh-Hant" suppressHydrationWarning><body suppressHydrationWarning>
      <nav className="topnav"><div className="shell"><Link href="/scenes" className="brand">RAN Scene Editor</Link><Link href="/scenes">場景</Link><Link href="/network-elements">網路元件</Link><Link href="/imports">匯入</Link><a className="right" href={MONITOR_BASE_URL} target="_blank" rel="noreferrer">監控平台 ↗</a></div></nav>
      <main>{children}</main>
    </body></html>
  );
}
