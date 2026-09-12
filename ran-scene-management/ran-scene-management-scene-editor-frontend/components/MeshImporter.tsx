'use client';

import { useRef, useState } from 'react';
import {
  importGlb,
  applyMapToScene,
  setupIndoor,
  type GlbImportStats,
  type MaterialMode,
  type RadioMaterials,
} from '@/services/api/map';

// GLB/glTF 網格匯入面板：選檔 → 後端轉 USD → 註冊成一張地圖 → 可直接套用到場景。
// 與 MapGenerator 產生的 OSM 地圖共用同一份 MapScene 清單，所以匯入後
// 也會出現在上方的地圖選單裡，一樣能 apply / detach / delete。

interface Props {
  disabled?: boolean;
  onImported?: () => void; // 匯入或套用後觸發外層 refresh
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '7px 9px', background: '#111827', color: '#e5e7eb',
  border: '1px solid #374151', borderRadius: '5px', fontSize: '12px',
  boxSizing: 'border-box',
};
const labelStyle: React.CSSProperties = {
  fontSize: '10px', color: '#6b7280', marginBottom: '3px', display: 'block',
};

function btn(bg: string, disabled?: boolean): React.CSSProperties {
  return {
    width: '100%', padding: '9px 12px', background: disabled ? '#374151' : bg,
    color: '#fff', border: 'none', borderRadius: '6px', fontSize: '13px',
    fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
  };
}

/** 檔名 → 預設場景名（去副檔名、非法字元換底線，數字開頭補前綴）。 */
function nameFromFile(filename: string): string {
  const stem = filename.replace(/\.(glb|gltf)$/i, '');
  const safe = stem.replace(/[^A-Za-z0-9_-]/g, '_');
  return /^\d/.test(safe) ? `mesh_${safe}` : safe;
}

