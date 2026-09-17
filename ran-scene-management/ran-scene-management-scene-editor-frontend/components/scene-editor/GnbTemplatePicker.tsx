'use client';
import Link from 'next/link';
import type { GnbConfigTemplate } from '@/types/registry';

/** 步驟 2:放 gNB 時要套用哪個模板(模板本身在「網路元件」頁維護;選中物件後也能在右側「現場存成模板」) */
export function GnbTemplatePicker({ templates, value, onChange }: { templates: GnbConfigTemplate[]; value: string; onChange: (uuid: string) => void }) {
  const cur = templates.find((t) => t.gnb_config_template_uuid === value) ?? templates.find((t) => t.source === 'oai') ?? templates[0];
  return (
    <div className="tplpick">
      <div className="row head">放置時套用模板</div>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">預設(OAI 對齊)</option>
        {templates.map((t) => <option key={t.gnb_config_template_uuid} value={t.gnb_config_template_uuid}>{t.name}{t.source ? ` · ${t.source}` : ''}</option>)}
      </select>
      {cur && <p className="muted small">{cur.cells_per_gnb} cell · {cur.band} {cur.center_frequency_ghz} GHz · {cur.bandwidth_mhz} MHz · {cur.power_dbm} dBm · A3 {cur.a3_enabled ? '開' : '關'}</p>}
      <p className="muted small">模板管理:<Link href="/network-elements">網路元件</Link></p>
    </div>
  );
}
