'use client';
import { MONITOR_BASE_URL } from '@/config';
import { CheckList } from '@/components/scene-editor/CheckList';
import type { Check } from '@/hooks/feature/sceneChecks';
import type { PrecomputeStatus } from '@/services/api/runs';
import type { SceneRun } from '@/types/registry';
import { effectiveRun, lastResultLabel, statusLabel } from '@/hooks/feature/runStatus';

interface Props {
  run: SceneRun | null; checks: Check[]; precomp: PrecomputeStatus | null; saving: boolean;
  onPrecompute: () => void; onStopPrecompute: () => void; onStart: () => void; onStop: () => void; onRefresh: () => void;
}
const eta = (s: number) => (s >= 3600 ? `${(s / 3600).toFixed(1)} h` : `${Math.ceil(s / 60)} 分`);
/** 步驟 4:啟動前檢查 → Precompute(cached)→ 啟動 / 停止 → 監控 */
export function LaunchPanel({ run, checks, precomp, saving, onPrecompute, onStopPrecompute, onStart, onStop, onRefresh }: Props) {
  const blocked = checks.some((c) => c.level === 'error');
  const running = run?.status === 'running'; const computing = run?.status === 'precomputing';
  const pg = precomp?.progress;
  return (
    <div className="launch">
      <div className="row head">狀態 <button className="ghost" onClick={onRefresh}>重新整理</button></div>
      <p>{run ? <><span className={`pill ${run.status}`}>{statusLabel(run)}</span> {lastResultLabel(run) && <span className="muted small">{lastResultLabel(run)} · </span>}<span className="muted small">{effectiveRun(run).mode} · {effectiveRun(run).speed_x}× · {run.duration_sec}s{effectiveRun(run).note ? `(${effectiveRun(run).note})` : ''}</span></> : <span className="muted">尚未建立 run</span>}</p>
      <CheckList title="啟動前檢查" checks={checks} />
      {run?.mode === 'cached' && <>
        <div className="row head">Precompute <span className="muted">GPU 光追;預算後可加速到 10×,沒預算以 live 1× 啟動</span></div>
        {computing && <div className="prog-row"><div className="prog"><i style={{ width: `${pg?.pct ?? 0}%` }} /></div><span className="mono small">{pg ? `${pg.pct.toFixed(1)}% · ${pg.rate_tps.toFixed(0)} t/s · 剩 ${eta(pg.eta_sec)}` : '準備中…'}</span></div>}
        <div className="actions">{computing ? <button className="danger" disabled={saving} onClick={onStopPrecompute}>停止 Precompute</button>
          : <button disabled={saving || running} onClick={onPrecompute}>{run.cache_path ? '重新 Precompute' : '開始 Precompute'}</button>}</div>
        {run.cache_path && <p className="muted small mono">{run.cache_path.split('/').pop()}</p>}
      </>}
      <div className="row head">執行</div>
      <div className="actions">
        {running ? <button className="danger" disabled={saving} onClick={() => { if (confirm('停止這個 run?')) onStop(); }}>停止</button>
          : <button className="primary" disabled={saving || !run || computing} onClick={() => { if (!blocked || confirm('檢查有錯誤,仍要啟動?')) onStart(); }}>啟動</button>}
        {run && <a className="btnlink" href={`${MONITOR_BASE_URL}/runs/${run.scene_run_uuid}`} target="_blank" rel="noreferrer">開監控 ↗</a>}
      </div>
      <p className="muted small">啟動後會自動註冊到 RIC 閘道並部署專屬 xApp;允許的控制種類由 orchestrator 設定(RIC_GATEWAY_ALLOWED_STYLES)。同一場景要多份對照,請在步驟 1 用「複製場景」。</p>
    </div>
  );
}
