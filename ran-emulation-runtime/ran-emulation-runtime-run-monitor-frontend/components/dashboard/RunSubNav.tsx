'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const ITEMS = [{ seg: '', l: '儀表板' }, { seg: '/live3d', l: '3D 即時' }, { seg: '/events', l: '事件流' }, { seg: '/playback', l: '回放' }];
/** run 各頁共用的右上導覽(目前所在頁高亮) */
export function RunSubNav({ id }: { id: string }) {
  const path = usePathname();
  return <nav className="sub">{ITEMS.map((it) => { const href = `/runs/${id}${it.seg}`; return <Link key={it.seg} href={href} className={path === href ? 'on' : ''}>{it.l}</Link>; })}</nav>;
}