export function MeshImporter({ disabled, onImported }: Props) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [label, setLabel] = useState('');
  const [scale, setScale] = useState('1');
  const [recenter, setRecenter] = useState(true);
  const [materialMode, setMaterialMode] = useState<MaterialMode>('conservative');
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [msg, setMsg] = useState('');
  const [stats, setStats] = useState<GlbImportStats | null>(null);
  const [radio, setRadio] = useState<RadioMaterials | null>(null);
  const [importedName, setImportedName] = useState('');

  const pickFile = (f: File | null) => {
    setFile(f);
    setStats(null);
    setRadio(null);
    setImportedName('');
    setMsg('');
    if (f && !name.trim()) setName(nameFromFile(f.name));
  };

  const onImport = async () => {
    if (!file) { setMsg('✗ 請先選擇 .glb 檔'); return; }
    if (!name.trim()) { setMsg('✗ 請輸入名稱'); return; }
    const s = parseFloat(scale);
    if (Number.isNaN(s) || s <= 0) { setMsg('✗ 縮放需為大於 0 的數字'); return; }

    setBusy(true); setProgress(0); setMsg(''); setStats(null); setRadio(null);
    try {
      const row = await importGlb({
        file, name: name.trim(), label: label.trim() || undefined,
        scale: s, recenter, materialMode, onProgress: setProgress,
      });
      setStats(row.import_stats);
      setRadio(row.radio_materials ?? null);
      setImportedName(row.name);
      setMsg(
        `✓ ${row.name}:${row.import_stats.mesh_count} mesh / `
        + `${row.import_stats.triangle_count.toLocaleString()} 三角形,`
        + `${row.import_stats.extent_ew_m.toFixed(1)}×${row.import_stats.extent_ns_m.toFixed(1)} m`,
      );
      onImported?.();
    } catch (e: any) {
      setMsg(`✗ 匯入失敗:${e?.response?.data?.message ?? e?.message ?? e}`);
    } finally {
      setBusy(false);
      setProgress(0);
    }
  };

  const onApply = async () => {
    if (!importedName) return;
    setBusy(true); setMsg('');
    try {
      const r = await applyMapToScene(importedName);
      // 明講 Sionna 有沒有收到 —— 這一步同時推 Kit 與 Physics，
      // 但先前 UI 完全沒顯示，使用者不知道光追場景到底建了沒
      setMsg(
        `✓ 已套用「${importedName}」到 Kit（原物件已清空,可再加 gNB/UE）。`
        + (r.physics_pushed
            ? ' Sionna 光追場景已建立。'
            : ` ⚠ Sionna 未同步：${r.physics_error || '這張地圖沒有材質分類'}`),
      );
      onImported?.();
    } catch (e: any) {
      setMsg(`✗ 套用失敗:${e?.response?.data?.message ?? e?.message ?? e}`);
    } finally {
      setBusy(false);
    }
  };

  const onIndoor = async () => {
    if (!importedName) return;
    setBusy(true); setMsg('');
    try {
      const r = await setupIndoor(importedName);
      const ue = r.changes.ues.length;
      const gnb = r.changes.gnbs.length;
      setMsg(
        `✓ 已切換為室內尺度：${ue} 個 UE 高 ${r.changes.ues[0]?.target_height_m ?? 1.7} m `
        + `沿走廊巡走（路徑 ${r.path.path_length_m} m,不穿牆）、`
        + `${gnb} 個 gNB 移進室內（視覺尺寸 ×${r.gnb_visual_scale}）、`
        + `可走面積 ${r.grid.walkable_area_m2} m²、天花板已收起。`
        + (r.physics_pushed ? ' Sionna 光追場景已建立。'
                            : ` ⚠ Sionna 未同步：${r.physics_error}`),
      );
      onImported?.();
    } catch (e: any) {
      setMsg(`✗ 室內設定失敗:${e?.response?.data?.message ?? e?.message ?? e}`);
    } finally {
      setBusy(false);
    }
  };

  const anyBusy = busy || disabled;

  return (
    <div style={{ marginBottom: '32px' }}>
      <h3 style={{ fontSize: '13px', fontWeight: 600, color: '#9ca3af', marginBottom: '12px' }}>
        網格匯入 (GLB/glTF → USD)
      </h3>

      <div style={{ marginBottom: '10px' }}>
        <label style={labelStyle}>模型檔（.glb，glTF 2.0）</label>
        <input
          ref={fileRef}
          type="file"
          accept=".glb,model/gltf-binary"
          disabled={anyBusy}
          onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
          style={{ ...inputStyle, padding: '6px', fontSize: '11px' }}
        />
        {file && (
          <div style={{ fontSize: '10px', color: '#6b7280', marginTop: '4px' }}>
            {file.name} — {(file.size / 1e6).toFixed(1)} MB
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '10px' }}>
        <div>
          <label style={labelStyle}>名稱（選取鍵）</label>
          <input style={inputStyle} value={name} disabled={anyBusy}
                 onChange={(e) => setName(e.target.value)} placeholder="scan_20260906" />
        </div>
        <div>
          <label style={labelStyle}>顯示標籤（選填）</label>
          <input style={inputStyle} value={label} disabled={anyBusy}
                 onChange={(e) => setLabel(e.target.value)} placeholder="走廊掃描" />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '12px' }}>
        <div>
          <label style={labelStyle}>縮放（模型非公尺單位時調整）</label>
          <input style={inputStyle} value={scale} disabled={anyBusy}
                 onChange={(e) => setScale(e.target.value)} placeholder="1" />
        </div>
        <div>
          <label style={labelStyle}>置中對齊</label>
          <label style={{ ...inputStyle, display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
            <input type="checkbox" checked={recenter} disabled={anyBusy}
                   onChange={(e) => setRecenter(e.target.checked)} />
            <span style={{ fontSize: '11px' }}>移到原點、底部貼地</span>
          </label>
        </div>
      </div>

      <div style={{ marginBottom: '12px' }}>
        <label style={labelStyle}>材質分類（給 Sionna 用的 itu_* radio material）</label>
        <select
          style={{ ...inputStyle, cursor: 'pointer' }}
          value={materialMode}
          disabled={anyBusy}
          onChange={(e) => setMaterialMode(e.target.value as MaterialMode)}
        >
          <option value="conservative">保守（建議）— 只判混凝土與木頭</option>
          <option value="legacy_color">色彩全開（不建議）— 額外判玻璃/金屬</option>
        </select>
        <div style={{ fontSize: '10px', color: '#6b7280', marginTop: '4px', lineHeight: 1.6 }}>
          {materialMode === 'conservative'
            ? '玻璃透明、金屬鏡面，照片裡的外觀取決於周圍環境而非材質本身，無法用色彩判別。判不出的表面一律回退成不透明的混凝土。'
            : '⚠ 實測會把過曝的白牆判成玻璃、把牆面高光判成金屬。玻璃的穿透率遠高於混凝土，會嚴重低估室內隔離度。僅供比對。'}
        </div>
      </div>

      <button style={btn('#7c3aed', anyBusy || !file)} disabled={anyBusy || !file} onClick={onImport}>
        {busy && progress > 0 && progress < 100
          ? `上傳中… ${progress}%`
          : busy
            ? '轉換中…'
            : '匯入並轉成 USD'}
      </button>

      {importedName && !busy && (
        <>
          <button style={{ ...btn('#2563eb', anyBusy), marginTop: '8px' }} disabled={anyBusy} onClick={onApply}>
            套用「{importedName}」到 Kit + Sionna
          </button>
          <button style={{ ...btn('#059669', anyBusy), marginTop: '6px' }} disabled={anyBusy} onClick={onIndoor}>
            設為室內場景（UE 1.7 m、gNB 移進室內、天花板收起）
          </button>
          <div style={{ fontSize: '10px', color: '#6b7280', marginTop: '5px', lineHeight: 1.6 }}>
            兩個按鈕都會把 Mitsuba 場景推給 Sionna。室內掃描建議直接按第二個——
            它涵蓋第一個的所有動作，並額外把 UE 降到真人身高、沿走廊規劃不穿牆的路徑、
            把 gNB 移進室內並縮小視覺尺寸。
          </div>
        </>
      )}

      {msg && (
        <div style={{
          marginTop: '10px', fontSize: '11px',
          color: msg.startsWith('✓') ? '#4ade80' : '#f87171',
          lineHeight: 1.5,
        }}>
          {msg}
        </div>
      )}

      {stats && (
        <div style={{
          marginTop: '10px', padding: '8px 10px', background: '#111827',
          border: '1px solid #374151', borderRadius: '5px',
          fontSize: '10px', color: '#9ca3af', lineHeight: 1.7,
        }}>
          <div>網格 {stats.mesh_count} 個 · 三角形 {stats.triangle_count.toLocaleString()} · 頂點 {stats.vertex_count.toLocaleString()}</div>
          <div>材質 {stats.material_count} · 貼圖 {stats.texture_count} 張</div>
          <div>
            尺寸 {stats.extent_ew_m.toFixed(1)} × {stats.extent_ns_m.toFixed(1)} m，
            高 {stats.height_max_m.toFixed(1)} m
          </div>
          {radio?.evidence && (
            <div style={{ marginTop: '8px', borderTop: '1px solid #374151', paddingTop: '6px' }}>
              <div style={{ color: '#d1d5db' }}>材質分類（{radio.evidence.mode}）</div>
              {Object.entries(radio.materials).map(([k, v]) => (
                v.area_pct > 0 ? (
                  <div key={k}>
                    {k}：{v.area_m2.toFixed(1)} m²（{v.area_pct}%）
                  </div>
                ) : null
              ))}
              <div style={{ marginTop: '4px' }}>
                證據涵蓋：
                <span style={{ color: '#4ade80' }}>{radio.evidence.proven_area_pct}% 有證據</span>
                {' / '}
                <span style={{ color: '#fbbf24' }}>
                  {radio.evidence.fallback_area_pct}% 保守回退為 {radio.evidence.fallback_material}
                </span>
              </div>
              {radio.diagnostics && !radio.diagnostics.wood_boundary_reliable && (
                <div style={{ marginTop: '4px', color: '#fbbf24' }}>
                  ⚠ 木頭門檻邊界密度 {radio.diagnostics.wood_boundary_isolated_pct}%（&gt;2%）：
                  有一批「像木頭但沒判成木頭」的表面，木頭面積可能被低估。
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
