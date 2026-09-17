'use client';
import Link from 'next/link';
import { EDITOR_STEPS, type EditorStep } from '@/config';

/** 場景建置四步驟導覽:目前步驟高亮;每一步都可以直接點回去改 */
export function StepBar({ sceneUuid, step }: { sceneUuid: string; step: EditorStep }) {
  const cur = EDITOR_STEPS.findIndex((s) => s.key === step);
  return (
    <nav className="stepbar">
      {EDITOR_STEPS.map((s, i) => (
        <Link key={s.key} href={`/scenes/${sceneUuid}/${s.key}`} className={`step ${i === cur ? 'on' : i < cur ? 'done' : ''}`} title={s.hint}>
          <b>{s.label}</b><span className="muted small">{s.hint}</span>
        </Link>))}
    </nav>
  );
}
