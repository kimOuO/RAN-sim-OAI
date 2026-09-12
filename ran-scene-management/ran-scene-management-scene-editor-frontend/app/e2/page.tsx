'use client';

/**
 * /e2 — E2 Data Explorer(只讀檢視,資料結構不變)
 *
 * 兩個資料源(輪詢,均為 CU 既有端點,原樣呈現不改結構):
 *   - POST /CU/E2/E2FullReporter/read   → FULLKPM(func 5 上 wire 的內容)
 *   - POST /CU/E2/Anr/indication        → ANR 觀測(func 6 上 wire 的內容)
 *
 * 以上兩支都是**上行**(sim → RIC 的 indication)。下行(xApp 下發的 RIC Control)
 * 走第三支,資料源在 adapter —— RC / CCC / ANR 三種控制都經過它,是唯一能一次
 * 看完所有下發命令的地方,也只有它握有 instId / ACK bytes / rtt:
 *   - POST /E2Adapter/ControlAudit/ControlAuditReader/read → 下發命令
 */

import { useEffect, useRef, useState } from 'react';
import { CU_BASE_URL, E2_ADAPTER_BASE_URL } from '@/config';
import { fetchLiveUePositions, type LiveUeSnapshot } from '@/services/api/ueLive';
import styles from './page.module.css';

const POLL_MS = 2000;

// ── types(對齊後端 JSON,僅取檢視所需欄位;結構原樣)────────────
type UeStatus = {
  ue_id: string; serving_gnb: string; serving_pci: number;
  rsrp_dbm: number; sinr_db: number; all_rsrp: Record<string, number>;
  throughput_dl_mbps: number; throughput_ul_mbps: number;
  quality: string; qos_5qi: number; mcs_dl: number; rb_width_dl: number;
};

type FullData = {
  timestamp_ms: number; compute_ms: number; tick_ms: number;
  e2: { gnb_id: string; cells: { cell_id: string; ran_name: string; pci: number; ues: any[] }[] }[];
  ue_status: UeStatus[];
  pm: Record<string, Record<string, string>[]>;
  bbu_status: Record<string, any>;
  warnings: string[];
};

type AnrData = {
  timestamp_ms: number;
  e2NodeInformation: {
    servingCells: { ncgi: string; physicalCellId: number; arfcn: number }[];
    neighbourCellRelations: {
      sourceCellNcgi: string; targetCellGlobalId: string; targetPhysicalCellId: number;
      isHoAllowed?: boolean; xnX2Established: boolean; hoValidated: boolean; version: number;
      // v10 起旗標不再上 E2(卷面第 12 題考點:旗標不可觀測),v8 才有
      flags?: { hoBlocklist: boolean; noRemove: boolean; xnBlocklist: boolean };
    }[];
    relationChangeEvents: { action: string; targetCellGlobalId: string; by: string; at: string }[];
  };
  kpmIndication: {
    cellLevel: Record<string, any>;
    perNeighbourRelation: any[];
  };
  // v8 專屬容器 —— v10 已取消(量測併入 kpmIndication.cellLevel 扁平鍵)
  rlfKpm?: {
    cellLevel: Record<string, { 'RLF.DetectedRate': number; 'RLF.DropWithoutReestablishmentRate': number; 'RRC.ConnReEstabInboundRatePerMin': number }>;
    reestablishmentInboundByPreviousPci: { cellNcgi: string; byPreviousPci: { previousPhysicalCellId: number; ratePerMin: number }[] }[];
  };
  mroKpm?: {
    cellLevel: Record<string, any>;
    total: Record<string, number>;
  };
  e2MessageCopyAggregate: {
    // v10:重建來源統計從 rlfKpm 搬到這裡
    reestablishmentInboundByPreviousPci?: { cellNcgi: string; byPreviousPci: { previousPhysicalCellId: number; ratePerMin: number }[] }[];
    measurementReportAggregate: {
      reportedPhysicalCellId: number; reportedArfcn: number; sampleRatePerMin: number;
      rsrpPercentile50Dbm: number; rsrpPercentile90Dbm: number;
      rsrpStandardDeviationDb: number; servingRsrpPercentile50Dbm: number;
    }[];
  };
};

type ControlRow = {
  seq: number; ts_ms: number;
  ranFunc: number | null; ranFuncName: string; instId: number | null;
  style: number | null; action: number | null;
  command: string; params: Record<string, string | number | boolean>;
  ueid: Record<string, unknown>;
  acked: boolean; result: string; detail: string;
  ackBytes: number | null; rttMs: number | null; failure: string;
};

