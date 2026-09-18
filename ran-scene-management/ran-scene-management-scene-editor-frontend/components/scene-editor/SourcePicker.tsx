'use client';
import Link from 'next/link';

export type SceneSource = 'map' | 'scan';

/** 步驟 1 第一層:場景從哪裡來 */
export function SourcePicker({ hasGeometry, onPick, onCancel }: { hasGeometry: boolean; onPick: (s: SceneSource) => void; onCancel: (() => void) | null }) {
  return (
    <div className="sourcepick">
      <h2>場景從哪裡來?</h2>
      {hasGeometry && <p className="msg small">這個場景已經有幾何;選新的來源會取代它(gNB / UE 保留)。</p>}
      <div className="sourcecards">
        <button className="sourcecard" onClick={() => onPick('map')}>
          <b>從地圖建立</b>
          <span>搜尋地標,自動框出範圍後再調整多邊形;讀取範圍內的 OSM 建築,逐棟設定材質與高度。</span>
        </button>
        <button className="sourcecard" onClick={() => onPick('scan')}>
          <b>上傳掃描檔</b>
          <span>上傳 3D 掃描模型(.glb),自動分類材質並轉成傳播用場景,直接進 3D。</span>
        </button>
      </div>
      <p className="muted small">已有劇本 JSON?到 <Link href="/imports">匯入</Link> 頁。{onCancel && <> · <button className="link" onClick={onCancel}>回到 3D</button></>}</p>
    </div>
  );
}
