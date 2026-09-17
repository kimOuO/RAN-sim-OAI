'use client';
import Link from 'next/link';
import type { ReactNode } from 'react';
import type { EditorStep } from '@/config';
import { StepBar } from '@/components/scene-editor/StepBar';
import type { SceneTree } from '@/types/registry';

/** 四個步驟頁共用的外框:頂部路徑 + 步驟列 + 左 / 中(畫布)/ 右 三欄 */
export function EditorLayout({ tree, step, saving, message, progress, left, center, right, next }: {
  tree: SceneTree; step: EditorStep; saving: boolean; message: string | null; progress?: string | null;
  left: ReactNode; center: ReactNode; right: ReactNode; next?: { href: string; label: string; blocked?: string | null };
}) {
  const sid = tree.scene.scene_uuid;
  return (
    <section className="editor">
      <div className="editor-bar"><Link href="/scenes" className="muted">場景</Link><span className="muted">/</span><b>{tree.scene.name}</b>
        {tree.scene.legacy_scenario_id && <span className="muted small">劇本 {tree.scene.legacy_scenario_id}</span>}
        <span className="sp" />{progress && <span className="muted small">{progress}</span>}{saving && !progress && <span className="muted small">儲存中…</span>}{message && <span className="msg small">{message}</span>}
        {next && <Link className={`nextbtn ${next.blocked ? 'blocked' : ''}`} href={next.href} title={next.blocked ?? ''}
          onClick={(e) => { if (next.blocked && !confirm(`${next.blocked}\n仍要前往下一步?`)) e.preventDefault(); }}>{next.label} →</Link>}
      </div>
      <StepBar sceneUuid={sid} step={step} />
      <div className="editor-body"><div className="left">{left}</div><div className="center">{center}</div>{right}</div>
    </section>
  );
}
