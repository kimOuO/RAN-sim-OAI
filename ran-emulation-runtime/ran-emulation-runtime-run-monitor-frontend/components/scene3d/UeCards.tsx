'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ueAttached, type CellOwner } from '@/hooks/feature/live3d';
import type { UeKpm } from '@/types/telemetry';

type UeState = Record<string, UeKpm & { cell: string }>;
type Sort = 'name' | 'sinr';
const f1 = (v: number | null | undefined) => (v == null || !Number.isFinite(v) ? '—' : v.toFixed(1));

/** 3D 旁的 UE 卡片:每個 UE 一張,隨 KPM 輪詢更新。外框 = 服務 cell 顏色;SINR < 0 dB 標紅;點卡片 = 在 3D 選取該 UE */
export function UeCards({ names, ueState, color, owners, selected, onSelect }: {
  names: string[]; ueState: UeState; color: Record<string, string>; owners: Record<string, CellOwner>;
  selected: string | null; onSelect: (ue: string | null) => void;
}) {
  const [sort, setSort] = useState<Sort>('name');
  const [onlyBad, setOnlyBad] = useState(false);
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  // 3D 點選 UE 時把對應卡片捲進可視範圍
  useEffect(() => { if (selected) refs.current[selected]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }, [selected]);
  const rows = useMemo(() => {
    const bad = (n: string) => !ueAttached(ueState[n]) || ueState[n].sinr_db < 0;
    const list = names.filter((n) => !onlyBad || bad(n));
    return sort === 'name' ? list.sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
      : list.sort((a, b) => (ueState[a]?.sinr_db ?? -999) - (ueState[b]?.sinr_db ?? -999));
  }, [names, ueState, sort, onlyBad]);
  const attached = names.filter((n) => ueAttached(ueState[n])).length;
  return (
    <aside className="uecards">
      <div className="uecards-h">
        <b>UE {attached}/{names.length} 附著</b>
        <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}><option value="name">依名稱</option><option value="sinr">SINR 低→高</option></select>
        <label className="check-inline"><input type="checkbox" checked={onlyBad} onChange={(e) => setOnlyBad(e.target.checked)} /> 只看異常</label>
      </div>
      <div className="uecards-list">
        {rows.map((n) => {
          const s = ueState[n]; const on = ueAttached(s); const o = on ? owners[s.cell] : undefined;
          const col = on ? color[s.cell] ?? '#888' : '#5b6778'; const low = on && s.sinr_db < 0;
          return (
            <button key={n} ref={(el) => { refs.current[n] = el; }} className={`uecard ${selected === n ? 'on' : ''} ${low ? 'low' : ''}`}
              style={{ borderLeftColor: col }} onClick={() => onSelect(selected === n ? null : n)}>
              <div className="uecard-h"><b className="mono">{n}</b>{on ? <span className="mono" style={{ color: col }}>{s.cell}</span> : <span className="muted">未附著</span>}</div>
              {on && <>
                <div className="uecard-sub mono">{o ? `${o.gnb} / ${o.du} · PCI ${o.pci}` : '—'}</div>
                <dl>
                  <dt>SINR</dt><dd className={low ? 'bad' : ''}>{f1(s.sinr_db)} dB</dd>
                  <dt>RSRP</dt><dd>{f1(s.rsrp_dbm)} dBm</dd>
                  <dt>DL / UL</dt><dd>{f1(s.throughput_dl_mbps)} / {f1(s.throughput_ul_mbps)} Mb/s</dd>
                  <dt>MCS</dt><dd>{s.mcs_dl} / {s.mcs_ul ?? '—'}</dd>
                  <dt>PRB</dt><dd>{s.rb_width_dl} / {s.rb_width_ul ?? '—'}</dd>
                  <dt>5QI</dt><dd>{s.qos_5qi}{s.beam_id != null ? ` · beam #${s.beam_id}` : ''}</dd>
                </dl>
              </>}
            </button>);
        })}
        {!rows.length && <p className="muted small">{onlyBad ? '沒有異常的 UE' : '沒有 UE'}</p>}
      </div>
    </aside>
  );
}
