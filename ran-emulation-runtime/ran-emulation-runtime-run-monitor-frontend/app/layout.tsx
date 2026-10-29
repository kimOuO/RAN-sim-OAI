import type { ReactNode } from 'react';
import Link from 'next/link';
import { RunTabs } from '@/components/dashboard/RunTabs';
import '@/styles/globals.css';
export const metadata = { title: 'RAN Run Monitor' };
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // 瀏覽器翻譯擴充(沉浸式翻譯等)會在 React 接手前改 <html>/<body> 屬性 → hydration 警告;只忽略這兩層的屬性差異
    <html lang="zh-Hant" suppressHydrationWarning><body suppressHydrationWarning>
      <nav className="topnav"><div className="shell"><Link href="/runs" className="brand">RAN Run Monitor</Link><Link href="/playback" className="navlink">回放</Link><Link href="/compare" className="navlink">對照</Link><RunTabs /><span className="muted right">只讀 · 啟停在管理平台</span></div></nav>
      <main className="shell">{children}</main>
    </body></html>
  );
}
