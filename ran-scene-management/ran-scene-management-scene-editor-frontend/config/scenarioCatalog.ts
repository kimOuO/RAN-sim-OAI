// 劇本資料集分類 —— /scenarios 頁的分頁依據。
// 劇本一多就找不到,這裡把它們歸到「資料集(dataset)」,頁面用分頁 + 搜尋呈現。
//
// 新增劇本時:若 scenario_id 有前綴規則(anr_/cco_/es_/im_/dt_)會自動落到對應資料集,
// 只有需要顯示中文題名/說明時才要在 SCENARIO_LABELS 補一筆。

export interface DatasetMeta {
  id: string;
  label: string;
  desc: string;
  color: string;
  /** 判斷某 scenario_id 是否屬於此資料集 */
  match: (id: string) => boolean;
}

/** ANR 十二題:scenario_id → 題號(對齊 ANR情境_v8.docx 與 docs/anr_validation/README.md) */
export const ANR_CASE_NO: Record<string, number> = {
  anr_missing_neighbor: 1,
  anr_missing_meas: 2,
  anr_sparse_edge: 3,
  anr_unknown_cell: 4,
  anr_pci_confusion: 5,
  anr_xn_discovery: 6,
  anr_harmful_neighbor: 7,
  anr_inter_freq: 8,
  anr_nrt_capacity: 9,
  anr_stale_pci: 10,
  anr_stale_relation: 11,
  anr_attr_audit: 12,
};

/** 顯示名稱與一句話說明(沒列到的劇本就直接顯示 scenario_id) */
export const SCENARIO_LABELS: Record<string, { label: string; desc: string }> = {
  anr_missing_neighbor: { label: '缺漏鄰區(重建反推)', desc: 'src↔nbr 無關係 → RLF 重建集中同一 prevPci → ADD 止血' },
  anr_missing_meas:     { label: '缺漏鄰區(量測偵測)', desc: '量測看得到強鄰但 NRT 查無 → ADD;停用 ANR 時只能 SMO_NOTIFY' },
  anr_sparse_edge:      { label: '缺漏鄰區(深邊緣稀疏)', desc: '偏遠鄰區樣本稀疏 → 需低樣本下仍敢 ADD' },
  anr_unknown_cell:     { label: '未知 cell 偵測',       desc: '量測出現全新 NCGI → REPORTCGI 解析 → ADD' },
  anr_pci_confusion:    { label: 'PCI 撞號(擋)',        desc: '同 PCI 兩 cell → confusion=true → 必須抑制 ADD' },
  anr_xn_discovery:     { label: 'Xn-C 探索失敗(不動手)', desc: '關係在但 Xn 未建 → TXnRELOCprepExpiry → 只發 SMO_NOTIFY' },
  anr_harmful_neighbor: { label: '有害鄰居',             desc: '訊號可、接入失敗 → FLAG hoBlocklist 封而不刪' },
  anr_inter_freq:       { label: '跨頻鄰區啟用',         desc: '缺 2.1GHz 頻率層 → 帶 arfcn 的 REPORTCGI + ADD' },
  anr_nrt_capacity:     { label: 'NRT 容量修剪',         desc: 'used==limit 擋住 ADD → 先 REMOVE 零活動再 ADD' },
  anr_stale_pci:        { label: '過期對應(同站換 PCI)', desc: '關係存舊 PCI → CellNotAvailable → REMOVE 後重 ADD' },
  anr_stale_relation:   { label: '老化 / 自動刪除',       desc: '關係老且零活動 → REMOVE;noRemove 保護條目須拒絕' },
  anr_attr_audit:       { label: 'NRT 屬性稽核(不動手)', desc: '屬性看似異常但有正當理由 → 只稽核不改' },
  anr_neutral_healthy:  { label: '中性健康對照組',        desc: '全連通健康網路 — 驗十二支 guard 常駐不誤報' },
  anr_veto_variant:     { label: 'mobility 仲裁變體',     desc: '驗「該讓要讓 / 不該讓不讓」的讓路仲裁' },
  cco_20min:            { label: 'CCO 容量受限換手',      desc: 'cell 間 PRB 失衡 → RC handover' },
  im_fast:              { label: 'IM 干擾管理',           desc: 'PRB 滿 + channel 弱 → PRB quota cap' },
  cco_fast:             { label: 'CCO(短)',             desc: 'cell 間 PRB 失衡 → handover' },
  es_fast:              { label: 'ES 節能',               desc: '低載 + 無流量 → HO + PRB cap' },
};

export const DATASETS: DatasetMeta[] = [
  {
    id: 'anr',
    label: 'ANR 十二題',
    desc: 'ANR情境_v8.docx 十二題 + 對照組 —— 每題一劇本,配 RIC guard xApp 驗證',
    color: '#22c55e',
    match: (id) => id.startsWith('anr_'),
  },
  {
    id: 'trigger',
    label: '觸發情境(IM / CCO / ES)',
    desc: '三大 RIC 控制觸發 demo:干擾管理、覆蓋容量最佳化、節能',
    color: '#f59e0b',
    match: (id) => /^(im|cco|es)_/.test(id),
  },
  {
    id: 'kpm',
    label: 'KPM 對照 / 校正',
    desc: '對 OAI rfsim 校正用的資料收集劇本(dt_*、full_day_*、kpm_*)',
    color: '#38bdf8',
    match: (id) => /^(dt_|full_day|kpm_|recover_|multi)/.test(id),
  },
  {
    id: 'other',
    label: '其他 / 未分類',
    desc: '未落入上述資料集的劇本',
    color: '#94a3b8',
    match: () => true,   // fallback,放最後
  },
];

/** scenario_id → 所屬 dataset id(依序第一個命中者) */
export const datasetOf = (id: string): string =>
  (DATASETS.find(d => d.match(id)) ?? DATASETS[DATASETS.length - 1]).id;

/** 卡片標題:ANR 題目加「Q#」前綴,其餘用中文名或原 id */
export const displayName = (id: string): string => {
  const no = ANR_CASE_NO[id];
  const lbl = SCENARIO_LABELS[id]?.label;
  if (no) return `Q${no} ${lbl ?? id}`;
  return lbl ?? id;
};
