'use client';
import type { UeLabelMode } from '@/components/scene3d/LiveScene3D';

/** 3D 標籤開關:UE 標籤三段(預設「簡要」= 服務 cell + DL 吞吐)、站台名稱(gNB / DU / cell) */
export function LabelControls({ mode, setMode, sites, setSites }: { mode: UeLabelMode; setMode: (m: UeLabelMode) => void; sites: boolean; setSites: (v: boolean) => void }) {
  return (
    <span className="labelctl">
      <span className="muted small">UE 標籤</span>
      {([['none', '不顯示'], ['name', '名稱'], ['brief', '簡要']] as [UeLabelMode, string][]).map(([k, l]) =>
        <button key={k} className={`chip ${mode === k ? 'on' : ''}`} onClick={() => setMode(k)}>{l}</button>)}
      <label className="check-inline"><input type="checkbox" checked={sites} onChange={(e) => setSites(e.target.checked)} /> 站台名稱</label>
    </span>
  );
}
