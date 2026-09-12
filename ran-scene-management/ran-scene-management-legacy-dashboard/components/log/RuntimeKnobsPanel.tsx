'use client';

import { useEffect, useState } from 'react';
import { DU_BASE_URL } from '@/config';
import { fetchDriverStatus } from '@/services/api/scenarioMonitor';

const C_CARD = '#111827';
const C_BORDER = '#374151';
const C_TEXT = '#cbd5e1';
const C_MUTED = '#6b7280';
const C_ADJ = '#f59e0b';   // 已調整(非預設)— 橘色提醒
const C_DEF = '#10b981';   // 預設值 — 綠色

interface RuntimePhys {
  inter_freq: boolean;
  discard_timer_ms: number;
  tx_power_dbm: number;
  rlc_delay_model: string;
  noise_floor_dbm: number;
  slot_engine_takeover: boolean;
  defaults: Record<string, unknown>;
  adjusted: string[];
}

const POLL_MS = 3000;

// 每個旋鈕對 KPM 的影響註解 — 讓使用者知道「為什麼這個調整會改 KPM」。
const KNOB_META: Record<string, { label: string; effect: string }> = {
  tx_power_dbm:     { label: 'TX Power (dBm)',     effect: '↑功率 → RSRP/SINR↑ → MCS↑ → throughput↑、PRB↓' },
  inter_freq:       { label: 'Inter-Freq (關互擾)', effect: 'on = 跨 cell 不互擾 → SINR↑(換手後回升成立)' },
  discard_timer_ms: { label: 'RLC discardTimer (ms)', effect: '封頂過載 delay;0/小 = 丟包早、delay 不爆;大 = delay 真實爬' },
  rlc_delay_model:  { label: 'RLC delay model',    effect: 'calib = ÷30 對齊 OAI 低 delay;subtick = 誠實佇列延遲(壅塞真爬)' },
};

export function RuntimeKnobsPanel() {
  const [phys, setPhys] = useState<RuntimePhys | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [simRunning, setSimRunning] = useState(false);

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const [r, driver] = await Promise.all([
          fetch(
            `${DU_BASE_URL}/api/v0.1/DU/MAC/MacScheduler/get_runtime_phys`,
            { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' },
          ),
          fetchDriverStatus().catch(() => null),
        ]);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (stop) return;
        setSimRunning(!!driver?.running);
        setPhys(j?.data ?? null);
        setError('');
        setLoading(false);
      } catch (e: any) {
        if (stop) return;
        setError(e?.message || String(e));
        setLoading(false);
      }
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { stop = true; clearInterval(id); };
  }, []);

  const adjusted = new Set(phys?.adjusted ?? []);
  const rows: Array<{ key: string; value: string }> = phys ? [
    { key: 'tx_power_dbm', value: `${phys.tx_power_dbm}` },
    { key: 'inter_freq', value: phys.inter_freq ? 'on' : 'off' },
    { key: 'discard_timer_ms', value: `${phys.discard_timer_ms}` },
    { key: 'rlc_delay_model', value: phys.rlc_delay_model },
  ] : [];

  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{ margin: 0, color: C_TEXT, fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
        🎛 Sim Runtime Knobs （非 xApp 的 DU 調整，會影響 KPM）
      </h2>
      <div style={{ color: C_MUTED, fontSize: 11, marginBottom: 12 }}>
        劇本在 Start Sim 時靜默套用的物理旋鈕。<span style={{ color: C_ADJ }}>橘色 = 已被劇本/手動調過(非預設)</span>,
        <span style={{ color: C_DEF }}> 綠色 = 預設</span>。KPM 對不上時先看這裡。
      </div>

      <div style={{ background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8, padding: 12 }}>
        {error && <div style={{ color: '#ef4444', fontSize: 11, marginBottom: 8 }}>err: {error}</div>}
        {loading && !phys ? (
          <div style={{ color: C_MUTED, fontSize: 12 }}>loading...</div>
        ) : !simRunning ? (
          <div style={{ color: C_MUTED, fontSize: 12 }}>
            劇本已結束 — 已清除。這些旋鈕跟著劇本走,下次 Start Sim 套用新劇本時才會顯示。
          </div>
        ) : !phys ? (
          <div style={{ color: C_MUTED, fontSize: 12 }}>(DU runtime phys 取不到)</div>
        ) : (
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C_BORDER}`, color: C_MUTED, fontSize: 11 }}>
                <th style={{ textAlign: 'left', padding: 6 }}>旋鈕</th>
                <th style={{ textAlign: 'right', padding: 6 }}>現值</th>
                <th style={{ textAlign: 'right', padding: 6 }}>預設</th>
                <th style={{ textAlign: 'left', padding: 6 }}>對 KPM 的影響</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ key, value }) => {
                const isAdj = adjusted.has(key);
                const meta = KNOB_META[key];
                const def = phys.defaults?.[key];
                const defStr = typeof def === 'boolean' ? (def ? 'on' : 'off') : String(def);
                return (
                  <tr key={key} style={{ borderBottom: '1px solid #1f2937' }}>
                    <td style={{ padding: 6, color: C_TEXT }}>{meta?.label ?? key}</td>
                    <td style={{
                      padding: 6, textAlign: 'right', fontFamily: 'monospace', fontWeight: 600,
                      color: isAdj ? C_ADJ : C_DEF,
                    }}>
                      {value}{isAdj ? ' ●' : ''}
                    </td>
                    <td style={{ padding: 6, textAlign: 'right', fontFamily: 'monospace', color: C_MUTED }}>
                      {defStr}
                    </td>
                    <td style={{ padding: 6, color: C_MUTED, fontSize: 10 }}>{meta?.effect ?? ''}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        {phys && simRunning && (
          <div style={{ fontSize: 10, color: C_MUTED, marginTop: 10, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <span>noise floor: <span style={{ color: C_TEXT }}>{phys.noise_floor_dbm} dBm</span></span>
            <span>slot engine takeover: <span style={{ color: C_TEXT }}>{phys.slot_engine_takeover ? 'on (delay 走 slot engine)' : 'off (delay 走 calib ÷30)'}</span></span>
            <span style={{ marginLeft: 'auto' }}>
              {adjusted.size > 0
                ? `⚠ ${adjusted.size} 項已調整 — KPM 受影響`
                : '✓ 全部預設 — KPM 為基準'}
            </span>
          </div>
        )}
        <div style={{
          fontSize: 10, color: C_MUTED, marginTop: 8, paddingTop: 8,
          borderTop: `1px solid ${C_BORDER}`, lineHeight: 1.5,
        }}>
          ★ 備註:劇本若帶 <span style={{ color: C_TEXT }}>cell_quotas</span>(如 PRB 容量上限)等限制,
          是<span style={{ color: '#06b6d4' }}> 劇本觸發 </span>(非 xApp 即時下發)。
          這些 quota 顯示在下方「🎯 Intent-Driven Control Audit → Active PRB Quotas」,來源標
          <span style={{ color: '#06b6d4' }}> 劇本</span>;<span style={{ color: '#a855f7' }}>xApp</span> 才是 RIC 即時控制。
        </div>
      </div>
    </section>
  );
}
