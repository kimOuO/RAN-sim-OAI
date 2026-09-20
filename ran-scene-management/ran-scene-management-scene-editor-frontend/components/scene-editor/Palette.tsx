'use client';
import type { PlaceKind } from '@/hooks/feature/useSceneEditorPage';
const ITEMS: { kind: Exclude<PlaceKind, null>; icon: string; label: string; hint: string }[] = [
  { kind: 'gnb', icon: '▲', label: 'gNB', hint: '自帶 1 DU / 1 cell / 1 RU' }, { kind: 'cell', icon: '◉', label: 'Cell(拉遠)', hint: '先選 gNB;DAS 獨立位置' },
  { kind: 'ue', icon: '●', label: 'UE', hint: '起點 waypoint' }, { kind: 'building', icon: '▦', label: '建築盒', hint: '10×6×10 m,可改尺寸/材質' },
];
/** 元件庫:點一個 → 進放置模式 → 點畫布地面放下 */
export function Palette({ placeKind, onPick, kinds, blocked }: {
  placeKind: PlaceKind; onPick: (k: PlaceKind) => void; kinds?: Exclude<PlaceKind, null>[];
  /** kind → 不能放的原因;有值就停用該按鈕並顯示原因(以前只寫在 title,點下去沒反應像壞掉) */
  blocked?: Partial<Record<Exclude<PlaceKind, null>, string>>;
}) {
  const items = kinds ? ITEMS.filter((it) => kinds.includes(it.kind)) : ITEMS;
  const why = placeKind ? blocked?.[placeKind] : undefined;
  return (
    <div className="palette">
      <div className="row head">元件庫 <span className="muted">點選後點畫布放置(貼齊地面 / 屋頂 / 模型表面);放好可直接拖曳換位置</span></div>
      <div className="palette-grid">{items.map((it) => <button key={it.kind} className={`pal ${placeKind === it.kind ? 'on' : ''}`} disabled={!!blocked?.[it.kind]}
          onClick={() => onPick(placeKind === it.kind ? null : it.kind)}
          title={blocked?.[it.kind] ? `${blocked[it.kind]} — ${it.hint}` : it.hint}><span className="ico">{it.icon}</span><span>{it.label}</span></button>)}</div>
      {placeKind && (why
        ? <p className="msg small warn">還不能放 {ITEMS.find((i) => i.kind === placeKind)?.label}:{why}</p>
        : <p className="msg small">放置模式:點畫布地面放下 {ITEMS.find((i) => i.kind === placeKind)?.label}(Esc 取消)</p>)}
    </div>
  );
}
