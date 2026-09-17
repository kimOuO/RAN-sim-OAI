'use client';
import type { ReactNode } from 'react';
import type { useSceneEditorPage } from '@/hooks/feature/useSceneEditorPage';

/** 載入中 / 錯誤的共用處理;樹到手才畫步驟內容 */
export function StepGate({ p, children }: { p: ReturnType<typeof useSceneEditorPage>; children: (tree: NonNullable<ReturnType<typeof useSceneEditorPage>['tree']>) => ReactNode }) {
  if (p.status === 'loading' && !p.tree) return <p className="muted shell page">載入場景…</p>;
  if (p.error) return <p className="err shell page">{p.error.message}</p>;
  return p.tree ? <>{children(p.tree)}</> : null;
}
