import type { Metadata } from 'next';
import { NavBar } from '@/components/NavBar';
import { SimProvider } from '@/components/SimProvider';
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
    cuUrl: process.env.CU_URL || `http://${process.env.SERVER_IP || 'localhost'}:8101`,
    duUrl: process.env.DU_URL || `http://${process.env.SERVER_IP || 'localhost'}:8102`,
    ruUrl: process.env.RU_URL || `http://${process.env.SERVER_IP || 'localhost'}:8103`,
    physicsUrl: process.env.PHYSICS_URL || `http://${process.env.SERVER_IP || 'localhost'}:8104`,
    e2AdapterUrl: process.env.E2_ADAPTER_URL || `http://${process.env.SERVER_IP || 'localhost'}:8201`,
    ueUrl: process.env.UE_URL || `http://${process.env.SERVER_IP || 'localhost'}:8105`,
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
      <body style={{ background: '#0b1220', color: '#cbd5e1', minHeight: '100vh' }}>
        <SimProvider>
          <NavBar />
          <main style={{ padding: '24px', background: '#0b1220', minHeight: 'calc(100vh - 60px)' }}>
            {children}
          </main>
        </SimProvider>
      </body>
    </html>
  );
}
