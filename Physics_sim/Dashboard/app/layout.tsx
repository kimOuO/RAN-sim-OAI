import type { Metadata } from 'next';
import { NavBar } from '@/components/NavBar';
import '@/styles/globals.css';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'RAN Digital Twin',
  description: 'Ray tracing-based 5G RAN simulation platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const config = {
    apiBaseUrl: process.env.API_BASE_URL || 'http://localhost:8000',
    omniverseUrl: process.env.OMNIVERSE_URL || 'http://localhost:8001',
    vncUrl: process.env.VNC_URL || 'http://localhost:6080/vnc.html',
    wsUrl: process.env.WS_URL || 'ws://localhost:8000/ws/sim/live/',
  };

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__APP_CONFIG__=${JSON.stringify(config)};`,
          }}
        />
      </head>
      <body>
        <NavBar />
        <main style={{ padding: '24px' }}>
          {children}
        </main>
      </body>
    </html>
  );
}
