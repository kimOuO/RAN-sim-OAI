'use client';

import { useEffect, useState } from 'react';
import {
  generateMap,
  listMaps,
  applyMapToScene,
  detachMap,
  deleteMap,
  geocodeLandmark,
  type MapRow,
  type GeocodeResult,
} from '@/services/api/map';

// OSM → USD 地圖產生面板:輸入名稱 + 4 座標 → 產生 USD → 名稱選取套用到 3D 場景。
// 座標順序對齊 OSM Export 面板:minLon(左) / minLat(下) / maxLon(右) / maxLat(上)。

interface Props {
  disabled?: boolean;
  onApplied?: () => void; // 套用後可觸發外層 refreshScene
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

export function MapGenerator({ disabled, onApplied }: Props) {
  const [name, setName] = useState('');
  const [minLon, setMinLon] = useState('');
  const [minLat, setMinLat] = useState('');
  const [maxLon, setMaxLon] = useState('');
  const [maxLat, setMaxLat] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const [maps, setMaps] = useState<MapRow[]>([]);
  const [selected, setSelected] = useState('');
  const [applying, setApplying] = useState(false);

  // 地標搜尋 → 自動填座標
  const [searchQ, setSearchQ] = useState('');
  const [searching, setSearching] = useState(false);
  const [candidates, setCandidates] = useState<GeocodeResult[]>([]);

  const reload = async () => {
    try {
      const rows = await listMaps();
      setMaps(rows);
      const act = rows.find((m) => m.active);   // 反映當前套用的地圖
      if (act) setSelected(act.name);
    } catch { /* backend 未就緒時忽略 */ }
  };
  useEffect(() => { reload(); }, []);

  const activeMap = maps.find((m) => m.active);

  const onSearch = async () => {
    if (!searchQ.trim()) return;
    setSearching(true); setMsg(''); setCandidates([]);
    try {
      const rows = await geocodeLandmark(searchQ.trim());
      setCandidates(rows);
      setMsg(rows.length ? `✓ 找到 ${rows.length} 個候選,點選以填入座標` : '✗ 查無此地標');
    } catch (e: any) {
      setMsg(`✗ 搜尋失敗:${e?.response?.data?.message ?? e?.message ?? e}`);
    } finally {
      setSearching(false);
    }
  };

  const pickCandidate = (r: GeocodeResult) => {
    setName(r.name.replace(/\s+/g, '_'));
    setMinLon(String(r.bbox.min_lon));
    setMinLat(String(r.bbox.min_lat));
    setMaxLon(String(r.bbox.max_lon));
    setMaxLat(String(r.bbox.max_lat));
    setCandidates([]);
    setMsg(`✓ 已填入「${r.name}」座標,可直接產生地圖`);
  };

  const onGenerate = async () => {
    setMsg('');
    if (!name.trim()) { setMsg('✗ 請輸入名稱'); return; }
    const nums = [minLon, minLat, maxLon, maxLat].map(parseFloat);
    if (nums.some((n) => Number.isNaN(n))) { setMsg('✗ 4 個座標都要填數字'); return; }
    setBusy(true);
    try {
      const row = await generateMap({
        name: name.trim(),
        min_lon: nums[0], min_lat: nums[1], max_lon: nums[2], max_lat: nums[3],
      });
      setMsg(`✓ ${row.name}:${row.building_count} 棟,${Math.round(row.extent_ew_m)}×${Math.round(row.extent_ns_m)} m`);
      await reload();
      setSelected(row.name);
    } catch (e: any) {
      setMsg(`✗ 產生失敗:${e?.response?.data?.message ?? e?.message ?? e}`);
    } finally {
      setBusy(false);
    }
  };

  const onApply = async (mapName: string) => {
    setSelected(mapName);
    if (!mapName) return;
    setApplying(true); setMsg('');
    try {
      await applyMapToScene(mapName);
      setMsg(`✓ 已套用「${mapName}」為當前場景(原物件已清空,可再加 gNB/UE)`);
      await reload();
      onApplied?.();
    } catch (e: any) {
      setMsg(`✗ 套用失敗:${e?.response?.data?.message ?? e?.message ?? e}`);
    } finally {
      setApplying(false);
    }
  };

  const onDetach = async () => {
    setApplying(true); setMsg('');
    try {
      await detachMap();
      setSelected('');
      setMsg('✓ 已移除當前地圖');
      await reload();
      onApplied?.();
    } catch (e: any) {
      setMsg(`✗ 移除失敗:${e?.response?.data?.message ?? e?.message ?? e}`);
    } finally {
      setApplying(false);
    }
  };

  const onDelete = async () => {
    if (!selected) return;
    if (!confirm(`刪除地圖「${selected}」?`)) return;
    try { await deleteMap(selected); setSelected(''); await reload(); setMsg('✓ 已刪除'); }
    catch (e: any) { setMsg(`✗ 刪除失敗:${e?.message ?? e}`); }
  };

  const anyBusy = busy || applying || disabled;

  return (
    <div style={{ marginBottom: '32px' }}>
      <h3 style={{ fontSize: '13px', fontWeight: 600, color: '#9ca3af', marginBottom: '12px' }}>
        地圖產生器 (OpenStreetMap → 3D)
      </h3>

      {/* 地標搜尋 → 自動填座標 */}
      <div style={{ marginBottom: '8px' }}>
        <label style={labelStyle}>🔍 用地標搜尋(自動填座標)</label>
        <div style={{ display: 'flex', gap: '6px' }}>
          <input style={{ ...inputStyle, flex: 1 }} value={searchQ}
            disabled={anyBusy || searching}
            onChange={(e) => setSearchQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') onSearch(); }}
            placeholder="例:台北101、中正紀念堂" />
          <button style={{ ...btn('#3b82f6', anyBusy || searching), width: '64px', padding: '7px 0' }}
            disabled={anyBusy || searching} onClick={onSearch}>
            {searching ? '…' : '搜尋'}
          </button>
        </div>
        {candidates.length > 0 && (
          <div style={{ marginTop: '4px', border: '1px solid #374151', borderRadius: '5px', overflow: 'hidden' }}>
            {candidates.map((r, i) => (
              <div key={i} onClick={() => pickCandidate(r)}
                style={{ padding: '6px 9px', fontSize: '11px', color: '#cbd5e1', cursor: 'pointer',
                         background: i % 2 ? '#0f172a' : '#111827', lineHeight: 1.3 }}
                title={r.display_name}>
                <span style={{ color: '#e5e7eb', fontWeight: 600 }}>{r.name}</span>
                <span style={{ color: '#64748b' }}> ({r.type})</span>
                <div style={{ color: '#64748b' }}>{r.display_name.slice(0, 55)}…</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 名稱 */}
      <div style={{ marginBottom: '8px' }}>
        <label style={labelStyle}>名稱(選取用,例:NTUST)</label>
        <input style={inputStyle} value={name} disabled={anyBusy}
          onChange={(e) => setName(e.target.value)} placeholder="NTUST" />
      </div>

      {/* 4 座標 2×2 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '8px' }}>
        <div><label style={labelStyle}>minLon(左/西經)</label>
          <input style={inputStyle} type="number" step="0.0001" value={minLon} disabled={anyBusy}
            onChange={(e) => setMinLon(e.target.value)} placeholder="121.5396" /></div>
        <div><label style={labelStyle}>minLat(下/南緯)</label>
          <input style={inputStyle} type="number" step="0.0001" value={minLat} disabled={anyBusy}
            onChange={(e) => setMinLat(e.target.value)} placeholder="25.0114" /></div>
        <div><label style={labelStyle}>maxLon(右/東經)</label>
          <input style={inputStyle} type="number" step="0.0001" value={maxLon} disabled={anyBusy}
            onChange={(e) => setMaxLon(e.target.value)} placeholder="121.5444" /></div>
        <div><label style={labelStyle}>maxLat(上/北緯)</label>
          <input style={inputStyle} type="number" step="0.0001" value={maxLat} disabled={anyBusy}
            onChange={(e) => setMaxLat(e.target.value)} placeholder="25.0156" /></div>
      </div>

      <button style={btn('#22c55e', anyBusy)} disabled={anyBusy} onClick={onGenerate}>
        {busy ? '產生中…(抓 OSM + 轉 USD,約 10-30 秒)' : '產生地圖'}
      </button>

      {/* 已存在的地圖:名稱選取 + 套用 */}
      <div style={{ marginTop: '14px' }}>
        <label style={labelStyle}>選既有地圖套用到場景</label>
        <select style={{ ...inputStyle, cursor: anyBusy ? 'not-allowed' : 'pointer' }}
          value={selected} disabled={anyBusy}
          onChange={(e) => onApply(e.target.value)}>
          <option value="">— 選地圖套用 —</option>
          {maps.map((m) => (
            <option key={m.name} value={m.name} disabled={m.status !== 'ready'}>
              {m.name} {m.status === 'ready' ? `(${m.building_count} 棟)` : `(${m.status})`}
            </option>
          ))}
        </select>
        {activeMap && (
          <div style={{ fontSize: '11px', color: '#22c55e', marginTop: '6px' }}>
            ● 目前場景地圖:{activeMap.name}（{activeMap.building_count} 棟）
          </div>
        )}
        <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
          {activeMap && (
            <button style={{ ...btn('transparent'), color: '#f59e0b', border: '1px solid #374151' }}
              disabled={anyBusy} onClick={onDetach}>移除地圖</button>
          )}
          {selected && (
            <button style={{ ...btn('transparent'), color: '#ef4444', border: '1px solid #374151' }}
              disabled={anyBusy} onClick={onDelete}>刪除「{selected}」</button>
          )}
        </div>
      </div>

      <div style={{ fontSize: '11px', color: msg.startsWith('✗') ? '#f87171' : '#6b7280', marginTop: '8px', lineHeight: 1.4 }}>
        {msg || '座標可到 openstreetmap.org 用 Export 面板框選取得。'}
      </div>
    </div>
  );
}
