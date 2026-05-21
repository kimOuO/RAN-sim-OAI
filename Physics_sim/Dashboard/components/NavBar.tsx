'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import styles from './NavBar.module.css';

const NAV_ITEMS = [
  { href: '/editor', label: 'Scene Editor' },
  { href: '/logs', label: 'Logs' },
  { href: '/scenarios', label: 'Scenarios' },
  { href: '/playback', label: 'Playback' },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <nav className={styles.navbar}>
      <h1 className={styles.title}>RAN Digital Twin</h1>
      <ul className={styles.navList}>
        {NAV_ITEMS.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className={pathname === item.href ? styles.active : ''}
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
