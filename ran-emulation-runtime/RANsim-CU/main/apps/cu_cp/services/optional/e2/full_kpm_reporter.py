"""FullKpmReporter — 完整版 E2 KPM snapshot,欄位架構 1:1 對齊 docs/E2_data_example.md。

輸出 top-level keys:timestamp_ms / compute_ms / tick_ms / e2 / ue_status / pm /
bbu_status / warnings。量測得到的欄位給真值,量不到且推不出來的一律 "0"
(pm 區值型別跟範例一樣全部是字串)。

資料源:
  - CU DB:UeContext / MeasurementLog(含 neighbor rsrp+rsrq)/ CellConfig /
    HandoverEvent / CellMeasurementLog
  - DU dump_pm(HTTP):per-cell MCS 32-bin / CQI 16-bin / PRB 累計 / PDCP bytes
    per-5QI / wall_tick_ms
  - BbuTelemetryService:host psutil/pynvml(per-gNB 分攤 → proxy 值)

RSRQ:3GPP 真實版(2026-08-07 升級,見 _derive_rsrq)—— RSRQ = RSRP/RSSI,
RSSI = 12·Σ(P_cell×activity) + noise,activity 含 per-cell PRB 負載(負載感知)。
legacy 公式(10log10(P/ΣP)−10.8)已棄用;新公式在「全滿載+忽略雜訊」極限下
收斂回 legacy 值(差 <1dB),語意連續。
"""
from __future__ import annotations

import math
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import requests

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.cell_measurement_log import CellMeasurementLog
from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.measurement_log import MeasurementLog
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.services.optional.e2.bbu_telemetry import BbuTelemetryService
from main.utils.env_loader import get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)

_HTTP_TIMEOUT = 3.0
MCS_BINS = 32
CQI_BINS = 16

# interfered 判定:任一鄰區 RSRP 進到 serving 10 dB 以內 → 視為受干擾
_INTERFERED_GAP_DB = 10.0

# RRC.ConnMax 追蹤(process 存活期間的高水位;restart 歸零)
_conn_max_seen: dict[str, int] = defaultdict(int)


# ── 小工具 ─────────────────────────────────────────────────────────


def _env_float(name: str, default: float) -> float:
    """功耗模型常數 —— 實機校準時用環境變數覆寫,不必改碼。壞值就用預設。"""
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def _lin(dbm: float) -> float:
    return 10.0 ** (dbm / 10.0)


# 3GPP 真實版 RSRQ(2026-08-07 升級,取代 legacy 10log10(P/ΣP)−10.8):
#   RSRQ = N·RSRP/RSSI,RSSI 為量測頻寬全能量 = 各 cell 能量×活動係數 + 熱雜訊。
#   activity = α_ref + (1−α_ref)·load —— 空閒 cell 只發參考訊號/控制(α_ref=1/6,
#   對齊 3GPP「idle cell RSRQ ≈ −3dB、滿載 ≈ −10.8dB」兩個錨點),load 取該 cell
#   PrbTot%(DU 真實排程負載)→ RSRQ 具負載感知:鄰站閒時 RSRQ 變好。
#   雜訊用 RU_NOISE_FLOOR_DBM(與 SINR 計算同一尺度,預設 −98)。
_RSRQ_ALPHA_REF = 1.0 / 6.0
_NOISE_FLOOR_DBM = float(get_str("RU_NOISE_FLOOR_DBM", "-98") or "-98")


def _derive_rsrq(target_dbm: float, cells_dbm_load: list[tuple[float, float]]) -> int:
    """3GPP 版:target 對「12×Σ(P_c×activity_c)+noise」的比值(dB),四捨五入取整。

    cells_dbm_load: [(rsrp_dbm, load_0_1), ...] — 該 UE 量得到的所有 cell(含 serving)。
    """
    rssi = sum(
        12.0 * _lin(p) * (_RSRQ_ALPHA_REF + (1.0 - _RSRQ_ALPHA_REF) * max(0.0, min(1.0, ld)))
        for p, ld in cells_dbm_load
    ) + _lin(_NOISE_FLOOR_DBM)
    ratio = _lin(target_dbm) / max(rssi, 1e-30)
    rsrq = 10.0 * math.log10(max(ratio, 1e-30))
    return int(round(max(-43.0, min(20.0, rsrq))))  # clamp 到 3GPP SS-RSRQ 值域


def _quality(sinr_db: float) -> str:
    if sinr_db >= 10.0:
        return "good"
    if sinr_db >= 0.0:
        return "fair"
    return "poor"


def _arfcn_of(cfg: CellConfig) -> int | None:
    """cell → NR-ARFCN。CellConfig 只存 frequency_ghz,依 TS 38.104 §5.4.2.1 換算
    (3.5 GHz → 633333,與 registry 設定一致)。"""
    try:
        from ran_sim_protocol.nr_frequency import nr_arfcn_from_ghz
        return nr_arfcn_from_ghz(getattr(cfg, "frequency_ghz", None))
    except Exception:  # noqa: BLE001 — 換算不出來就回 None,不猜
        return None


# 2026-09-23:鄰區量測的鍵。"cell" = 現況(以 cell 身分為鍵,上帝視角);
# "pci" = 真實 UE 量得到的程度 —— 每筆 {pci, arfcn, rsrp, rsrq},只有 CU 的鄰區表(NRT)
# 已解出該 PCI@ARFCN 對應的 cell 時才附 ncgi;PCI 混淆(同鍵對到多顆)時合併成一筆且不附。
# 預設維持 "cell",與 RIC 約好窗口再切(提案見 docs/agent_need/給RIC的提案_2026-09-22_*)。
_NEIGHBOR_KEY = os.environ.get("E2_NEIGHBOR_KEY", "cell").strip().lower()


def _dbm_sum(values: list[float]) -> float:
    """多筆 RSRP 以功率相加(混淆的兩顆 cell 同 PCI 同頻,UE 量到的是疊加後的訊號)。"""
    mw = sum(10.0 ** (v / 10.0) for v in values)
    return 10.0 * math.log10(mw) if mw > 0 else -140.0


