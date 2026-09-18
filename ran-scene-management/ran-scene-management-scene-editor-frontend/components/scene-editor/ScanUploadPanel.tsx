'use client';
import { useState } from 'react';
import { importScanGlb, setSceneScanGeometry } from '@/services/api/geometry';

/** 上傳掃描檔 → 材質分類 + Mitsuba → 設成場景幾何(不經地圖,直接進 3D) */
export function ScanUploadPanel({ sceneUuid, defaultName, onDone, onBack }: { sceneUuid: string; defaultName: string; onDone: () => void; onBack: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState(defaultName);
  const [mode, setMode] = useState<'conservative' | 'legacy_color'>('conservative');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const submit = async () => {
    if (!file) return;
    setBusy(true); setMsg(null);
    try {
      const a = await importScanGlb(file, name.trim(), mode);
      await setSceneScanGeometry(a.scan_asset_uuid, sceneUuid);
      onDone();
    } catch (e) { setMsg(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };
  return (
    <div className="sourcepick">
      <button className="link" onClick={onBack}>← 換場景來源</button>
      <h2>上傳掃描檔</h2>
      <div className="scanform">
        <label className="stack"><span>檔案(.glb,上限 300 MB)</span>
          <input type="file" accept=".glb,model/gltf-binary" onChange={(e) => { const f = e.target.files?.[0] ?? null; setFile(f); if (f && !name) setName(f.name.replace(/\.glb$/i, '')); }} /></label>
        <label className="stack"><span>幾何名稱</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="stack"><span>材質分類</span>
          <select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
            <option value="conservative">保守(依幾何與顏色,不確定的歸混凝土)</option>
            <option value="legacy_color">依顏色(舊版)</option>
          </select></label>
        <p className="muted small">上傳後會自動置中並貼齊地面(y = 0),轉成 Y 軸朝上的傳播場景。大檔可能要數分鐘。</p>
        <button className="primary" disabled={!file || !name.trim() || busy} onClick={() => void submit()}>{busy ? '上傳與轉換中…' : '上傳並建立場景 → 3D'}</button>
        {msg && <p className="err small">{msg}</p>}
      </div>
    </div>
  );
}
