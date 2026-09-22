import type { SceneRun, SceneTree } from '@/types/registry';
import { sceneExtent } from '@/hooks/feature/sceneGeometry';

export type CheckLevel = 'error' | 'warn' | 'ok';
export interface Check { level: CheckLevel; text: string }

const cellsOf = (tree: SceneTree) => tree.gnbs.flatMap((g) => g.dus.flatMap((d) => d.cells.map((c) => ({ g, c, pos: c.position ?? g.position }))));

/** 步驟 1:場景有沒有幾何可以算傳播 */
export function environmentChecks(tree: SceneTree): Check[] {
  const src = tree.scene.geometry_source as { type?: string } | null;
  const out: Check[] = [];
  if (src?.type === 'mitsuba_xml_path') out.push({ level: 'ok', text: '使用掃描模型(mitsuba)' });
  else if (tree.buildings.length) out.push({ level: 'ok', text: `${tree.buildings.length} 棟建築` });
  else out.push({ level: 'warn', text: '沒有建築也沒有掃描模型:傳播會用自由空間計算' });
  const noMat = tree.buildings.filter((b) => b.source === 'manual_box' && !b.f_material_uuid).length;
  if (noMat) out.push({ level: 'warn', text: `${noMat} 個建築盒沒指定材質(用場景預設)` });
  return out;
}

/** 步驟 2:gNB / cell 設定的常見問題 */
export function networkChecks(tree: SceneTree): Check[] {
  const out: Check[] = [];
  const cells = cellsOf(tree);
  if (!tree.gnbs.length) return [{ level: 'error', text: '還沒有 gNB' }];
  // 同站同頻:位置相同(誤差 0.5 m)且中心頻率相同的 cell 互相干擾
  const groups = new Map<string, number>();
  cells.forEach(({ c, pos }) => { const k = `${Math.round(pos[0] * 2)}:${Math.round(pos[2] * 2)}:${c.center_frequency_ghz}`; groups.set(k, (groups.get(k) ?? 0) + 1); });
  const coSite = [...groups.values()].filter((n) => n > 1);
  if (coSite.length) out.push({ level: 'warn', text: `同站同頻的 cell 有 ${coSite.reduce((a, b) => a + b, 0)} 個:扇區間干擾大,室內窄空間容易 RLF;可改異頻或確認天線方向` });
  // PCI 衝突:同頻 PCI 重複
  const pci = new Map<string, number>();
  cells.forEach(({ c }) => { const k = `${c.center_frequency_ghz}:${c.pci}`; pci.set(k, (pci.get(k) ?? 0) + 1); });
  const dup = [...pci.entries()].filter(([, n]) => n > 1).map(([k]) => k.split(':')[1]);
  if (dup.length) out.push({ level: 'error', text: `同頻 PCI 重複:${dup.join(', ')}` });
  const noA3 = tree.gnbs.filter((g) => !g.a3_enabled).length;
  if (cells.length > 1 && noA3) out.push({ level: 'warn', text: `${noA3} 個 gNB 沒開 A3 換手:UE 只能在 RLF 後重新駐留換 cell` });
  const noAnt = cells.filter(({ c }) => !c.ru?.f_antenna_preset_uuid && !tree.scene.f_gnb_antenna_preset_uuid).length;
  // 2026-09-22:原本寫「用 1×1 iso,沒有方向性」是錯的 —— Physics 端沒指定 preset 時的
  // 預設是 1×1 tr38901,元件本身有 8 dBi 指向性與 65° HPBW,方位角是有作用的。
  // 缺的是「陣列」增益與波束成形(要多元件),不是方向性。
  if (noAnt) out.push({ level: 'ok', text: `${noAnt} 個 cell 沒指定天線 preset(用 1×1 tr38901:有元件方向性,無陣列增益與波束成形)` });
  if (!out.length) out.push({ level: 'ok', text: `${tree.gnbs.length} gNB · ${cells.length} cell 設定沒有明顯問題` });
  return out;
}