def _nrt_resolver(cells: list[CellConfig]):
    """回 resolve(serving_cell_id, pci, arfcn) → ncgi | None。

    「解得出」= NRT 裡 serving cell 對該 (pci, arfcn) **恰好一個**目標,且目標是已知 cell。
    零筆 = 缺漏鄰區(gNB 不知道這 PCI 是誰);兩筆以上 = PCI 混淆。兩者都回 None ——
    這正是真實 gNB 知道的程度,也是 Agent 要出的兩類題。
    """
    from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
    by_id = {c.cell_id: c for c in cells}
    table: dict[tuple[str, int, int | None], set[str]] = {}
    try:
        for r in NrCellRelation.objects.values_list("source_cell_id", "target_cgi", "target_pci", "target_arfcn"):
            src, tgt, pci, arfcn = r
            key = (str(src), int(pci or 0), int(arfcn) if arfcn else None)
            table.setdefault(key, set()).add(str(tgt))
    except Exception:  # noqa: BLE001 — NRT 讀不到就全部視為未解出,不要猜
        table = {}

    def resolve(serving: str, pci: int, arfcn: int | None) -> str | None:
        targets = table.get((serving, int(pci), arfcn)) or table.get((serving, int(pci), None)) or set()
        if len(targets) != 1:
            return None
        cfg = by_id.get(next(iter(targets)))
        return _ncgi_of(cfg) if cfg is not None else None
    return resolve


def _ncgi_of(cfg: CellConfig) -> str:
    """NCGI 字串,格式與 Agent 介面 I-2 的 `ncgi` 相同:`<mcc><mnc 3 位>-<36-bit NCI 9 hex>`。
    NCI 走與 E2 Setup / KPM 同一套 explicit-first / SHA-1(cell_id_map.to_nr_cellid),
    所以 RIC 從 nodeConfigs 解出的 NCI 直接對得上。"""
    from main.apps.cu_cp.services.common.cell_id_map import to_nr_cellid
    plmn = str(cfg.served_plmn or "00101")
    mcc, mnc = plmn[:3], plmn[3:].zfill(3)
    nci = int(to_nr_cellid(cfg.cell_id, explicit=getattr(cfg, "nr_cellid", None))) & ((1 << 36) - 1)
    return f"{mcc}{mnc}-{nci:09x}"


def _cell_hex_id(cfg: CellConfig) -> str:
    """範例 cell_id 是 36-bit NCI hex(15 位)。有 nr_cellid 用 hex,否則退回字串 id。"""
    if cfg.nr_cellid:
        return f"{int(cfg.nr_cellid):015x}"
    return cfg.cell_id