async function post<T>(url: string, body: object = {}): Promise<T | null> {
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) return null;
    const j = await r.json();
    return (j?.data ?? null) as T;
  } catch {
    return null;
  }
}

// ── 小元件 ───────────────────────────────────────────────────────
function Tile({ label, value, unit, tone }: { label: string; value: string | number; unit?: string; tone?: 'good' | 'warn' | 'bad' | 'info' }) {
  const toneCls = tone === 'good' ? styles.tileGood : tone === 'warn' ? styles.tileWarn : tone === 'bad' ? styles.tileBad : styles.tileInfo;
  return (
    <div className={`${styles.tile} ${toneCls}`}>
      <div className={styles.tileLabel}>{label}</div>
      <div className={styles.tileValue}>{value}{unit && <span className={styles.tileUnit}>{unit}</span>}</div>
    </div>
  );
}

function hhmmss(ms: number): string {
  const d = new Date(ms);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** ran function 標籤 —— RC / ANR / CCC 各自配色,和 RIC 端對帳時好認 */
function FnTag({ name }: { name: string }) {
  const cls = name === 'RC' ? styles.fnRc
    : name === 'ANR' ? styles.fnAnr
    : name === 'CCC' ? styles.fnCcc
    : styles.fnMisc;
  return <span className={`${styles.fnTag} ${cls}`}>{name}</span>;
}

/** 只顯示有值的參數,避免一排空欄位 */
function Params({ p }: { p: Record<string, string | number | boolean> }) {
  const kv = Object.entries(p ?? {}).filter(([, v]) => v !== '' && v != null);
  if (kv.length === 0) return <span className={styles.dim}>—</span>;
  return (
    <>
      {kv.map(([k, v], i) => (
        <span key={k}>
          {i > 0 && <span className={styles.dim}> · </span>}
          <span className={styles.paramKey}>{k}=</span>
          <span className={styles.paramVal}>{String(v)}</span>
        </span>
      ))}
    </>
  );
}

/** 結果碼:成功綠 / 被拒琥珀(規範要求的保護行為,不是錯誤)/ 失敗紅 / 等 ACK 灰 */
function ResultPill({ row }: { row: ControlRow }) {
  if (row.failure) {
    return <span className={`${styles.pill} ${styles.resFail}`} title={row.failure}>FAILURE</span>;
  }
  if (!row.acked) {
    return <span className={`${styles.pill} ${styles.resPending}`}>等 ACK</span>;
  }
  const r = row.result;
  if (!r) return <span className={`${styles.pill} ${styles.resOk}`}>ACK</span>;
  const rejected = r.includes('REJECT') || r === 'NOT_FOUND';
  return (
    <span className={`${styles.pill} ${rejected ? styles.resRejected : styles.resOk}`}
          title={row.detail || r}>
      {r}
    </span>
  );
}

function QualityPill({ q }: { q: string }) {
  const cls = q === 'good' ? styles.pillGood : q === 'fair' ? styles.pillFair : styles.pillPoor;
  return <span className={`${styles.pill} ${cls}`}>{q}</span>;
}

function RsrpBar({ dbm }: { dbm: number }) {
  // -120(空)~ -50(滿)
  const pct = Math.max(0, Math.min(100, ((dbm + 120) / 70) * 100));
  const color = pct > 60 ? '#34d399' : pct > 30 ? '#fbbf24' : '#f87171';
  return (
    <span className={styles.barTrack}>
      <span className={styles.barFill} style={{ width: `${pct}%`, background: color }} />
    </span>
  );
}

function BoolPill({ on, onText = 'yes', offText = 'no', danger = false }: { on: boolean; onText?: string; offText?: string; danger?: boolean }) {
  const cls = on ? (danger ? styles.pillFlag : styles.pillOn) : styles.pillOff;
  return <span className={`${styles.pill} ${cls}`}>{on ? onText : offText}</span>;
}

// pm 摘要要顯示的關鍵欄(原鍵名,不改結構)
const PM_HIGHLIGHTS: [string, string][] = [
  ['cu_RRC.ConnMean', '連線數'],
  ['cu_MM.HoExeIntraSucc', 'HO 成功'],
  ['cu_RRC.ReEstabAtt', '重建'],
  ['cu_gnb.UECNTX.Release.gNBinit.sum', '掉話釋放'],
  ['cu_DRB.PdcpPacketDiscardDL.5QI9', '丟包'],
  ['cu_DRB.PdcpSduVolumeDL_5QI9', 'DL 累計 B'],
  ['du_CARR.PRBUsageDLNbr', 'PRB 累計'],
];

export default function E2Page() {
  const [full, setFull] = useState<FullData | null>(null);
  const [anr, setAnr] = useState<AnrData | null>(null);
  const [ctrl, setCtrl] = useState<ControlRow[]>([]);
  // 掉話(IDLE)的 UE 不在 FULLKPM 的 ue_status 裡 —— 那份只收 CONNECTED。
  // 只看它會讓 UE「憑空從 5 個變 3 個」,像是壞掉;其實是掉話後在選網中。
  // 這份補上執行期看得到的全部 UE 與其狀態。
  const [liveUe, setLiveUe] = useState<LiveUeSnapshot | null>(null);
  const [lastOk, setLastOk] = useState<number>(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const [f, a, c] = await Promise.all([
        post<FullData>(`${CU_BASE_URL}/api/v0.1/CU/E2/E2FullReporter/read`),
        post<AnrData>(`${CU_BASE_URL}/api/v0.1/CU/E2/Anr/indication`, { window_min: 5 }),
        post<{ commands: ControlRow[] }>(
          `${E2_ADAPTER_BASE_URL}/api/v0.1/E2Adapter/ControlAudit/ControlAuditReader/read`,
          { limit: 40 }),
      ]);
      try { const lv = await fetchLiveUePositions(); if (alive) setLiveUe(lv); }
      catch { /* UE service 拉不到就只顯示 CONNECTED,不影響其他區塊 */ }
      if (!alive) return;
      if (f) setFull(f);
      if (a) setAnr(a);
      if (c) setCtrl(c.commands ?? []);
      if (f || a) setLastOk(Date.now());
    };
    tick();
    timer.current = setInterval(tick, POLL_MS);
    return () => { alive = false; if (timer.current) clearInterval(timer.current); };
  }, []);

  const live = Date.now() - lastOk < POLL_MS * 3;
  const ues = full?.ue_status ?? [];
  const connected = ues.filter((u) => u.rsrp_dbm != null && u.rsrp_dbm > -150);
  // 掉話中的 UE:執行期看得到,但沒進 ue_status(CU 端是 IDLE)。
  // STANDBY = 我們的執行期狀態,對應 RRC_IDLE 正在選網(TS 38.304)。
  const shownIds = new Set(connected.map((u) => u.ue_id));
  const droppedUes = Object.entries(liveUe?.states ?? {})
    .filter(([id, st]) => !shownIds.has(id) && st !== 'STOPPED')
    .map(([id]) => ({
      ue_id: id,
      pos: liveUe?.positions[id],
      lastCell: liveUe?.servingCells[id] ?? '',
    }));
  const cells = full?.e2.flatMap((g) => g.cells) ?? [];
  const pmRecs = full ? Object.values(full.pm).flat() : [];
  const sumPm = (key: string) => pmRecs.reduce((s, r) => s + (parseInt(r[key] ?? '0', 10) || 0), 0);
  // ── v10 schema(2026-08-26 切換)──────────────────────────────
  // v8 的 rlfKpm / mroKpm 容器已取消,量測改為 kpmIndication.cellLevel 的
  // 扁平鍵「<指標名>.<NCGI>」+ {currentPerMin|currentPct, baseline…, trend…}。
  // 這裡重組回 per-cell 結構,讓下面的畫面邏輯不用改寫。
  const metricNum = (v: any): number =>
    typeof v === 'number' ? v : (v?.currentPerMin ?? v?.currentPct ?? v?.current ?? 0);
  const cellLevelFlat: Record<string, any> = anr?.kpmIndication?.cellLevel ?? {};
  const byCell: Record<string, Record<string, number>> = {};
  const netTotal: Record<string, number> = {};
  for (const [key, val] of Object.entries(cellLevelFlat)) {
    const i = key.lastIndexOf('.');
    if (i < 0) continue;
    const metric = key.slice(0, i);
    const cell = key.slice(i + 1);
    const n = metricNum(val);
    (byCell[cell] ??= {})[metric] = n;
    netTotal[metric] = (netTotal[metric] ?? 0) + n;
  }
  // 只留有 RLF/重建數字的 cell(v8 的 rlfKpm.cellLevel 等價物)
  const rlfCells: Record<string, Record<string, number>> = Object.fromEntries(
    Object.entries(byCell).filter(([, m]) =>
      (m['RLF.DetectedRate'] ?? 0) > 0 || (m['RRC.ConnReEstabInboundRatePerMin'] ?? 0) > 0),
  );
  const totalRlfRate = netTotal['RLF.DetectedRate'] ?? 0;
  const mroTotal: Record<string, number> = netTotal;
  const relations = anr?.e2NodeInformation?.neighbourCellRelations ?? [];
  // v10:重建來源統計搬到 e2MessageCopyAggregate 底下
  const inbound = anr?.e2MessageCopyAggregate?.reestablishmentInboundByPreviousPci
    ?? anr?.rlfKpm?.reestablishmentInboundByPreviousPci ?? [];
  const measAgg = anr?.e2MessageCopyAggregate?.measurementReportAggregate ?? [];
  const changeEvents = anr?.e2NodeInformation?.relationChangeEvents ?? [];
  const perRel = anr?.kpmIndication?.perNeighbourRelation ?? [];
  const ctrlRejected = ctrl.filter((c) => c.result.includes('REJECT')).length;
  const ctrlFailed = ctrl.filter((c) => c.failure || (!c.acked && Date.now() - c.ts_ms > 5000)).length;

  return (
    <main className={styles.page}>
      <div className={styles.pageHead}>
        <h2>
          <span className={`${styles.liveDot} ${live ? '' : styles.stale}`} />
          E2 Data Explorer
        </h2>
        <span className={styles.sub}>
          FULLKPM(func 5)+ ANR(func 6)— RIC 端 xApp 訂閱收到的完整內容,每 {POLL_MS / 1000}s 更新
          {full && <> · compute {full.compute_ms}ms · tick {full.tick_ms}ms</>}
        </span>
      </div>

      {/* ── 總覽 tiles ── */}
      <div className={styles.tiles}>
        <Tile label="CONNECTED UE" value={connected.length}
              unit={droppedUes.length ? `+${droppedUes.length} 掉話` : ''}
              tone={droppedUes.length ? 'warn' : 'info'} />
        <Tile label="Cells" value={cells.length} tone="info" />
        <Tile label="HO 成功(累計)" value={sumPm('cu_MM.HoExeIntraSucc')} tone="good" />
        <Tile label="RLF 掉線率" value={totalRlfRate.toFixed(2)} unit="/min" tone={totalRlfRate > 0.5 ? 'bad' : totalRlfRate > 0 ? 'warn' : 'good'} />
        <Tile label="重建(累計)" value={sumPm('cu_RRC.ReEstabAtt')} tone="warn" />
        <Tile label="丟包(累計)" value={sumPm('cu_DRB.PdcpPacketDiscardDL.5QI9')} tone={sumPm('cu_DRB.PdcpPacketDiscardDL.5QI9') > 0 ? 'bad' : 'good'} />
        <Tile label="NRT 關係" value={relations.length} tone="info" />
        <Tile label="下發命令" value={ctrl.length} unit={ctrlRejected ? `含 ${ctrlRejected} 拒` : ''}
              tone={ctrlFailed ? 'bad' : ctrlRejected ? 'warn' : ctrl.length ? 'good' : 'info'} />
      </div>

      {!full && !anr && <div className={styles.error}>CU 連線中…(確認 sim 是否啟動、CU {CU_BASE_URL} 是否可達)</div>}
      {full && full.warnings.length > 0 && (
        <div className={styles.error}>warnings: {full.warnings.join(' / ')}</div>
      )}

      {/* ══ 下行:xApp 下發的 RIC Control ══ */}
      <section className={`${styles.section} ${styles.downlink}`}>
        <div className={styles.sectionHead}>
          <h3>
            下發命令 <span className={styles.dirTag}>RIC → sim · downlink</span>
          </h3>
          <span className={`${styles.badge} ${styles.badgeAmber}`}>
            adapter · RC + CCC + ANR · 最近 {ctrl.length} 筆
          </span>
        </div>
        {ctrl.length === 0 ? (
          <div className={styles.empty}>
            尚無下發命令(adapter 重啟後會清空 —— 這是記憶體環狀緩衝,不是持久化紀錄)
          </div>
        ) : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead><tr>
                <th>時間</th><th>func</th><th className={styles.num}>instId</th>
                <th>命令</th><th>參數</th><th>結果</th>
                <th className={styles.num}>ACK</th><th className={styles.num}>rtt</th>
              </tr></thead>
              <tbody>
                {ctrl.map((c) => (
                  <tr key={c.seq}>
                    <td className={styles.mono}>{hhmmss(c.ts_ms)}</td>
                    <td><FnTag name={c.ranFuncName} />
                      {c.style != null && c.style > 0 && (
                        <span className={styles.dim}> {c.style}/{c.action}</span>)}
                    </td>
                    <td className={`${styles.num} ${styles.mono}`}>{c.instId ?? '—'}</td>
                    <td className={styles.mono}>{c.command || '—'}</td>
                    <td className={styles.paramCell} title={JSON.stringify(c.params)}>
                      <Params p={c.params} />
                    </td>
                    <td><ResultPill row={c} /></td>
                    <td className={`${styles.num} ${styles.mono}`}>{c.ackBytes ?? '—'}</td>
                    <td className={`${styles.num} ${styles.mono}`}>
                      {c.rttMs == null ? '—' : `${c.rttMs}ms`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className={styles.footNote}>
          instId 可直接與 RIC 端 xApp 日誌對帳。結果碼取自 ACK 的 RICcontrolOutcome(IE id=32)
          —— <b>被拒(REJECTED)不是錯誤</b>,是規範要求的保護行為(如 noRemove 條目、
          NRT 容量已滿、ANR 功能停用),真正的異常是 failure 或遲遲沒有 ACK。
        </div>
      </section>

      {/* ══ FULLKPM(func 5)══ */}
      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h3>UE 即時量測</h3>
          <span className={`${styles.badge} ${styles.badgeBlue}`}>FULLKPM · func 5 · ue_status[]</span>
        </div>
        {connected.length === 0 && droppedUes.length === 0 ? (
          <div className={styles.empty}>無 UE(sim 未跑或量測未就緒)</div>
        ) : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead><tr>
                <th>UE</th><th>Serving(PCI)</th><th>RSRP</th><th className={styles.num}>SINR</th>
                <th className={styles.num}>DL / UL Mbps</th><th className={styles.num}>MCS</th>
                <th className={styles.num}>PRB</th><th>Quality</th><th className={styles.num}>5QI</th>
              </tr></thead>
              <tbody>
                {connected.map((u) => (
                  <tr key={u.ue_id}>
                    <td className={styles.mono}>{u.ue_id}</td>
                    <td>{u.serving_gnb} <span className={styles.dim}>({u.serving_pci})</span></td>
                    <td><RsrpBar dbm={u.rsrp_dbm} /><span className={styles.mono}>{u.rsrp_dbm.toFixed(1)}</span></td>
                    <td className={`${styles.num} ${styles.mono}`}>{u.sinr_db.toFixed(1)}</td>
                    <td className={`${styles.num} ${styles.mono}`}>{u.throughput_dl_mbps} / {u.throughput_ul_mbps}</td>
                    <td className={`${styles.num} ${styles.mono}`}>{u.mcs_dl}</td>
                    <td className={`${styles.num} ${styles.mono}`}>{u.rb_width_dl}</td>
                    <td><QualityPill q={u.quality} /></td>
                    <td className={`${styles.num} ${styles.mono}`}>{u.qos_5qi}</td>
                  </tr>
                ))}
                {/* 掉話中的 UE —— 灰列。它們沒有 CONNECTED 態的量測,欄位以「—」表示
                    「這一刻沒有這個值」,而不是 0(0 會被誤讀成量到了但很差)。 */}
                {droppedUes.map((u) => (
                  <tr key={u.ue_id} className={styles.dimRow}>
                    <td className={styles.mono}>{u.ue_id}</td>
                    <td>
                      <span className={`${styles.pill} ${styles.pillIdle}`}>IDLE 選網中</span>
                      {u.lastCell && <span className={styles.dim}> 前 {u.lastCell}</span>}
                    </td>
                    <td className={styles.dim}>—</td>
                    <td className={`${styles.num} ${styles.dim}`}>—</td>
                    <td className={`${styles.num} ${styles.dim}`}>—</td>
                    <td className={`${styles.num} ${styles.dim}`}>—</td>
                    <td className={`${styles.num} ${styles.dim}`}>—</td>
                    <td className={styles.dim}>
                      {u.pos ? `(${u.pos[0].toFixed(0)}, ${u.pos[2].toFixed(0)})` : '—'}
                    </td>
                    <td className={`${styles.num} ${styles.dim}`}>—</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {droppedUes.length > 0 && (
          <div className={styles.footNote}>
            掉話的 UE 仍留在模擬中:位置照走、每 5 秒自行量 SSB 選網(TS 38.304),
            訊號回到門檻以上就自己發起 RRCSetupRequest 重新連線。
            它們不在 FULLKPM 的 <code>ue_status</code> 裡(那份只收 CONNECTED),
            此處由 UE service 的執行期狀態補上 —— 否則 UE 會像憑空消失。
          </div>
        )}
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h3>Per-cell PM 摘要(190 欄取關鍵)</h3>
          <span className={`${styles.badge} ${styles.badgeBlue}`}>FULLKPM · func 5 · pm{'{}'}</span>
        </div>
        {pmRecs.length === 0 ? <div className={styles.empty}>無 pm 資料</div> : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead><tr>
                <th>Cell</th>
                {PM_HIGHLIGHTS.map(([k, label]) => <th key={k} className={styles.num} title={k}>{label}</th>)}
              </tr></thead>
              <tbody>
                {Object.entries(full?.pm ?? {}).flatMap(([gnb, recs]) =>
                  recs.map((r, i) => (
                    <tr key={`${gnb}-${i}`}>
                      <td className={styles.mono}>{gnb.replace('gnb-', '')} <span className={styles.dim}>/ {r['cell_id']?.slice(0, 12)}</span></td>
                      {PM_HIGHLIGHTS.map(([k]) => (
                        <td key={k} className={`${styles.num} ${styles.mono}`} title={k}>{r[k] ?? '0'}</td>
                      ))}
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        )}
        <div className={styles.footNote}>完整 190 欄結構不變 — 此處僅為檢視摘要;逐欄語意見 docs/kpm_field_notes*.md</div>
      </section>

      {/* ══ ANR(func 6)══ */}
      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h3>NRT 鄰區關係表(§9.3.38)</h3>
          <span className={`${styles.badge} ${styles.badgeTeal}`}>ANR · func 6 · e2NodeInformation</span>
        </div>
        {relations.length === 0 ? <div className={styles.empty}>NRT 為空(缺漏鄰區?xApp 可下 ANR ADD)</div> : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead><tr>
                <th>Source</th><th>Target(PCI)</th><th className={styles.num}>ver</th>
                <th>HO 允許</th><th>Xn 已建</th><th>HO 驗證</th><th>Flags</th>
              </tr></thead>
              <tbody>
                {relations.map((r, i) => (
                  <tr key={i}>
                    <td className={styles.mono}>{r.sourceCellNcgi}</td>
                    <td className={styles.mono}>{r.targetCellGlobalId} <span className={styles.dim}>({r.targetPhysicalCellId})</span></td>
                    <td className={`${styles.num} ${styles.mono}`}>{r.version}</td>
                    <td><BoolPill on={r.isHoAllowed ?? true} /></td>
                    <td><BoolPill on={r.xnX2Established} /></td>
                    <td><BoolPill on={r.hoValidated} /></td>
                    <td>
                      {r.flags?.hoBlocklist && <BoolPill on danger onText="hoBlock" />}{' '}
                      {r.flags?.noRemove && <BoolPill on danger onText="noRemove" />}{' '}
                      {r.flags?.xnBlocklist && <BoolPill on danger onText="xnBlock" />}
                      {!r.flags && <span className={styles.dim} title="v10 起旗標不上 E2(卷面第 12 題:旗標不可觀測)">v10 不可觀測</span>}
                      {r.flags && !r.flags.hoBlocklist && !r.flags.noRemove && !r.flags.xnBlocklist && <span className={styles.dim}>—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {changeEvents.length > 0 && (
          <div className={styles.footNote}>
            最近變更:{changeEvents.slice(0, 3).map((e) => `${e.action} ${e.targetCellGlobalId}(${e.by})`).join(' · ')}
          </div>
        )}
      </section>

      <div className={styles.cols2}>
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <h3>RLF / 重建</h3>
            <span className={`${styles.badge} ${styles.badgeTeal}`}>ANR · func 6 · kpmIndication.cellLevel</span>
          </div>
          {Object.keys(rlfCells).length === 0 ? <div className={styles.empty}>窗口內無 RLF 事件</div> : (
            Object.entries(rlfCells).map(([cell, v]) => (
              <div className={styles.miniCard} key={cell} style={{ marginBottom: 8 }}>
                <h4>{cell}</h4>
                <div className={styles.kvRow}><span>RLF 掉線率</span><b>{v['RLF.DetectedRate']}/min</b></div>
                <div className={styles.kvRow}><span>掉話(無處重建)</span><b>{v['RLF.DropWithoutReestablishmentRate']}/min</b></div>
                <div className={styles.kvRow}><span>重建 inbound</span><b>{v['RRC.ConnReEstabInboundRatePerMin']}/min</b></div>
              </div>
            ))
          )}
          {inbound.length > 0 && (
            <div className={styles.miniCard}>
              <h4>重建來源(inbound by previous PCI)— 缺漏鄰區證據</h4>
              {inbound.map((c) => (
                <div className={styles.kvRow} key={c.cellNcgi}>
                  <span className={styles.mono}>{c.cellNcgi}</span>
                  <b>{c.byPreviousPci.map((p) => `←PCI${p.previousPhysicalCellId} ${p.ratePerMin}/min`).join('  ')}</b>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <h3>MRO 換手病態歸因</h3>
            <span className={`${styles.badge} ${styles.badgeTeal}`}>ANR · func 6 · kpmIndication.cellLevel</span>
          </div>
          <div className={styles.miniCard}>
            <h4>全網(window 5 min)</h4>
            <div className={styles.kvRow}><span>過早換手 TooEarly</span><b>{mroTotal['HO.IntraSys.TooEarlyRate'] ?? 0}/min</b></div>
            <div className={styles.kvRow}><span>過晚換手 TooLate</span><b>{mroTotal['HO.IntraSys.TooLateRate'] ?? 0}/min</b></div>
            <div className={styles.kvRow}><span>換錯 cell ToWrongCell</span><b>{mroTotal['HO.IntraSys.ToWrongCellRate'] ?? 0}/min</b></div>
          </div>
          {perRel.length > 0 && (
            <div className={styles.miniCard} style={{ marginTop: 8 }}>
              <h4>每鄰區關係 HO(kpmIndication.perNeighbourRelation)</h4>
              {perRel.slice(0, 6).map((r: any, i: number) => (
                <div className={styles.kvRow} key={i}>
                  <span className={styles.mono}>{r.sourceCellNcgi}→{r.targetCellGlobalId}</span>
                  <b>{r['MM.HoExeAttRatePerMin']}/min · succ {r['MM.HoExeSuccRatio_last50'] ?? '—'}</b>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h3>量測聚合(依 reported PCI)</h3>
          <span className={`${styles.badge} ${styles.badgeTeal}`}>ANR · func 6 · e2MessageCopyAggregate</span>
        </div>
        {measAgg.length === 0 ? <div className={styles.empty}>窗口內無量測樣本</div> : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead><tr>
                <th className={styles.num}>PCI</th><th className={styles.num}>ARFCN</th>
                <th className={styles.num}>樣本率 /min</th><th className={styles.num}>RSRP P50</th>
                <th className={styles.num}>RSRP P90</th><th className={styles.num}>σ (dB)</th>
                <th className={styles.num}>同報 serving P50</th>
              </tr></thead>
              <tbody>
                {measAgg.map((m) => (
                  <tr key={m.reportedPhysicalCellId}>
                    <td className={`${styles.num} ${styles.mono}`}>{m.reportedPhysicalCellId}</td>
                    <td className={`${styles.num} ${styles.mono}`}>{m.reportedArfcn}</td>
                    <td className={`${styles.num} ${styles.mono}`}>{m.sampleRatePerMin}</td>
                    <td className={`${styles.num} ${styles.mono}`}>{m.rsrpPercentile50Dbm}</td>
                    <td className={`${styles.num} ${styles.mono}`}>{m.rsrpPercentile90Dbm}</td>
                    <td className={`${styles.num} ${styles.mono}`}>{m.rsrpStandardDeviationDb}</td>
                    <td className={`${styles.num} ${styles.mono}`}>{m.servingRsrpPercentile50Dbm}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className={styles.footNote}>
        資料結構原樣呈現(不改後端 schema);wire 上 func 5/6 為同內容之 JSON+zlib。取用文件:docs/api/e2sm_fullkpm.md · e2sm_anr.md
      </div>
    </main>
  );
}
