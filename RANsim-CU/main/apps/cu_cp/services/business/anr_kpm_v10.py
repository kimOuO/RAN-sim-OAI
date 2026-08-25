"""E2SM-ANR 觀測資料 —— v10 版格式(ANR情境測驗_v10.docx 肆章)。

與 v8 的差別不是加欄位,是**重組**:
  1. cell 級指標鍵名扁平化為 `指標.NCGI`,值改成 {current*, baseline*, trendLast30Min}
  2. rlfKpm / mroKpm 兩個頂層容器在 v10 不存在 —— 全部併入 kpmIndication.cellLevel
  3. 鄰區關係**不得**帶 flags / isHoAllowed / isRemoveAllowed / isXnAllowed / relationAgeSec
     (v10:旗標狀態非 E2 可觀測;第 12 題的考點就是「讀不到旗標,由行為訊號推論封鎖」——
      送出旗標等於把答案給 xApp)
  4. 換手失敗率拆成**準備**(HoPrepInterFail)與**執行**(HoExeInterFail)兩支 ——
     第 6 題(換手發不出去)與第 7 題(換過去失敗)靠這個鑑別

v8 格式保留於 anr_kpm.py,由 ANR_SCHEMA 環境變數決定送哪版。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
from main.apps.cu_cp.services.business import anr_kpm
from main.apps.cu_cp.services.business.anr_history import metric
from main.apps.cu_cp.services.business.anr_seeder import nr_arfcn_from_ghz
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.utils.logger import get_logger

logger = get_logger(__name__)

# TS 38.423 §9.2.3.2 之 Cause:屬於「換手準備」階段的失敗
_PREP_CAUSES = {"TXnRELOCprepExpiry", "CellNotAvailable", "NoRadioResourcesAvailable"}


def _split_fail_causes(causes: dict[str, float]) -> tuple[dict, dict]:
    """把合併的失敗原因拆成準備/執行兩支(v10 perNeighbourRelation 要分列)。

    準備失敗 = 連 Handover Request 都沒送成(Xn 不通、目標不可用);
    執行失敗 = 送出去了但 UE 接不進去(RandomAccessProblem 等)。
    第 6 題與第 7 題外觀都是「換手失敗」,鑑別點正是落在哪一邊。
    """
    prep = {k: v for k, v in (causes or {}).items() if k in _PREP_CAUSES}
    exe = {k: v for k, v in (causes or {}).items() if k not in _PREP_CAUSES}
    return prep, exe


def _cell_throughput(window_min: float) -> dict[str, dict[str, float]]:
    """cell 級 DRB 量測(UEThp / PdcpSduVolume / RlcSduDelay)。

    MeasurementLog 沒有 cell 欄位 —— 以 UE 當下的 serving_cell 歸戶。
    近似:窗內換過手的 UE,其樣本會全部記到新的 cell。窗口短時影響有限,
    這點寫在這裡而不是藏著。
    """
    from main.apps.cu_cp.models.measurement_log import MeasurementLog
    from main.apps.cu_cp.models.ue_context import UeContext
    now = TimestampService.now()
    win_start = now - timedelta(minutes=window_min)
    serving = dict(UeContext.objects.values_list("ue_id", "serving_cell"))
    acc: dict[str, list[tuple[float, float, float, float, float]]] = {}
    rows = MeasurementLog.objects.filter(recorded_at__gte=win_start).values_list(
        "ue_id", "throughput_dl_mbps", "throughput_ul_mbps",
        "pdcp_sdu_volume_dl", "pdcp_sdu_volume_ul", "rlc_sdu_delay_dl_ms")
    for ue_id, dl, ul, vdl, vul, delay in rows:
        cid = serving.get(ue_id) or ""
        if not cid:
            continue
        acc.setdefault(cid, []).append(
            (float(dl or 0), float(ul or 0), float(vdl or 0), float(vul or 0), float(delay or 0)))
    out: dict[str, dict[str, float]] = {}
    for cid, r in acc.items():
        n = max(len(r), 1)
        out[cid] = {
            "DRB.UEThpDl": sum(x[0] for x in r) / n,
            "DRB.UEThpUl": sum(x[1] for x in r) / n,
            # byte → Mbit(卷面單位為 Mbit/收集間隔)
            "DRB.PdcpSduVolumeDL": sum(x[2] for x in r) * 8 / 1e6,
            "DRB.PdcpSduVolumeUL": sum(x[3] for x in r) * 8 / 1e6,
            "DRB.RlcSduDelayDl": sum(x[4] for x in r) / n,
        }
    return out


def _meas_rate_by_relation(window_min: float) -> dict[tuple[str, str], float]:
    """把「依 (pci, arfcn) 統計的量測樣本速率」對映到「逐關係」。

    第 11 題的回收判準是**雙歸零**:量測樣本速率與換手嘗試速率**同步**歸零
    並持續 6 小時。只看換手嘗試會誤刪「暫時靜默但還在的鄰居」——
    量測還看得到就代表它沒走,雙訊號才是防誤刪的關鍵。
    量測面原本只有 per-(pci,arfcn),這裡用關係的 target pci/arfcn 回接。
    """
    agg = anr_kpm.meas_aggregate(window_min).get("measurementReportAggregate") or []
    by_key: dict[tuple[int, int], float] = {}
    for a in agg:
        pci, arfcn = a.get("reportedPhysicalCellId"), a.get("reportedArfcn")
        if pci is None:
            continue
        by_key[(int(pci), int(arfcn) if arfcn is not None else -1)] = float(
            a.get("sampleRatePerMin") or 0.0)
    out: dict[tuple[str, str], float] = {}
    for src, tgt, pci, arfcn in NrCellRelation.objects.values_list(
            "source_cell_id", "target_cgi", "target_pci", "target_arfcn"):
        if pci is None:
            continue
        out[(src, tgt)] = by_key.get((int(pci), int(arfcn) if arfcn is not None else -1), 0.0)
    return out


def _per_relation_v10(window_min: float) -> list[dict[str, Any]]:
    """逐關係量測 —— v10 形狀(純量 + trendLast30Min_*,不是 current/baseline 物件)。"""
    v8_rows = anr_kpm.ho_kpm(window_min).get("perNeighbourRelation") or []
    meas_rate = _meas_rate_by_relation(window_min)
    # 逐關係的換錯 cell 速率(v10 新增:9.3.38 物件層級含 NRCellRelation)
    wrong = _to_wrong_cell_by_relation(window_min)
    out = []
    for r in v8_rows:
        src, tgt = r["sourceCellNcgi"], r["targetCellGlobalId"]
        prep, exe = _split_fail_causes(r.get("handoverFailureCauseRatePerMin"))
        cum = r.get("handoverFailureCauseCumulativeSinceCreation") or {}
        att = r.get("MM.HoExeAttRatePerMin") or 0.0
        wr = wrong.get((src, tgt), 0.0)
        key = f"{src}|{tgt}"
        out.append({
            "sourceCellNcgi": src,
            "targetCellGlobalId": tgt,
            "MM.HoExeAttRatePerMin": att,
            "MM.HoExeSuccRatio_last50": r.get("MM.HoExeSuccRatio_last50"),
            "sampleCount_last50": r.get("sampleCount_last50"),
            "MM.HoPrepInterFailRatePerMin": prep,
            "MM.HoExeInterFailRatePerMin": exe,
            # 準備+執行合計之累計(v10 要的是總數,不是 cause 分列)
            "MM.HoFailCumulativeSinceCreation": sum(cum.values()) if cum else 0,
            "HO.IntraSys.ToWrongCellRate": wr,
            # 第 11 題雙歸零 aging 的另一半 —— 量測面
            "measSampleRatePerMin": meas_rate.get((src, tgt), 0.0),
            "trendLast30Min_attRatePerMin": _trend(f"rel.att.{key}", att),
            "trendLast30Min_ToWrongCell": _trend(f"rel.wrong.{key}", wr),
            "trendLast30Min_measSampleRatePerMin": _trend(
                f"rel.meas.{key}", meas_rate.get((src, tgt), 0.0)),
        })
    return out


def _trend(key: str, cur: float) -> list[float]:
    return metric(key, cur, "PerMin")["trendLast30Min"]


def _to_wrong_cell_by_relation(window_min: float) -> dict[tuple[str, str], float]:
    """逐關係的 HO.IntraSys.ToWrongCellRate。

    來源與 cell 級同一套:backfill 已把換錯 cell 的換手改寫成
    status=FAIL / failure_cause=HandoverToWrongCell,這裡依 (source,target) 聚合。
    """
    now = TimestampService.now()
    win_start = now - timedelta(minutes=window_min)
    out: dict[tuple[str, str], int] = {}
    for src, tgt in HandoverEvent.objects.filter(
            started_at__gte=win_start, failure_cause="HandoverToWrongCell",
    ).values_list("source_cell", "target_cell"):
        out[(src, tgt)] = out.get((src, tgt), 0) + 1
    return {k: round(v / max(window_min, 1e-9), 3) for k, v in out.items()}


def _relation_ie_v10(r: NrCellRelation) -> dict[str, Any]:
    """9.3.38 之必要欄位 —— **刻意不含**旗標與管理面屬性(見檔頭說明)。"""
    return {
        "sourceCellNcgi": r.source_cell_id,
        "targetCellGlobalId": r.target_cgi,
        "targetPhysicalCellId": r.target_pci,
        "targetArfcn": r.target_arfcn,
        "targetRadioAccessTechnology": r.target_rat,
        "xnX2Established": r.xn_x2_established,
        "hoValidated": r.ho_validated,
        "version": r.version,
    }


def _ccc_config_events(lookback_min: float = 60.0) -> list[dict[str, Any]]:
    """E2SM-CCC 組態變更事件 —— 新 O-NRCellCU 實例建立 = 新 cell 誕生。

    第 11 題要它做「從無到有」的組態面佐證,與量測面互證。
    以 CellConfig.created_at 落在回看窗內者視為新實例。
    """
    now = TimestampService.now()
    since = now - timedelta(minutes=lookback_min)
    out = []
    for c in CellConfig.objects.filter(created_at__gte=since).order_by("created_at"):
        out.append({
            "event": "O-NRCellCU-Created",
            "globalCellId": c.cell_id,
            "observedAt": c.created_at.isoformat(),
        })
    return out


def indication_v10(cell_id: str | None = None,
                   window_min: float = 10.0) -> dict[str, Any]:
    """組出 v10 形狀的完整觀測資料。"""
    from main.apps.cu_cp.models.nr_relation_change_event import NrRelationChangeEvent
    from main.apps.cu_cp.services.business.mro import mro_kpm
    from main.utils.env_loader import get_bool, get_int

    now = TimestampService.now()
    cells_qs = CellConfig.objects.filter(is_active=True)
    if cell_id:
        cells_qs = cells_qs.filter(cell_id=cell_id)
    cells = list(cells_qs)

    ho = anr_kpm.ho_kpm(window_min)
    rlf = anr_kpm.rlf_kpm(window_min)
    mro = mro_kpm(window_min)
    prb = {c: v for c, v in (ho.get("cellLevel") or {}).items()}
    thp = _cell_throughput(window_min)

    # ── cellLevel:扁平化鍵名 指標.NCGI,值為 {current*, baseline*, trend} ──
    cl: dict[str, Any] = {}
    for c in cells:
        n = c.cell_id
        p = prb.get(n) or {}
        t = thp.get(n) or {}
        r = (rlf.get("cellLevel") or {}).get(n) or {}
        m = (mro.get("cellLevel") or {}).get(n) or {}
        for name, val, unit in (
            ("RRU.PrbTotDl", p.get("RRU.PrbTotDl"), "Pct"),
            ("RRU.PrbTotUl", p.get("RRU.PrbTotUl"), "Pct"),
            ("DRB.UEThpDl", t.get("DRB.UEThpDl"), "Mbps"),
            ("DRB.UEThpUl", t.get("DRB.UEThpUl"), "Mbps"),
            ("DRB.PdcpSduVolumeDL", t.get("DRB.PdcpSduVolumeDL"), "Mbit"),
            ("DRB.PdcpSduVolumeUL", t.get("DRB.PdcpSduVolumeUL"), "Mbit"),
            ("DRB.RlcSduDelayDl", t.get("DRB.RlcSduDelayDl"), "Ms"),
            ("RRC.ConnReEstabInboundRatePerMin",
             r.get("RRC.ConnReEstabInboundRatePerMin"), "PerMin"),
            ("RLF.DetectedRate", r.get("RLF.DetectedRate"), "PerMin"),
            ("RLF.DropWithoutReestablishmentRate",
             r.get("RLF.DropWithoutReestablishmentRate"), "PerMin"),
            ("HO.IntraSys.TooEarlyRate", m.get("HO.IntraSys.TooEarlyRate"), "PerMin"),
            ("HO.IntraSys.TooLateRate", m.get("HO.IntraSys.TooLateRate"), "PerMin"),
            ("HO.IntraSys.ToWrongCellRate", m.get("HO.IntraSys.ToWrongCellRate"), "PerMin"),
        ):
            cl[f"{name}.{n}"] = metric(f"{name}.{n}", val, unit)

    rel_qs = NrCellRelation.objects.all()
    chg_qs = NrRelationChangeEvent.objects.all()
    if cell_id:
        rel_qs = rel_qs.filter(source_cell_id=cell_id)
        chg_qs = chg_qs.filter(source_cell_id=cell_id)

    meas = anr_kpm.meas_aggregate(window_min)
    agg = meas.get("measurementReportAggregate") or []
    for a in agg:
        k = f"meas.{a.get('reportedPhysicalCellId')}.{a.get('reportedArfcn')}"
        a["trendLast30Min_ratePerMin"] = _trend(k, a.get("sampleRatePerMin") or 0.0)

    return {
        "timestamp": now.isoformat(),
        # granularityPeriod = 量測**收集間隔**(E2SM-KPM §8.3.8),速率語意的定義域;
        # 不是 xApp 的分析窗(window_min)。DU 的 PM window 才是它的實際來源。
        "granularityPeriod": f"{get_int('ANR_GRANULARITY_SEC', 60)}s",
        "e2NodeInformation": {
            "servingCells": [
                {"ncgi": c.cell_id, "physicalCellId": c.pci,
                 "arfcn": nr_arfcn_from_ghz(c.frequency_ghz),
                 "radioAccessTechnology": "NR"} for c in cells],
            "neighbourCellRelations": [_relation_ie_v10(r) for r in rel_qs],
            "frequencyRelations": anr_kpm.freq_relations(),
            "nrtCapacity": {"limit": get_int("ANR_NRT_CAPACITY", 32),
                            "used": rel_qs.count()},
            "anrIntraEnabled": get_bool("ANR_INTRA_ENABLED", default=True),
            "relationChangeEvents": [
                {"action": e.action, "targetCellGlobalId": e.target_cgi,
                 "by": e.by, "at": e.at.isoformat(), "detail": e.detail,
                 "reason": e.detail if e.action.endswith("_REJECTED") else None}
                for e in chg_qs[:50]],
        },
        "kpmIndication": {
            "cellLevel": cl,
            "perNeighbourRelation": _per_relation_v10(window_min),
        },
        "e2MessageCopyAggregate": {
            "measurementReportAggregate": agg,
            "reestablishmentInboundByPreviousPci":
                rlf.get("reestablishmentInboundByPreviousPci") or [],
        },
        "cgiResolutionSampling": anr_kpm.cgi_resolution_sampling(),
        "cccConfigurationEvents": _ccc_config_events(),
    }