def _fetch_du_dump_pm() -> dict[str, Any]:
    host = get_str("HTTP_DU_HOST")
    if not host:
        return {}
    port = get_str("HTTP_DU_PORT", "8000")
    try:
        r = requests.post(
            f"http://{host}:{port}/api/v0.1/DU/Tick/TickController/dump_pm",
            json={}, timeout=_HTTP_TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("data", {}) or {}
    except requests.RequestException as exc:
        logger.warning("dump_pm fetch failed: %s", exc)
        return {}


# ── pm 區:190 欄模板 ───────────────────────────────────────────────


def _beam_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """每波束量測(O-RAN WG1 §4.6.4.1)。

    rows = 這個 cell 目前 CONNECTED 的 UE 快照。對每個 GoB 波束回:
      served_ues    以它為服務波束的 UE 數
      rsrp_dbm_avg  這些 UE 的平均 RSRP(服務波束才有意義)
      sinr_db_avg   平均 SINR
      dl_mbps       下行吞吐合計
      prb_dl        下行 PRB 合計
      measured_ues  有量到這道波束的 UE 數(含非服務波束;來自 RU 的 beam_rsrp_top)
      rel_dbm_avg   這些 UE 量到的「相對各自最佳波束」平均 dB(≤ 0;越接近 0 表示這道波束對他們越好)
    沒有 GoB(beam_id 都是 None)→ 回空 list。
    """
    serving: dict[int, list[dict[str, Any]]] = defaultdict(list)
    measured: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        m = r["meas"]
        if getattr(m, "beam_id", None) is not None:
            serving[int(m.beam_id)].append(r)
        for item in (getattr(m, "beam_rsrp_top_json", None) or []):
            try:
                b, rel = int(item[0]), float(item[1])
            except (TypeError, ValueError, IndexError):
                continue
            measured[b].append(rel)
    out = []
    for b in sorted(set(serving) | set(measured)):
        srv = serving.get(b, [])
        rel = measured.get(b, [])
        rec: dict[str, Any] = {"beam_id": b, "served_ues": len(srv), "measured_ues": len(rel)}
        # 無量測樣本的列(rsrp/sinr 為 None)不進平均 —— 混進去會把平均拉向 0
        _srv_m = [r for r in srv if r["meas"].rsrp_dbm is not None and r["meas"].sinr_db is not None]
        if _srv_m:
            rec["rsrp_dbm_avg"] = round(sum(float(r["meas"].rsrp_dbm) for r in _srv_m) / len(_srv_m), 1)
            rec["sinr_db_avg"] = round(sum(float(r["meas"].sinr_db) for r in _srv_m) / len(_srv_m), 1)
        if srv:
            rec["dl_mbps"] = round(sum(float(r["meas"].throughput_dl_mbps) for r in srv), 2)
            rec["prb_dl"] = int(sum(int(r["meas"].rb_width_dl or 0) for r in srv))
        if rel:
            rec["rel_dbm_avg"] = round(sum(rel) / len(rel), 1)
        out.append(rec)
    return out

def _pm_record(
    cfg: CellConfig,
    *,
    now: datetime,
    conn_cnt: int,
    conn_max: int,
    ho: dict[str, int],
    du_acc: dict[str, Any],
    prb_avail: int = 0,
    du_tick_now: int = 0,
    cell_ue_rows: list[dict] | None = None,
    prb_log: CellMeasurementLog | None,
    cell_delay_ms: float,
    cpu_temp: float,
    rlf: dict[str, int] | None = None,
    session_time_sec: int = 0,
    estab: tuple[int, int] = (0, 0),
    cell_delay_q1_ms: float = 0.0,
    conn_mean: float | None = None,
    sim_dt_ms: int = 0,
) -> dict[str, str]:
    """單一 cell 的 pm dict — 鍵名/順序/值型別(字串)完全對齊範例。"""
    ts_start = now.strftime("%Y%m%d.%H%M%z")
    ts_end = now.strftime("%H%M%z")
    gid = cfg.gnb_id or "unknown"

    # 2026-08-12 轉真:RrcEstabCounter 事件真累計(SETUP_REQUEST=Att / SETUP_COMPLETE=Succ,
    # 只加不減,HO 不影響)。取代舊「現值代理」。
    est_att, est_succ = str(int(estab[0])), str(int(estab[1]))
    attach = est_succ   # 下游 UECNTX/SM/DRB.Estab 同源(每成功 attach 建 1 session/DRB)

    def _bucket(direction: str, qi: int) -> str:
        d = du_acc.get(f"pdcp_bytes_{direction}", {}) or {}
        return str(int(d.get(str(qi), d.get(qi, 0))))

    pdcp_dl, pdcp_ul = _bucket("dl", 9), _bucket("ul", 9)
    # P0-6(2026-08-11):5QI1/4 分桶轉真 — DU per-5QI 帳本本來就有,照桶讀
    q1_dl, q1_ul = _bucket("dl", 1), _bucket("ul", 1)
    q4_dl, q4_ul = _bucket("dl", 4), _bucket("ul", 4)

    # P1-3 補(2026-08-12):釋放/Reconfig/SessionTime 轉真 —— 全部由真實事件推導。
    #   gNB 發起釋放 = RLF 掉話(RlfEvent DROP,無線原因);核網(5GCinit)發起釋放
    #   平台無此流程 → 誠實維持 0。ConnReConfig = HO 執行鏡像(每次換手隱含一次 reconfig)。
    drop_n = int((rlf or {}).get("drop", 0))       # 本 cell RLF 掉話數(真事件)
    ho_req = int((ho or {}).get("exe_req", 0))
    ho_succ = int((ho or {}).get("exe_succ", 0))
    drop_s = str(drop_n)
    st_s = str(int(session_time_sec))

    rec: dict[str, str] = {
        "cell_id": _cell_hex_id(cfg),
        "cu_timestamp_start": ts_start,
        "cu_timestamp_end": ts_end,
        "cu_filename": f"A{ts_start}-{ts_end}_{gid}-cu.xml",
        "du_timestamp_start": ts_start,
        "du_timestamp_end": ts_end,
        "du_filename": f"A{ts_start}-{ts_end}_{gid}-du.xml",
        "cu_CU_Capability": "1",
        # RRC 連線建立(代理:目前 CONNECTED 數;皆為 mo-Data)
        "cu_RRC.ConnEstabAtt.sum": est_att,
        "cu_RRC.ConnEstabAtt.mo-Data": est_att,
        "cu_RRC.ConnEstabAtt.mo-Signalling": "0",
        "cu_RRC.ConnEstabSucc.sum": attach,
        "cu_RRC.ConnEstabSucc.mo-Data": attach,
        "cu_RRC.ConnEstabSucc.mo-Signalling": "0",
        "cu_RRC.ConnEstabSucc.emergency": "0",
        "cu_RRC.ConnMax": str(conn_max),
        "cu_RRC.ConnMean": str(int(round(conn_mean if conn_mean is not None else conn_cnt))),  # C:取樣真平均
        # ReEstab — P1-3(2026-08-12)轉真:RlfEvent 依 source_cell 聚合
        "cu_RRC.ConnReEstabSetup.sum": str((rlf or {}).get("reestab_att", 0)),
        "cu_RRC.ReEstabAtt": str((rlf or {}).get("reestab_att", 0)),
        "cu_RRC.ReEstabAtt.otherFailure": str((rlf or {}).get("drop", 0)),
        "cu_RRC.ReEstabSuccWithUeContext.sum": str((rlf or {}).get("reestab_with", 0)),
        "cu_RRC.ReEstabSuccWithUeContext.otherFailure": "0",
        "cu_RRC.ReEstabSuccWithoutUeContext.sum": str((rlf or {}).get("reestab_without", 0)),
        "cu_RRC.ReEstabSuccWithoutUeContext.otherFailure": "0",
        # HO — 真值(HandoverEvent;全部 intra-freq)
        "cu_MM.HoExeIntraFreqReq": str(ho.get("exe_req", 0)),
        "cu_MM.HoExeIntraFreqSucc": str(ho.get("exe_succ", 0)),
        "cu_MM.HoExeIntraReq": str(ho.get("exe_req", 0)),
        "cu_MM.HoExeIntraSucc": str(ho.get("exe_succ", 0)),
        "cu_MM.HoPrepIntraReq": str(ho.get("prep_req", 0)),
        "cu_MM.HoPrepIntraSucc": str(ho.get("prep_succ", 0)),
        "cu_gnb.MR.Event.A3": str(ho.get("a3", 0)),
        # UECNTX — 與 RRC ConnEstab 同源
        "cu_UECNTX.ConnEstabAtt.sum": est_att,
        "cu_UECNTX.ConnEstabAtt.mo-Data": est_att,
        "cu_UECNTX.ConnEstabAtt.mo-Signalling": "0",
        "cu_UECNTX.ConnEstabSucc.sum": attach,
        "cu_UECNTX.ConnEstabSucc.mo-Data": attach,
        "cu_UECNTX.ConnEstabSucc.mo-Signalling": "0",
        "cu_UECNTX.Release.5GCinit.NASCause": "0",  # 核網發起釋放:平台無此流程,誠實 0
        "cu_UECNTX.Release.5GCinit.RNCause": "0",
        "cu_UECNTX.Release.5GCinit.sum": "0",
        "cu_gnb.UECNTX.Release.gNBinit.RNCause": drop_s,  # gNB 發起釋放=RLF 掉話(無線原因)
        "cu_gnb.UECNTX.Release.gNBinit.sum": drop_s,
        # PDU session / DRB:一 UE 一 session(5QI9)
        "cu_SM.PDUSessionSetupReq": attach,
        "cu_SM.PDUSessionSetupSucc": attach,
        "cu_gnb.SM.PDUSessionRelease.Att": drop_s,  # 每掉話 UE 一 session
        "cu_gnb.SM.PDUSessionRelease.Succ": drop_s,
        "cu_DRB.EstabAtt.5QI.sum": attach,
        "cu_DRB.EstabAtt.5QI9": attach,
        "cu_DRB.EstabSucc.5QI.sum": attach,
        "cu_DRB.EstabSucc.5QI9": attach,
        "cu_DRB.InitialEstabAtt.5QI.sum": attach,
        "cu_DRB.InitialEstabAtt.5QI1": "0",
        "cu_DRB.InitialEstabSucc.5QI.sum": attach,
        "cu_DRB.InitialEstabSucc.5QI9": attach,
        # P0-1(2026-08-11)轉真:DU per-cell RLC tx-cap drop 累計(對齊 OAI sdu_rejected)
        "cu_DRB.PdcpPacketDiscardDL.5QI9": str(int(du_acc.get("rlc_drop_sdus", 0))),
        "cu_DRB.PdcpReordDelayUl": "0",
        "cu_DRB.RelActNbr.5QI.sum": drop_s,  # 釋放時仍活躍的 DRB=掉話(掉話 UE 本在傳輸)
        "cu_DRB.RelActNbr.5QI9": drop_s,
        "cu_DRB.SessionTime.5QI.sum": st_s,  # Σ(now−created_at) 秒
        "cu_DRB.SessionTime.5QI9": st_s,
        # PDCP/SDAP volume — 真值(DU 累計 bytes,5QI 分桶)
        "cu_DRB.PdcpSduVolumeDL_5QI1": q1_dl,
        "cu_DRB.PdcpSduVolumeUl_5QI1": q1_ul,
        "cu_gnb.DRB.SdapSduVolumeDL.5QI1": q1_dl,
        "cu_gnb.DRB.SdapSduVolumeUl.5QI1": q1_ul,
        "cu_DRB.PdcpSduVolumeDL_5QI4": q4_dl,
        "cu_DRB.PdcpSduVolumeUl_5QI4": q4_ul,
        "cu_gnb.DRB.SdapSduVolumeDL.5QI4": q4_dl,
        "cu_gnb.DRB.SdapSduVolumeUl.5QI4": q4_ul,
        "cu_DRB.PdcpSduVolumeDL_5QI9": pdcp_dl,
        "cu_DRB.PdcpSduVolumeUl_5QI9": pdcp_ul,
        "cu_gnb.DRB.SdapSduVolumeDL.5QI9": pdcp_dl,
        "cu_gnb.DRB.SdapSduVolumeUl.5QI9": pdcp_ul,
        # QoS flow / SigTime — 模擬器無此流程 → 0
        "cu_QF.EstabAttNbr.5QI.sum": "0",
        "cu_QF.EstabAttNbr.5QI9": "0",
        "cu_QF.EstabSuccNbr.5QI.sum": "0",
        "cu_QF.EstabSuccNbr.5QI9": "0",
        "cu_QF.InitialEstabAttNbr.5QI.sum": "0",
        "cu_QF.InitialEstabAttNbr.5QI9": "0",
        "cu_QF.InitialEstabSuccNbr.5QI.sum": "0",
        "cu_QF.InitialEstabSuccNbr.5QI9": "0",
        "cu_QF.RelActNbr.Qos.sum": "0",
        "cu_QF.RelActNbr.Qos9": "0",
        "cu_QF.ReleaseAttNbr.5QI.sum": "0",
        "cu_QF.ReleaseAttNbr.5QI9": "0",
        "cu_gnb.RRC.ConnEstabSetup.emergency": "0",
        "cu_gnb.RRC.ConnEstabSetup.mo-Data": "0",
        "cu_gnb.RRC.ConnEstabSetup.mo-Signalling": "0",
        "cu_gnb.RRC.ConnEstabSetup.sum": attach,
        "cu_gnb.RRC.ConnReConfigAtt": str(ho_req),  # HO 執行=Reconfig(短期為 HO 鏡像)
        "cu_gnb.RRC.ConnReConfigSucc": str(ho_succ),
        "cu_gnb.RRC.ConnReEstab.ReEstab.otherFailure": "0",
        "cu_gnb.RRC.ConnReEstab.ReEstab.sum": "0",
        "cu_gnb.RRC.ConnReEstabSetup.otherFailure": "0",
        "cu_gnb.RRC.ConnRelease.Other": "0",  # 非無線原因釋放:無,全歸 sum
        "cu_gnb.RRC.ConnRelease.sum": drop_s,
        "cu_gnb.RRC.SigTimeReEstab.Avg": "0",
        "cu_gnb.RRC.SigTimeReEstab.Max": "0",
        "cu_gnb.RRC.SigTimeReconfig.Avg": "0",
        "cu_gnb.RRC.SigTimeReconfig.Max": "0",
        "cu_gnb.RRC.SigTimeSetup.Avg": "0",
        "cu_gnb.RRC.SigTimeSetup.Max": "0",
        # PEE 溫度 — host CPU 溫度(proxy;無 min/max 追蹤 → 三值同源)
        "du_169:PEE.AvgTemperature": f"{cpu_temp:.2f}",
        "du_170:PEE.MinTemperature": f"{cpu_temp:.2f}",
        "du_171:PEE.MaxTemperature": f"{cpu_temp:.2f}",
    }

    # MCS / CQI 分布 — 真值(DU pm_aggregator bins)
    mcs_dl = du_acc.get("mcs_dl_bins") or [0] * MCS_BINS
    mcs_ul = du_acc.get("mcs_ul_bins") or [0] * MCS_BINS
    cqi = du_acc.get("cqi_bins") or [0] * CQI_BINS
    for i in range(MCS_BINS):
        rec[f"du_CARR.PDSCHMCSDist.BinTable2.BinMCS{i}"] = str(int(mcs_dl[i]) if i < len(mcs_dl) else 0)
    for i in range(MCS_BINS):
        rec[f"du_CARR.PUSCHMCSDist.BinTable1.BinMCS{i}"] = str(int(mcs_ul[i]) if i < len(mcs_ul) else 0)
    for i in range(CQI_BINS):
        _c = int(cqi[i]) if i < len(cqi) else 0
        rec[f"du_CARR.WBCQIDist.BinCQI{i}.BinTable2"] = str(_c)
        # 標準名並存(理由同 PrbTot)。RIC 端找 du_wbCqiDist.* 找不到,
        # 誤判成「連分箱都沒有」。
        rec[f"du_wbCqiDist.BinCQI{i}"] = str(_c)

    # PRB 累計 — 真值(DU 累計 PRB 數)
    # 2026-09-22:PRB 可用數 —— 使用率的分母,訂閱端無法從用量反推。
    # 也是功耗估算(P = P_static + P_dyn × PRB率)的必要輸入。
    _prb_avail = int(prb_avail or 0)
    if _prb_avail:
        rec["du_RRU.PrbAvailDl"] = str(_prb_avail)
        rec["du_RRU.PrbAvailUl"] = str(_prb_avail)
    _prb_dl = int(du_acc.get("prb_used_dl", 0))
    _prb_ul = int(du_acc.get("prb_used_ul", 0))
    rec["du_CARR.PRBUsageDLNbr"] = str(_prb_dl)
    rec["du_CARR.PRBUsageULNbr"] = str(_prb_ul)
    # 2026-09-22:同一組數值再用 TS 28.552 標準名出一份。
    # RIC 端照規格找 RRU.PrbTotDl 找不到,誤判成「有分母沒分子」——
    # 其實分子一直都在,只是叫 du_CARR.PRBUsageDLNbr。
    # 用「並存」而非改名:既有 xApp 已經在讀舊名,改名會讓它們解不到欄位。
    rec["du_RRU.PrbTotDl"] = str(_prb_dl)
    rec["du_RRU.PrbTotUl"] = str(_prb_ul)
    # 2026-09-22:活動終端數與每終端吞吐 —— 都是逐 UE 資料的聚合,
    # 訂閱端要自己從 e2 區塊推,兩邊推法不同就對不起來,索性在這裡算好。
    _rows = cell_ue_rows or []
    _act_dl = [r for r in _rows if float(getattr(r["meas"], "throughput_dl_mbps", 0) or 0) > 0]
    _act_ul = [r for r in _rows if float(getattr(r["meas"], "throughput_ul_mbps", 0) or 0) > 0]
    rec["du_DRB.MeanActiveUeDl"] = str(len(_act_dl))
    rec["du_DRB.MeanActiveUeUl"] = str(len(_act_ul))
    # UEThp = 該 cell 所有連線 UE 的吞吐平均(Mbps);沒有 UE 時回 0 而非除零
    _thp_dl = [float(r["meas"].throughput_dl_mbps or 0) for r in _rows]
    _thp_ul = [float(r["meas"].throughput_ul_mbps or 0) for r in _rows]
    rec["du_DRB.UEThpDl"] = f"{(sum(_thp_dl) / len(_thp_dl)) if _thp_dl else 0.0:.3f}"
    rec["du_DRB.UEThpUl"] = f"{(sum(_thp_ul) / len(_thp_ul)) if _thp_ul else 0.0:.3f}"
    # 2026-09-22:傳輸區塊計數(TS 28.552 §5.1.1.x)。DU 的 HARQ 計數器一直都有值,
    # 只是從沒對外輸出 —— RIC 端因此判定「du_TB 整族都沒有」。
    #   harq_rounds_dl[i] = 依下行 SINR 分箱估的「第 i 輪才成功」TB 數
    #   harq_errors_dl    = SINR < 0 dB 的 TB 數(視為最終失敗)
    # ⚠ 這是 SINR 分箱的**近似**,不是逐 TB 的 HARQ 實際回報。方向與量級可用,
    #   但不宜拿來做嚴格的 BLER 校驗。文件已標註。
    # 對映:TotNbr = 首傳數(每個 TB 只算一次);Tot = 含重傳的總傳輸次數。
    _hr = list(du_acc.get("harq_rounds_dl") or [])
    _herr = int(du_acc.get("harq_errors_dl") or 0)
    def _tb_counts(rounds: list, errors: int) -> tuple[int, int]:
        """(TB 數, 傳輸次數)。

        TotNbr 是**每個 TB 只算一次** —— 不管它第幾輪成功,首傳都發生過。
        2026-09-22:先前誤寫成 rounds[0] + errors,把第二、三輪才成功的 TB 漏掉,
        分母偏小使錯誤率從 16% 灌水到 47%。
        Tot 是含重傳的總傳輸次數:第 i 輪成功的 TB 傳了 i+1 次;最終失敗的用滿重傳上限。
        """
        rs = [int(x) for x in rounds]
        tb = sum(rs) + int(errors)
        max_tx = len([x for x in rs if x]) + 1 if any(rs) else 1
        tx = sum(v * (i + 1) for i, v in enumerate(rs)) + int(errors) * max_tx
        return tb, tx

    if any(_hr) or _herr:
        _tb, _tx = _tb_counts(_hr, _herr)
        rec["du_TB.TotNbrDl"] = str(_tb)            # TB 數(每個 TB 算一次)
        rec["du_TB.TotNbrDl.Tot"] = str(_tx)        # 傳輸次數(含重傳)
        rec["du_TB.ErrTotalNbrDl"] = str(_herr)
        rec["du_TB.ErrTotalNbrDl.Tot"] = str(_herr)
    # cell 可用率(TS 28.552 cellAvailablePer):該 cell 實際運作的 tick 數
    # ÷ 它存在期間經過的 tick 數 × 100。
    # 「不可用」在我們的模型裡 = 節能關站(is_active=False)—— tick_body 會跳過那些 cell,
    # tick 就不累加,兩者的差自然就是中斷時間。分母從 cell 第一次出現起算。
    _av = du_acc.get("avail_ticks_cum")
    _ft = du_acc.get("first_tick")
    _elapsed = 0   # cell 出現至今經過的 tick 數;下面的功耗模型也用它當時間基準
    if _av is not None and _ft is not None and int(_ft) >= 0 and du_tick_now > 0:
        _elapsed = max(1, int(du_tick_now) - int(_ft) + 1)
        rec["du_gnb.PEE.cellAvailablePer"] = f"{min(100.0, 100.0 * int(_av) / _elapsed):.2f}"

    # ── 功耗(TS 28.552 §5.1.1.19 PEE.AvgPower / PEE.Energy)────────────────
    # 模型:ETSI ES 203 228 / EARTH 線性功耗模型
    #     P_in = N_TRX × (P_static + Δp × P_out_max × load)      (運作中)
    #     P_in = N_TRX × P_sleep                                  (節能關站)
    # P_out_max 由該 cell 的發射功率換算(dBm → W);走廊場景 src/nbr 10 dBm、
    # mid 5 dBm,所以三顆的功耗本來就不同 —— 這也是為什麼要把 tx_power_dbm
    # 一路從場景帶到 CU,而不是用 DU 的單一全域旋鈕。
    # load 取下行 PRB 使用率(未經 OAI 校正的 raw 值 —— 校正係數是為了對齊 OAI
    # 的 KPM 讀數,拿來當實體佔用率會高估近 10 倍)。
    # 常數預設取 pico/small-cell 級別;實機校準時用 env 覆寫,不必改碼。
    _tx_dbm = getattr(cfg, "tx_power_dbm", None)
    if _tx_dbm is not None and du_tick_now > 0:
        _n_trx = _env_float("PEE_N_TRX", 1.0)
        _p_static = _env_float("PEE_STATIC_W", 6.8)
        _p_slope = _env_float("PEE_SLOPE", 4.0)
        _p_sleep = _env_float("PEE_SLEEP_W", 4.3)
        _p_out_max_w = 10.0 ** ((float(_tx_dbm) - 30.0) / 10.0)
        # 負載 = 累計已用 PRB ÷ 同期間的 PRB 容量。DU 的 per-cell 累加器是
        # 「開機以來累計」(snapshot 不 reset),所以分母也用累計 tick 數,
        # 兩邊同基準。算出來的是全程平均負載 —— 正好對應 AvgPower 的語意。
        _span = int(_elapsed) if _elapsed else int(du_tick_now)
        _cap = _prb_avail * max(1, _span)
        _load = min(1.0, max(0.0, (_prb_dl / _cap) if _cap > 0 else 0.0))
        # 關站中的 cell 走 sleep 功耗(is_active 由 DU Config Update 同步過來)。
        _watts = _n_trx * (
            (_p_static + _p_slope * _p_out_max_w * _load)
            if getattr(cfg, "is_active", True) else _p_sleep
        )
        rec["du_gnb.PEE.AvgPower"] = f"{_watts:.3f}"
        # Energy:TS 28.552 是量測期間的耗能(kWh)。這裡給 cell 出現至今的
        # **累計**值 —— 訂閱端做差分就能得到任意期間的耗能,反之不行。
        # 關站期間按 sleep 功耗計,所以節能關站會在曲線上看得出來。
        if _av is not None and sim_dt_ms > 0 and _elapsed > 0:
            _dt_s = float(sim_dt_ms) / 1000.0
            _on_s = int(_av) * _dt_s
            _off_s = max(0, int(_elapsed) - int(_av)) * _dt_s
            _p_on = _n_trx * (_p_static + _p_slope * _p_out_max_w * _load)
            _kwh = (_p_on * _on_s + _n_trx * _p_sleep * _off_s) / 3_600_000.0
            rec["du_gnb.PEE.Energy"] = f"{_kwh:.6f}"

    # 上行同理。2026-09-22 之前這一族是直接複製下行的(同一段程式用下行 SINR 累加兩個方向),
    # 已改成用上行自己的 SINR(RU 的 _compute_ul_sinr_db)。舊 RU 不帶 ul_sinr_db 時
    # DU 不累加,這裡就整族不輸出 —— 沒有值好過抄來的值。
    _hru = list(du_acc.get("harq_rounds_ul") or [])
    _herru = int(du_acc.get("harq_errors_ul") or 0)
    if any(_hru) or _herru:
        _tbu, _txu = _tb_counts(_hru, _herru)
        rec["du_TB.TotNbrUl"] = str(_tbu)
        rec["du_TB.TotNbrUl.Tot"] = str(_txu)
        rec["du_TB.ErrTotalNbrUl"] = str(_herru)
        rec["du_TB.ErrTotalNbrUl.Tot"] = str(_herru)
    # 空口 delay — RLC SDU delay 當 proxy(5QI9;UL 未建模 → 0)
    rec["du_DRB.AirIfDelayDlAvg.5QI1"] = f"{cell_delay_q1_ms:.0f}"  # D:5QI1(語音)delay 轉真
    rec["du_DRB.AirIfDelayDlAvg.5QI9"] = f"{cell_delay_ms:.0f}"
    rec["du_DRB.AirIfDelayUlAvg.5QI1"] = "0"
    rec["du_DRB.AirIfDelayUlAvg.5QI9"] = "0"
    return rec


# ── 主流程 ─────────────────────────────────────────────────────────

class FullKpmReporter:
    @staticmethod
    def collect() -> dict[str, Any]:
        t0 = time.monotonic()
        now = datetime.now(timezone.utc)
        now_ms = int(time.time() * 1000)
        warnings: list[str] = []

        cells = list(CellConfig.objects.all())
        active_cell_ids = {c.cell_id for c in cells}
        cell_by_id = {c.cell_id: c for c in cells}
        # cell_id → gNB 名(all_rsrp / ran_name 用)
        gnb_of_cell = {c.cell_id: (c.gnb_id or "unknown") for c in cells}
        gnb_ids = sorted({c.gnb_id or "unknown" for c in cells})

        du_dump = _fetch_du_dump_pm()
        du_gnbs: dict[str, Any] = du_dump.get("gnbs", {}) or {}
        tick_ms = int(du_dump.get("wall_tick_ms") or 0)
        if not du_dump:
            warnings.append("du dump_pm unreachable — du_* counters are 0")

        # per-cell DL 負載(0~1)— 3GPP RSRQ 的 activity factor 用(idle 鄰站干擾低)
        cell_load: dict[str, float] = {}
        for cid in active_cell_ids:
            last_prb = (
                CellMeasurementLog.objects.filter(cell_id=cid)
                .order_by("-recorded_at")
                .first()
            )
            cell_load[cid] = float(last_prb.prb_pct_dl) / 100.0 if last_prb else 0.0

        # per-UE 快照(CONNECTED only,對齊現行 KpmReporter 行為)
        ue_rows: list[dict[str, Any]] = []
        conn_per_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for ue in UeContext.objects.filter(rrc_state="CONNECTED"):
            if not ue.serving_cell or ue.serving_cell not in active_cell_ids:
                continue
            m = (
                MeasurementLog.objects.filter(ue_id=ue.ue_id)
                .order_by("-recorded_at")
                .first()
            )
            if m is None:
                continue
            neighbors = [
                n for n in (m.neighbor_cells_json or [])
                if n.get("cell_id") and n["cell_id"] in active_cell_ids
                and n["cell_id"] != ue.serving_cell
            ]
            if m.rsrp_dbm is None:      # 該視窗無量測樣本 → 不進統計(見 f1ap 的說明)
                continue
            all_dbm = [m.rsrp_dbm] + [float(n.get("rsrp_dbm", -120.0)) for n in neighbors]
            # (rsrp, load) 配對 — serving + 鄰區,RSRQ 的 RSSI 分母用
            cells_dbm_load = [(m.rsrp_dbm, cell_load.get(ue.serving_cell, 0.0))] + [
                (float(n.get("rsrp_dbm", -120.0)), cell_load.get(n["cell_id"], 0.0))
                for n in neighbors
            ]
            interfered = int(any(
                float(n.get("rsrp_dbm", -999.0)) >= m.rsrp_dbm - _INTERFERED_GAP_DB
                for n in neighbors
            ))
            qos_5qi = int((ue.traffic_profile_json or {}).get("qos_5qi", 9) or 9)
            row = {
                "ue": ue, "meas": m, "neighbors": neighbors,
                "all_dbm": all_dbm, "cells_dbm_load": cells_dbm_load,
                "interfered": interfered, "qos_5qi": qos_5qi,
            }
            ue_rows.append(row)
            conn_per_cell[ue.serving_cell].append(row)

        # HO 計數(只算 active cell;對齊現行 fresh-only filter)
        ho_per_cell: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for evt in HandoverEvent.objects.filter(source_cell__in=active_cell_ids):
            d = ho_per_cell[evt.source_cell]
            d["prep_req"] += 1
            if evt.status in ("EXEC", "SUCC", "FAIL"):
                d["prep_succ"] += 1
                d["exe_req"] += 1
            if evt.status == "SUCC":
                d["exe_succ"] += 1
            if evt.trigger == "A3_TTT":
                d["a3"] += 1

        # P1-3(2026-08-12):RLF / RRC 重建 per-cell 計數(RlfEvent 依 source_cell)
        rlf_per_cell: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        try:
            from main.apps.cu_cp.models.rlf_event import RlfEvent
            for evt in RlfEvent.objects.filter(source_cell__in=active_cell_ids):
                d = rlf_per_cell[evt.source_cell]
                d["rlf"] += 1
                if evt.outcome == "DROP":
                    d["drop"] += 1
                elif evt.outcome == "REESTAB_WITH_CTX":
                    d["reestab_with"] += 1
                    d["reestab_att"] += 1
                elif evt.outcome == "REESTAB_WITHOUT_CTX":
                    d["reestab_without"] += 1
                    d["reestab_att"] += 1
        except Exception:
            logger.exception("RLF per-cell aggregation failed")

        # 2026-08-12:ConnEstab 真累計(取代現值代理)—— RrcEstabCounter 事件計數
        estab_by_cell: dict[str, tuple[int, int]] = {}
        try:
            from main.apps.cu_cp.models.rrc_estab_counter import RrcEstabCounter
            for c_ in RrcEstabCounter.objects.filter(cell_id__in=active_cell_ids):
                estab_by_cell[c_.cell_id] = (int(c_.att), int(c_.succ))
        except Exception:
            logger.exception("estab counter fetch failed")

        host_bbu = BbuTelemetryService.snapshot_host()

        # ── e2[] ───────────────────────────────────────────────────
        e2_out: list[dict[str, Any]] = []
        for gid in gnb_ids:
            g_cells = []
            for cfg in cells:
                if (cfg.gnb_id or "unknown") != gid:
                    continue
                ues_out = []
                resolve_ncgi = _nrt_resolver(cells) if _NEIGHBOR_KEY == "pci" else None
                rb_cursor = 0  # 同 cell 內以實際 rb_width 疊出虛擬連續配置的起點
                for row in conn_per_cell.get(cfg.cell_id, []):
                    m = row["meas"]
                    neigh_list = []
                    if _NEIGHBOR_KEY == "pci":
                        # 依 (pci, arfcn) 合併:混淆的兩顆 cell UE 分不出來,只會量到一個疊加的訊號。
                        # 同鍵送兩筆會被 RIC 的標籤寫入 last-write-wins 吃掉一筆,那正是混淆的證據。
                        grouped: dict[tuple[int, int | None], list[float]] = {}
                        for n in row["neighbors"]:
                            n_cfg = cell_by_id.get(n["cell_id"])
                            n_pci = int(n_cfg.pci) if n_cfg is not None else int(n.get("pci") or 0)
                            n_arfcn = _arfcn_of(n_cfg) if n_cfg is not None else n.get("arfcn")
                            grouped.setdefault((n_pci, n_arfcn), []).append(float(n.get("rsrp_dbm", -120.0)))
                        for (n_pci, n_arfcn), rsrps in sorted(grouped.items()):
                            n_rsrp = _dbm_sum(rsrps)
                            entry = {"pci": n_pci, "arfcn": n_arfcn,
                                     "rsrp": round(n_rsrp, 1),
                                     "rsrq": round(float(_derive_rsrq(n_rsrp, row["cells_dbm_load"])), 1)}
                            ncgi = resolve_ncgi(cfg.cell_id, n_pci, n_arfcn)
                            if ncgi is not None and len(rsrps) == 1:
                                entry["ncgi"] = ncgi      # NRT 已解出且無混淆才給
                            neigh_list.append(entry)
                    for n in ([] if _NEIGHBOR_KEY == "pci" else row["neighbors"]):
                        n_cfg = cell_by_id.get(n["cell_id"])
                        n_hex = _cell_hex_id(n_cfg) if n_cfg else n["cell_id"]
                        n_rsrp = float(n.get("rsrp_dbm", -120.0))
                        # 一律用 3GPP 公式重算(RU 舊值公式不明,棄用求一致)
                        n_rsrq = _derive_rsrq(n_rsrp, row["cells_dbm_load"])
                        neigh_list.append({n_hex: {
                            # 2026-09-22:補上 pci / arfcn。真實 UE 量測鄰區只讀得到這兩個,
                            # 沒有它們,訂閱端就做不出「缺漏鄰區」「PCI 混淆」的判定 ——
                            # 那是外部 Agent 的核心題型。以 cell_id 為鍵是我方的上帝視角。
                            "pci": int(n_cfg.pci) if n_cfg is not None else n.get("pci"),
                            "arfcn": _arfcn_of(n_cfg) if n_cfg is not None else n.get("arfcn"),
                            # 小數保留一位:整數化會讓訂閱端算不出可用的標準差
                            "rsrp": round(n_rsrp, 1),
                            "rsrq": round(float(n_rsrq), 1),
                        }})
                    ues_out.append({
                        "role": 1,
                        "ue_id": row["ue"].ue_id,
                        # 2026-09-22 RIC 要求:與 ran_func 2 同一個 amf-UE-NGAP-ID。
                        # 他們的 3-1(單 UE 換手)/ 2-6 的 UEID 是 UEID-GNB,只拿到 p03 這種名字
                        # 對不到 NGAP ID 就下不了命令;兩條路在這裡接起來。
                        "ngap_id": getattr(row["ue"], "amf_ue_ngap_id", None),
                        "interfered": row["interfered"],
                        "rsrp": round(float(m.rsrp_dbm), 1),
                        # RU 已依 TS 38.215 算好 RSRQ(含 RSSI);沒有才退回本地推導
                        "rsrq": (round(float(m.rsrq_db), 1) if getattr(m, "rsrq_db", None) is not None
                                 else _derive_rsrq(m.rsrp_dbm, row["cells_dbm_load"])),
                        "sinr": round(float(m.sinr_db), 1),
                        "ul_sinr": (round(float(m.ul_sinr_db), 1)
                                    if getattr(m, "ul_sinr_db", None) is not None else None),
                        "cqi": (round(float(m.cqi), 1) if getattr(m, "cqi", None) is not None else None),
                        "neighbors": neigh_list,
                        "dl_throughput": round(float(m.throughput_dl_mbps), 2),
                        "ul_throughput": round(float(m.throughput_ul_mbps), 2),
                        "rb_start": rb_cursor,
                        "rb_width": int(m.rb_width_dl),
                    })
                    rb_cursor += int(m.rb_width_dl)
                _beams = _beam_stats(conn_per_cell.get(cfg.cell_id, []))
                g_cells.append({
                    "cell_id": _cell_hex_id(cfg),
                    "ran_name": gid,
                    "pci": int(cfg.pci),
                    "ues": ues_out,
                    # 每波束量測(O-RAN WG1 §4.6.4.1);沒有 GoB 的 cell 是空 list
                    "beams": _beams,
                })
            e2_out.append({
                "gnb_id": gid,
                "timestamp": now_ms // 1000,
                "cells": g_cells,
            })

        # ── ue_status[] ────────────────────────────────────────────
        ue_status_out: list[dict[str, Any]] = []
        for row in ue_rows:
            ue, m = row["ue"], row["meas"]
            all_rsrp: Any = {}
            serv_gnb = gnb_of_cell.get(ue.serving_cell, "unknown")
            if _NEIGHBOR_KEY == "pci":
                # list 形式,以 (pci, arfcn) 為識別;服務那筆 pci 必須等於 ue_status.serving_pci
                _serv_cfg = cell_by_id[ue.serving_cell]
                _agg: dict[tuple[int, int | None], list[float]] = {}
                for n in row["neighbors"]:
                    n_cfg = cell_by_id.get(n["cell_id"])
                    k = (int(n_cfg.pci) if n_cfg is not None else int(n.get("pci") or 0),
                         _arfcn_of(n_cfg) if n_cfg is not None else n.get("arfcn"))
                    _agg.setdefault(k, []).append(float(n.get("rsrp_dbm", -120.0)))
                all_rsrp = [{"pci": int(_serv_cfg.pci), "arfcn": _arfcn_of(_serv_cfg),
                             "rsrp": round(float(m.rsrp_dbm), 1), "serving": True}]
                all_rsrp += [{"pci": k[0], "arfcn": k[1], "rsrp": round(_dbm_sum(v), 1)}
                             for k, v in sorted(_agg.items())]
            else:
                all_rsrp[serv_gnb] = round(float(m.rsrp_dbm), 1)
                for n in row["neighbors"]:
                    g = gnb_of_cell.get(n["cell_id"], n["cell_id"])
                    v = round(float(n.get("rsrp_dbm", -120.0)), 1)
                    # 同 gNB 多 cell → 取最強
                    if g not in all_rsrp or v > all_rsrp[g]:
                        all_rsrp[g] = v
            ue_status_out.append({
                "ue_id": ue.ue_id,
                "ngap_id": getattr(ue, "amf_ue_ngap_id", None),
                "serving_gnb": serv_gnb,
                "serving_pci": int(cell_by_id[ue.serving_cell].pci),
                "rsrp_dbm": round(float(m.rsrp_dbm), 1),
                "sinr_db": round(float(m.sinr_db), 1),
                "all_rsrp": all_rsrp,
                "throughput_dl_mbps": int(round(m.throughput_dl_mbps)),
                "throughput_ul_mbps": int(round(m.throughput_ul_mbps)),
                "quality": _quality(m.sinr_db),
                "qos_5qi": row["qos_5qi"],
                "role": 1,
                "mcs_dl": int(m.mcs_dl),
                "rb_width_dl": int(m.rb_width_dl),
            })

        # ── pm{} ───────────────────────────────────────────────────
        pm_out: dict[str, list[dict[str, str]]] = {}
        for gid in gnb_ids:
            recs = []
            for cfg in cells:
                if (cfg.gnb_id or "unknown") != gid:
                    continue
                conn_cnt = len(conn_per_cell.get(cfg.cell_id, []))
                # B/C(2026-08-12):持久高水位 + 真平均(取樣累計,CU 重啟不歸零)
                try:
                    from main.apps.cu_cp.services.business.cell_counters import (
                        get_session_time, sample_conn,
                    )
                    conn_max_db, conn_mean_db = sample_conn(cfg.cell_id, conn_cnt)
                    released_session_sec = get_session_time(cfg.cell_id)
                except Exception:
                    conn_max_db, conn_mean_db = conn_cnt, float(conn_cnt)
                    released_session_sec = 0
                _conn_max_seen[cfg.cell_id] = max(_conn_max_seen[cfg.cell_id], conn_max_db)
                rows = conn_per_cell.get(cfg.cell_id, [])
                delays = [
                    float(getattr(r["meas"], "rlc_sdu_delay_dl_ms", 0.0) or 0.0)
                    for r in rows
                ]
                # D(2026-08-12):delay 按 UE 的 5QI 分桶(AirIfDelayDlAvg.5QI1 轉真)
                d_q1 = [float(getattr(r["meas"], "rlc_sdu_delay_dl_ms", 0.0) or 0.0)
                        for r in rows if int(getattr(r["meas"], "qos_5qi", 9) or 9) == 1]
                delay_q1_ms = (sum(d_q1) / len(d_q1)) if d_q1 else 0.0
                # P1-3 補(2026-08-12):SessionTime = Σ(now − created_at) 秒(本 cell CONNECTED UE)
                session_time_sec = released_session_sec + int(sum(
                    max(0.0, (now - r["ue"].created_at).total_seconds())
                    for r in rows if getattr(r["ue"], "created_at", None)
                ))
                recs.append(_pm_record(
                    cfg,
                    now=now,
                    conn_cnt=conn_cnt,
                    conn_max=_conn_max_seen[cfg.cell_id],
                    ho=ho_per_cell.get(cfg.cell_id, {}),
                    rlf=rlf_per_cell.get(cfg.cell_id, {}),
                    du_acc=du_gnbs.get(cfg.cell_id, {}),
                    prb_avail=int(du_dump.get("prb_per_cell") or 0),
                    du_tick_now=int(du_dump.get("tick_count") or 0),
                    cell_ue_rows=conn_per_cell.get(cfg.cell_id, []),
                    prb_log=None,
                    cell_delay_ms=(sum(delays) / len(delays)) if delays else 0.0,
                    cell_delay_q1_ms=delay_q1_ms,
                    cpu_temp=host_bbu["cpu_temp"],
                    session_time_sec=session_time_sec,
                    estab=estab_by_cell.get(cfg.cell_id, (0, 0)),
                    conn_mean=conn_mean_db,
                    sim_dt_ms=int(du_dump.get("sim_dt_ms") or 0),
                ))
            pm_out[f"gnb-{gid}"] = recs

        # ── bbu_status ─────────────────────────────────────────────
        bbu_raw = BbuTelemetryService.per_gnb_snapshot(gnb_ids)
        bbu_out: dict[str, Any] = {f"gnb-{g}": v for g, v in bbu_raw.items()}
        bbu_out["timestamp"] = str(now_ms)

        return {
            "timestamp_ms": now_ms,
            # 2026-09-22:劇本時間(自模擬起點的毫秒)。E2 原本只有牆鐘時戳,
            # 訂閱端無從得知事件發生在劇本第幾秒 —— 而牆鐘換算不可靠
            # (倍速達成率不穩,實測設 30× 只達成 27.3×)。None = DU 尚未回報。
            "scene_sim_ms": du_dump.get("scene_sim_ms"),
            "compute_ms": int((time.monotonic() - t0) * 1000),
            "tick_ms": tick_ms,
            "e2": e2_out,
            "ue_status": ue_status_out,
            "pm": pm_out,
            "bbu_status": bbu_out,
            "warnings": warnings,
        }
