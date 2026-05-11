'use client';

import { useEffect, useState } from 'react';
import { readA3, setA3, type A3Config } from '@/services/api/mobility';

/**
 * A3 Handover Control Panel — toggle A3 enable / tune offset / hys / ttt.
 * AK11: runtime control, sim CU 不用 restart.
 *
 * Usage: drop into /logs or any settings page:
 *   <A3ControlPanel />
 */
export function A3ControlPanel() {
  const [cfg, setCfg] = useState<A3Config | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string>('');

  const reload = async () => {
    try {
      setLoading(true);
      setErr('');
      const c = await readA3();
      setCfg(c);
    } catch (e: any) {
      setErr(e?.message || 'read failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { reload(); }, []);

  const update = async (patch: Partial<A3Config>) => {
    try {
      setLoading(true);
      setErr('');
      const c = await setA3(patch);
      setCfg(c);
    } catch (e: any) {
      setErr(e?.message || 'set failed');
    } finally {
      setLoading(false);
    }
  };

  if (!cfg) {
    return (
      <div style={panelStyle}>
        <h3 style={{ margin: 0, fontSize: 14 }}>A3 Handover Control</h3>
        <div style={{ fontSize: 12, color: '#888' }}>{err || 'loading...'}</div>
      </div>
    );
  }

  return (
    <div style={panelStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <h3 style={{ margin: 0, fontSize: 14, flex: 1 }}>A3 Handover Control</h3>
        <span
          style={{
            display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
            background: cfg.enabled ? '#22c55e' : '#ef4444',
          }}
        />
        <span style={{ fontSize: 12, color: cfg.enabled ? '#22c55e' : '#ef4444' }}>
          {cfg.enabled ? 'ENABLED' : 'DISABLED'}
        </span>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <button
          onClick={() => update({ enabled: !cfg.enabled })}
          disabled={loading}
          style={btnStyle(cfg.enabled ? '#ef4444' : '#22c55e')}
        >
          {cfg.enabled ? 'Disable A3' : 'Enable A3'}
        </button>
        <button onClick={reload} disabled={loading} style={btnStyle('#3b82f6')}>
          Refresh
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: 6, fontSize: 12 }}>
        <label>offset (dB)</label>
        <input
          type="number"
          step="0.1"
          value={cfg.offset_db}
          onChange={e => setCfg({ ...cfg, offset_db: parseFloat(e.target.value) })}
          onBlur={() => update({ offset_db: cfg.offset_db })}
          style={inputStyle}
        />
        <span style={{ color: '#888' }}>spec 0~3, demo 0.5</span>

        <label>hysteresis (dB)</label>
        <input
          type="number"
          step="0.1"
          value={cfg.hys_db}
          onChange={e => setCfg({ ...cfg, hys_db: parseFloat(e.target.value) })}
          onBlur={() => update({ hys_db: cfg.hys_db })}
          style={inputStyle}
        />
        <span style={{ color: '#888' }}>spec 0~15, demo 0.3</span>

        <label>TTT (ms)</label>
        <input
          type="number"
          step="10"
          value={cfg.ttt_ms}
          onChange={e => setCfg({ ...cfg, ttt_ms: parseInt(e.target.value) })}
          onBlur={() => update({ ttt_ms: cfg.ttt_ms })}
          style={inputStyle}
        />
        <span style={{ color: '#888' }}>spec 40~5120, demo 60</span>
      </div>

      {err && <div style={{ color: '#ef4444', fontSize: 11, marginTop: 6 }}>{err}</div>}

      <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 8 }}>
        關閉 A3: RIC RC.HO control_handover 不會被 sim 自動 rollback (CCO/ES demo 用).
        開啟 A3: sim 自動依 RSRP 變化做 HO (production behavior).
      </div>
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  padding: 12, border: '1px solid #1f2937', background: '#0b1220',
  borderRadius: 6, color: '#e5e7eb', minWidth: 320,
};

const inputStyle: React.CSSProperties = {
  width: 80, padding: '2px 6px', background: '#111827',
  border: '1px solid #1f2937', borderRadius: 3, color: '#e5e7eb', fontSize: 12,
};

const btnStyle = (color: string): React.CSSProperties => ({
  padding: '4px 10px', background: color, border: 'none', borderRadius: 4,
  color: '#fff', fontSize: 12, cursor: 'pointer',
});