/** 步驟 3:UE 路徑與流量 */
export function ueChecks(tree: SceneTree): Check[] {
  if (!tree.ues.length) return [{ level: 'error', text: '還沒有 UE' }];
  const out: Check[] = [];
  const noTraffic = tree.ues.filter((u) => !u.traffic.length).length;
  if (noTraffic) out.push({ level: 'warn', text: `${noTraffic} 個 UE 沒有流量(只量測、不排程)` });
  const still = tree.ues.filter((u) => u.waypoints.length < 2).length;
  if (still) out.push({ level: 'ok', text: `${still} 個 UE 固定不動` });
  const e = sceneExtent({ ...tree, ues: [] });
  const pad = 5;
  const outside = tree.gnbs.length || tree.buildings.length
    ? tree.ues.filter((u) => u.waypoints.some((w) => w[1] < e.xMin - pad || w[1] > e.xMax + pad || w[3] < e.zMin - pad || w[3] > e.zMax + pad)).length : 0;
  if (outside && !tree.scene.geometry_source) out.push({ level: 'warn', text: `${outside} 個 UE 的路徑跑出建築 / gNB 的範圍` });
  out.push({ level: 'ok', text: `${tree.ues.length} 個 UE` });
  return out;
}

/** 步驟 4:啟動前檢查 */
export function launchChecks(tree: SceneTree, run: SceneRun | null, allRuns: SceneRun[],
                             knobs: { key: string; value: unknown }[] = []): Check[] {
  const out: Check[] = [];
  if (!run) return [{ level: 'error', text: '還沒有 run 設定(儲存下面的設定會自動建立)' }];
  const errors = [...networkChecks(tree), ...ueChecks(tree)].filter((c) => c.level === 'error');
  errors.forEach((c) => out.push(c));
  const others = allRuns.filter((r) => r.scene_run_uuid !== run.scene_run_uuid && r.status === 'running');
  if (run.mode === 'live' && others.some((r) => r.mode === 'live')) out.push({ level: 'error', text: '已有另一個 live run 在跑(同時只允許 1 個;請改 cached 或先停掉)' });
  // 以 cache_path 判斷(匯入的劇本 run 可能是 draft 但已有 cache)
  if (run.mode === 'cached' && run.status === 'precomputing') out.push({ level: 'error', text: 'Precompute 還在跑' });
  else if (run.mode === 'cached' && !run.cache_path) out.push({ level: 'error', text: 'cached 模式沒有 cache,請先 Precompute' });
  if (others.length >= 4) out.push({ level: 'warn', text: `已有 ${others.length} 個 run 在跑,再加一個可能吃滿主機記憶體` });
  if (run.speed_x > 5 && tree.ues.length > 10) out.push({ level: 'warn', text: `倍速 ${run.speed_x}× 搭配 ${tree.ues.length} 個 UE,RU 可能跟不上而被健康檢查重啟` });
  // 2026-09-21:ric_purpose 是黏著的 run knob,設過一次之後這個 scene_run 每次啟動
  // 都會以驗證場次宣告給 RIC —— 對方會排主動探測並期待我們給快照。這種有遠端後果
  // 的設定不能只靜靜列在 knob 清單裡,啟動前要明講。
  // 走廊這種「每個 cell 各自一個 gNB」的場景,跨 gNB 鄰區關係不會自動種。
  // 沒開 anr_auto_add 又沒有 RIC 的 xApp 補,A3 會被 NRT gate 全部擋掉(實測一場 7 萬次)。
  const autoAnr = knobs.find((k) => k.key === 'anr_auto_add')?.value;
  const gnbCount = tree.gnbs.length;
  if (gnbCount > 1 && !autoAnr) {
    out.push({ level: 'warn', text: `${gnbCount} 個 gNB 但沒設 anr_auto_add —— 跨 gNB 的鄰區關係不會自動建立,A3 換手會被擋掉。單機跑請加這個 knob(值 1);要驗證 RIC 的 ANR 才留空。` });
  }
  const purpose = knobs.find((k) => k.key === 'ric_purpose')?.value;
  if (purpose) out.push({ level: 'warn', text: `這一場會以 labels.purpose=${String(purpose)} 宣告給 RIC —— 對方會排主動探測並期待數值快照。常規觀測請先移除這個 knob。` });
  if (!out.length) out.push({ level: 'ok', text: '可以啟動' });
  return out;
}
