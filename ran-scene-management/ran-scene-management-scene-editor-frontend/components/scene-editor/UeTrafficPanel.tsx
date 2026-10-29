'use client';
import { useEffect, useState } from 'react';
import type { Ue, UeTraffic } from '@/types/registry';

/** 選到 UE 時:流量(cbr 固定速率 / piecewise 時間表)與在場時段 */
export function UeTrafficPanel({ ue, saving, onTraffic, onWindows }: { ue: Ue; saving: boolean; onTraffic: (u: Ue, t: Partial<UeTraffic>) => void; onWindows: (u: Ue, w: [number, number][], restricted?: boolean) => void }) {
  const t = ue.traffic[0];
  const [pattern, setPattern] = useState(t?.pattern ?? 'cbr');
  const [rate, setRate] = useState(String(t?.rate_mbps ?? 1));
  const [sched, setSched] = useState(JSON.stringify(t?.schedule ?? []));
  const [win, setWin] = useState(ue.active_windows.map((w) => w.join('-')).join(', '));
  const [absent, setAbsent] = useState(!!ue.presence_restricted && !ue.active_windows.length);
  useEffect(() => { setAbsent(!!ue.presence_restricted && !ue.active_windows.length); }, [ue]);
  useEffect(() => { setPattern(t?.pattern ?? 'cbr'); setRate(String(t?.rate_mbps ?? 1)); setSched(JSON.stringify(t?.schedule ?? [])); setWin(ue.active_windows.map((w) => w.join('-')).join(', ')); }, [ue]);   // eslint-disable-line react-hooks/exhaustive-deps
  const parsed = (() => { try { const v = JSON.parse(sched); return Array.isArray(v) ? (v as number[][]) : null; } catch { return null; } })();
  const windows = win.trim() ? win.split(',').map((x) => x.trim().split('-').map(Number) as [number, number]) : [];
  const windowsValid = windows.every((w) => w.length === 2 && w.every(Number.isFinite) && w[0] >= 0 && w[1] > w[0]);
  const avg = parsed?.length ? parsed.reduce((a, r) => a + (r[1] ?? 0), 0) / parsed.length : null;
  return (
    <div className="uetraffic">
      <div className="row head">流量</div>
      <label><span>型態</span><select value={pattern} onChange={(e) => setPattern(e.target.value)}><option value="cbr">cbr(固定)</option><option value="piecewise">piecewise(時間表)</option></select></label>
      {pattern === 'cbr' ? <label><span>DL Mbps</span><input type="number" value={rate} onChange={(e) => setRate(e.target.value)} /></label>
        : <><label className="stack"><span>時間表 [秒, DL kbps, UL kbps]</span><textarea rows={4} value={sched} onChange={(e) => setSched(e.target.value)} /></label>
          <p className="muted small">{parsed ? `${parsed.length} 段 · 平均 DL ${avg?.toFixed(0)} kbps` : 'JSON 格式錯誤'}</p></>}
      <div className="actions"><button className="primary" disabled={saving || (pattern === 'piecewise' && !parsed)} onClick={() => onTraffic(ue, pattern === 'cbr' ? { pattern, rate_mbps: Number(rate), schedule: null } : { pattern, rate_mbps: 0, schedule: parsed })}>儲存流量</button></div>
      <div className="row head">在場時段</div>
      <label><span>全程不在場</span><input type="checkbox" checked={absent} onChange={(e) => setAbsent(e.target.checked)} /></label>
      <label className="stack"><span>秒,例:0-300, 600-900(空白 = 全程)</span><input disabled={absent} value={win} onChange={(e) => setWin(e.target.value)} /></label>
      {!absent && !windowsValid && <p className="err small">每段需為有效的起訖秒數，結束時間大於開始時間。</p>}
      <div className="actions"><button disabled={saving || (!absent && !windowsValid)} onClick={() => onWindows(ue, absent ? [] : windows, absent || windows.length > 0)}>儲存時段</button></div>
    </div>
  );
}
