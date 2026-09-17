'use client';
import type { Check } from '@/hooks/feature/sceneChecks';

const ICON = { error: '✕', warn: '!', ok: '✓' } as const;
/** 檢查清單:error 擋下一步(可略過),warn 只提示 */
export function CheckList({ title, checks }: { title: string; checks: Check[] }) {
  return (
    <div className="checks">
      <div className="row head">{title}</div>
      {checks.map((c, i) => <div key={i} className={`check ${c.level}`}><i>{ICON[c.level]}</i><span>{c.text}</span></div>)}
    </div>
  );
}
