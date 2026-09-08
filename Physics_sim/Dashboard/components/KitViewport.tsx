'use client';

import { useMemo, useState } from 'react';
import { VNC_URL } from '@/config';

/**
 * 把 Omniverse Kit 的畫面（經 noVNC）嵌在 Scene Layout 旁邊。
 *
 * Kit 容器跑 `websockify --web /usr/share/novnc 6080 localhost:5900`，
 * noVNC 是純前端 JS 客戶端，所以嵌進來只要一個 iframe —— 不涉及 XHR，
 * 不需要 CORS，也不需要同源。
 *
 * 兩個刻意的設計：
 *
 * 1. **收合時整個 unmount iframe**，不是 display:none。x11vnc 目前是
 *    `-noshm -noxdamage -noscr`（全畫面重推），連著就一直吃 CPU 與頻寬，
 *    看不到的時候必須真的把連線斷掉。
 * 2. **預設唯讀**。嵌入的畫面比原生視窗小很多，滑鼠一滑就可能在 Kit 裡
 *    誤拖物件或改到 stage；要操作再自己解鎖。
 */

interface Props {
  height?: number;
  /** 預設是否展開。第一次進頁面不自動連，避免使用者還沒要看就先吃頻寬。 */
  defaultOpen?: boolean;
}

const btn = (active: boolean): React.CSSProperties => ({
  padding: '4px 10px',
  fontSize: '11px',
  borderRadius: '4px',
  cursor: 'pointer',
  border: '1px solid #ccc',
  background: active ? '#2563eb' : '#111827',
  color: active ? '#fff' : '#9ca3af',
});

export function KitViewport({ height = 600, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const [viewOnly, setViewOnly] = useState(true);
  // 改 key 就能強制 iframe 重新掛載 = 重新連線
  const [reloadKey, setReloadKey] = useState(0);

  const src = useMemo(() => {
    const base = VNC_URL || 'http://localhost:6080/vnc.html';
    const params = new URLSearchParams({
      autoconnect: 'true',
      resize: 'scale',        // 把 1920x1080 縮進 iframe，不是裁切
      reconnect: 'true',
      quality: '6',           // 畫質/頻寬折衷；Kit viewport 一直在動，全開會很重
      compression: '6',
      view_only: viewOnly ? '1' : '0',
    });
    return `${base}?${params.toString()}`;
  }, [viewOnly]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '12px', fontWeight: 600, color: '#9ca3af' }}>
          Omniverse 畫面
        </span>
        <button style={btn(open)} onClick={() => setOpen(!open)}>
          {open ? '中斷連線' : '連線'}
        </button>
        {open && (
          <>
            <button style={btn(!viewOnly)} onClick={() => setViewOnly(!viewOnly)}>
              {viewOnly ? '唯讀' : '可操作'}
            </button>
            <button style={btn(false)} onClick={() => setReloadKey((k) => k + 1)}>
              重新連線
            </button>
          </>
        )}
        <a
          href={VNC_URL}
          target="_blank"
          rel="noreferrer"
          style={{ ...btn(false), textDecoration: 'none', display: 'inline-block' }}
        >
          開新視窗
        </a>
      </div>

      <div
        style={{
          height,
          background: '#0d0d1a',
          border: '1px solid #1a1a3e',
          borderRadius: 6,
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {open ? (
          <iframe
            key={`${reloadKey}-${viewOnly}`}
            src={src}
            title="Omniverse Kit viewport"
            style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
            allow="fullscreen"
          />
        ) : (
          <div
            style={{
              height: '100%', display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: '8px',
              color: '#6b7280', fontSize: '12px', padding: '16px', textAlign: 'center',
            }}
          >
            <div>未連線</div>
            <div style={{ fontSize: '11px', lineHeight: 1.6 }}>
              Kit 的畫面是整個桌面串流，連著會持續佔用頻寬與 CPU。
              <br />
              需要看 3D 渲染結果時再按「連線」。
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
