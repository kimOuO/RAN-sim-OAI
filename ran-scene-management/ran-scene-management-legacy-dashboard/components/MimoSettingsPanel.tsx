'use client';

import type { SceneAntennaConfig } from '@/types';

interface Props {
  config: SceneAntennaConfig;
  onChange: (next: SceneAntennaConfig) => void;
}

const POL_OPTIONS = ['V', 'H', 'VH', 'cross'] as const;
const PRESETS: Array<{ label: string; cfg: SceneAntennaConfig }> = [
  {
    label: 'SISO 1×1 (baseline)',
    cfg: {
      gnb_array_rows: 1, gnb_array_cols: 1, gnb_polarization: 'V',
      ue_array_rows: 1, ue_array_cols: 1, ue_polarization: 'V',
    },
  },
  {
    label: '4×2 cross / UE 1×2 cross (典型 5G mid-band)',
    cfg: {
      gnb_array_rows: 4, gnb_array_cols: 2, gnb_polarization: 'cross',
      ue_array_rows: 1, ue_array_cols: 2, ue_polarization: 'cross',
    },
  },
  {
    label: '8×4 cross / UE 2×2 cross (mMIMO)',
    cfg: {
      gnb_array_rows: 8, gnb_array_cols: 4, gnb_polarization: 'cross',
      ue_array_rows: 2, ue_array_cols: 2, ue_polarization: 'cross',
    },
  },
];

export function MimoSettingsPanel({ config, onChange }: Props) {
  const set = (patch: Partial<SceneAntennaConfig>) => onChange({ ...config, ...patch });

  const gnbPorts =
    (config.gnb_array_rows ?? 1) *
    (config.gnb_array_cols ?? 1) *
    (config.gnb_polarization === 'cross' || config.gnb_polarization === 'VH' ? 2 : 1);
  const uePorts =
    (config.ue_array_rows ?? 1) *
    (config.ue_array_cols ?? 1) *
    (config.ue_polarization === 'cross' || config.ue_polarization === 'VH' ? 2 : 1);

  return (
    <div style={{ padding: 12, border: '1px solid #ddd', borderRadius: 6, background: '#fafafa' }}>
      <h4 style={{ margin: '0 0 12px', fontSize: 14 }}>📡 MIMO Antenna Config</h4>

      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 12, fontWeight: 600 }}>Preset</label>
        <select
          style={{ width: '100%', padding: 4, marginTop: 4, fontSize: 12 }}
          onChange={(e) => {
            const idx = Number(e.target.value);
            if (!Number.isNaN(idx) && PRESETS[idx]) onChange(PRESETS[idx].cfg);
          }}
          defaultValue=""
        >
          <option value="" disabled>— select a preset —</option>
          {PRESETS.map((p, i) => (
            <option key={p.label} value={i}>{p.label}</option>
          ))}
        </select>
      </div>

      <fieldset style={{ marginBottom: 8, padding: 8, border: '1px solid #ccc', borderRadius: 4 }}>
        <legend style={{ fontSize: 12, fontWeight: 600 }}>gNB array</legend>
        <Row label="Rows">
          <NumInput
            value={config.gnb_array_rows ?? 1}
            min={1} max={16}
            onChange={(v) => set({ gnb_array_rows: v })}
          />
        </Row>
        <Row label="Cols">
          <NumInput
            value={config.gnb_array_cols ?? 1}
            min={1} max={16}
            onChange={(v) => set({ gnb_array_cols: v })}
          />
        </Row>
        <Row label="Polarization">
          <select
            value={config.gnb_polarization ?? 'V'}
            onChange={(e) => set({ gnb_polarization: e.target.value as any })}
            style={{ fontSize: 12, padding: 2 }}
          >
            {POL_OPTIONS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </Row>
      </fieldset>

      <fieldset style={{ marginBottom: 8, padding: 8, border: '1px solid #ccc', borderRadius: 4 }}>
        <legend style={{ fontSize: 12, fontWeight: 600 }}>UE array</legend>
        <Row label="Rows">
          <NumInput
            value={config.ue_array_rows ?? 1}
            min={1} max={4}
            onChange={(v) => set({ ue_array_rows: v })}
          />
        </Row>
        <Row label="Cols">
          <NumInput
            value={config.ue_array_cols ?? 1}
            min={1} max={4}
            onChange={(v) => set({ ue_array_cols: v })}
          />
        </Row>
        <Row label="Polarization">
          <select
            value={config.ue_polarization ?? 'V'}
            onChange={(e) => set({ ue_polarization: e.target.value as any })}
            style={{ fontSize: 12, padding: 2 }}
          >
            {POL_OPTIONS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </Row>
      </fieldset>

      <div style={{ fontSize: 11, color: '#666', lineHeight: 1.4 }}>
        Total ports: <b>gNB {gnbPorts}</b> · <b>UE {uePorts}</b>
        <br />
        套用後請按 <b>Build Scene</b> 觸發 Sionna 重新初始化。
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
      <span style={{ fontSize: 12 }}>{label}</span>
      {children}
    </div>
  );
}

function NumInput({ value, min, max, onChange }: { value: number; min: number; max: number; onChange: (v: number) => void }) {
  return (
    <input
      type="number"
      value={value}
      min={min}
      max={max}
      onChange={(e) => {
        const v = Number(e.target.value);
        if (!Number.isNaN(v)) onChange(Math.min(max, Math.max(min, v)));
      }}
      style={{ width: 60, fontSize: 12, padding: 2, textAlign: 'right' }}
    />
  );
}
