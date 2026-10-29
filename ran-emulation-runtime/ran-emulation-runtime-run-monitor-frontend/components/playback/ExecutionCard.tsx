'use client';
import Link from 'next/link';
import { SceneThumb } from '@/components/playback/SceneThumb';
import { fmtSimTime } from '@/hooks/feature/kpmDerive';
import type { RunExecution, SceneTree3d } from '@/types/telemetry';

const fmtDate = (ms: number | null) => (ms ? new Date(ms).toLocaleString('zh-TW', { hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—');

/** 回放清單的一張卡:這次執行的時間、劇本、組別、時長、規模與事件數,點了才進回放 */
export function ExecutionCard({ e, name, category, mode, tree, latest }: { e: RunExecution; name: string; category?: string; mode?: string; tree: SceneTree3d | null | undefined; latest?: boolean }) {
  const href = `/runs/${e.f_scene_run_uuid}/playback?seq=${e.run_seq}`;
  const speed = e.sim_sec && e.wall_sec ? e.sim_sec / e.wall_sec : null;
  return (
    <Link href={href} className="exec-card">
      <SceneThumb tree={tree} />
      <div className="exec-body">
        <div className="exec-h"><b>{name}</b>{latest && <span className="tag son">最新</span>}</div>
        <div className="muted small">{category ? `組別 ${category}` : '未分組'}{mode ? ` · ${mode === 'cached' ? '快取通道' : '即時通道'}` : ''} · 第 {e.run_seq} 次執行</div>
        <dl>
          <dt>執行時間</dt><dd>{fmtDate(e.started_ms)}</dd>
          <dt>模擬時長</dt><dd>{e.sim_sec != null ? fmtSimTime(e.sim_sec) : '—'}<span className="muted"> (實際 {fmtSimTime(e.wall_sec)}{speed ? ` · ${speed.toFixed(2)}×` : ''})</span></dd>
          <dt>規模</dt><dd>{e.cell_count} cell · 結束時 {e.ue_count} UE · {e.windows} 個量測視窗</dd>
          <dt>事件</dt><dd>換手 {e.handover_succ} · RLF {e.rlf} · 控制命令 {e.controls}</dd>
        </dl>
      </div>
    </Link>
  );
}
