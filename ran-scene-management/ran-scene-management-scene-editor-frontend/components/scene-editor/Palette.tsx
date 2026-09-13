'use client';
import type { PlaceKind } from '@/hooks/feature/useSceneEditorPage';
const ITEMS: { kind: Exclude<PlaceKind, null>; icon: string; label: string; hint: string }[] = [
  { kind: 'gnb', icon: '▲', label: 'gNB', hint: '自帶 1 DU / 1 cell / 1 RU' }, { kind: 'cell', icon: '◉', label: 'Cell(拉遠)', hint: '先選 gNB;DAS 獨立位置' },
  { kind: 'ue', icon: '●', label: 'UE', hint: '起點 waypoint' }, { kind: 'building', icon: '▦', label: '建築盒', hint: '10×6×10 m,可改尺寸/材質' },
];
/** 元件庫:點一個 → 進放置模式 → 點畫布地面放下 */
export function Palette({ placeKind, onPick }: { placeKind: PlaceKind; onPick: (k: PlaceKind) => void }) {
  return (
    <div className="palette">
      <div className="row head">元件庫 <span className="muted">點選後點畫布放置</span></div>
      <div className="palette-grid">{ITEMS.map((it) => <button key={it.kind} className={`pal ${placeKind === it.kind ? 'on' : ''}`} onClick={() => onPick(placeKind === it.kind ? null : it.kind)} title={it.hint}><span className="ico">{it.icon}</span><span>{it.label}</span></button>)}</div>
      {placeKind && <p className="msg small">放置模式:點畫布地面放下 {ITEMS.find((i) => i.kind === placeKind)?.label}(Esc 取消)</p>}
    </div>
  );
}
