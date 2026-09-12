'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // 自動重導向到新的 Scene Editor
    router.push('/editor');
  }, [router]);


  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh'
    }}>
      <p>Redirecting to Scene Editor...</p>
    </div>
  );
}
