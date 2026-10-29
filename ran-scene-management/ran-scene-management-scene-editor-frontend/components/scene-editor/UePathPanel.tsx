'use client';
import { useEffect, useState } from 'react';
import type { Ue } from '@/types/registry';

export function UePathPanel({ ue, saving, onSave }: { ue: Ue; saving: boolean; onSave: (u: Ue, points: Ue['waypoints']) => void }) {
  const [rows, setRows] = useState<string[][]>([]);
  useEffect(() => { setRows(ue.waypoints.map((p) => p.map(String))); }, [ue]);
  const points = rows.map((r) => r.map(Number) as [number, number, number, number]);
  const valid = !!points.length && rows.every((r) => r.every((v) => v.trim() !== '')) && points.every((p, i) =>
    p.every(Number.isFinite) && (i === 0 ? p[0] === 0 : p[0] > points[i - 1][0]));
  return <div className="uetraffic">
    <div className="row head">移動路徑 · {rows.length} 點</div>
    <p className="muted small">第一點時間為 0 秒，後續時間遞增；兩點間等速移動，最後停在終點。單點代表靜止。</p>
    <div className="path-editor-wrap"><table className="path-editor"><colgroup><col className="c-t" /><col /><col /><col /><col className="c-del" /></colgroup>
      <thead><tr><th>秒</th><th>X m</th><th>Y m</th><th>Z m</th><th /></tr></thead>
      <tbody>{rows.map((row, i) => <tr key={i}>{row.map((value, j) => <td key={j}><input aria-label={`路徑點 ${i + 1} ${['秒', 'X', 'Y', 'Z'][j]}`} type="number" step="any" value={value} title={value} disabled={saving}
        onChange={(e) => setRows((old) => old.map((r, k) => k === i ? r.map((v, n) => n === j ? e.target.value : v) : r))} /></td>)}
        <td><button aria-label={`刪除路徑點 ${i + 1}`} disabled={saving || rows.length === 1} onClick={() => setRows((old) => old.filter((_, k) => k !== i))}>×</button></td></tr>)}</tbody></table></div>
    {!valid && <p className="err small">請填入有限數值；第一點為 0 秒，後續時間須大於前一點。</p>}
    <div className="actions"><button disabled={saving} onClick={() => setRows((old) => {
      const last = old.at(-1); return [...old, last ? [String((Number(last[0]) || 0) + 30), ...last.slice(1)] : ['0', '0', String(ue.antenna_height_m), '0']];
    })}>新增路徑點</button><button className="primary" disabled={saving || !valid} onClick={() => onSave(ue, points)}>儲存路徑</button></div>
    <p className="muted small">儲存後可用下方播放列預覽；已啟動的 Run 要重啟才會使用新路徑，cached 模式請重新預算。</p>
  </div>;
}
