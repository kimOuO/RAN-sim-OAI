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
    """measSampleRatePerMin 的正式定義(2026-08-25 定案,RIC 第八輪指出原語意矛盾):

        **「駐留於 source cell 的 UE,量測回報中看到 target cell 的樣本率(/min)」**
        —— per-(source, target) 歸屬,不是 target 的總量測率。

    原實作是「該 target (pci,arfcn) 的總量測率,不分來源」,同時還有
    arfcn 鍵對不上的 bug,兩者疊加讓同一份輸出用任何一種定義都解釋不通
    (d02→s19=0 但 d02 的 UE 正以 300/min 量測 s19;s19→d02=300 但無任何來源歸屬)。

    為什麼要來源歸屬:第 11 題的雙歸零判準是「**這條關係**沒人在用了」——
    別的 cell 的 UE 量得到 target 不代表這條關係活著。歸屬用 meas_aggregate
    的 bySourceCell(回報該筆量測的 UE 當下 serving cell)。
    """
    agg = anr_kpm.meas_aggregate(window_min).get("measurementReportAggregate") or []
    # (target_pci, source_cell) → rate
    by_src: dict[int, dict[str, float]] = {}
    for a in agg:
        pci = a.get("reportedPhysicalCellId")
        if pci is None:
            continue
        by_src[int(pci)] = {k: float(v) for k, v in (a.get("bySourceCell") or {}).items()}
    out: dict[tuple[str, str], float] = {}
    for src, tgt, pci in NrCellRelation.objects.values_list(
            "source_cell_id", "target_cgi", "target_pci"):
        if pci is None:
            continue
        out[(src, tgt)] = by_src.get(int(pci), {}).get(src, 0.0)
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
            # 依 cause 分列的累計 —— v10 第 12 題範例是 map
            # ({"RrcReestabReq":1180,"TXnRELOCprepExpiry":96}),且其 pseudo code
            # 用「is empty」判斷有無失敗史。先前回 int 是誤讀肆章的文字定義
            # (「準備＋執行」指涵蓋範圍,不是要加總),RIC 2026-08-25 指出。
            "MM.HoFailCumulativeSinceCreation": dict(cum),
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
    # 現存 cell(含非 active 的,只要組態還在就不算殘留)。
    # 2026-08-26 第三十三輪:只按 source 過濾 —— target 可以是已消失的 cell,
    # 那正是殭屍/回收(第 11 題)的敘事本體;原本連 target 一起濾,
    # REMOVE/REMOVE_REJECTED(ghost target)全被吞掉,RIC 重啟回填帳本斷料。
    # 跨劇本殘留仍由 source 過濾擋住(舊場景的 source cell 已不在)。
    _live = set(CellConfig.objects.values_list("cell_id", flat=True))
    chg_qs = chg_qs.filter(source_cell_id__in=_live)

    meas = anr_kpm.meas_aggregate(window_min)
    agg = meas.get("measurementReportAggregate") or []
    for a in agg:
        k = f"meas.{a.get('reportedPhysicalCellId')}.{a.get('reportedArfcn')}"
        a["trendLast30Min_ratePerMin"] = _trend(k, a.get("sampleRatePerMin") or 0.0)

    return {
        "timestamp": now.isoformat(),
        # granularityPeriod = 速率語意的定義域(E2SM-KPM §8.3.8)。
        # **必須等於這批速率實際的計算窗**,否則 xApp 的「每分鐘」會對不上。
        # 先前用獨立 env 寫死 60s,而速率其實是用 window_min(預設 10 分鐘)算的 ——
        # 兩者各說各話,RIC 2026-08-25 指出。改為由實際窗推導,不可能再漂。
        "granularityPeriod": f"{int(round(window_min * 60))}s",
        "e2NodeInformation": {
            "servingCells": [
                {"ncgi": c.cell_id, "physicalCellId": c.pci,
                 "arfcn": nr_arfcn_from_ghz(c.frequency_ghz),
                 "radioAccessTechnology": "NR"} for c in cells],
            "neighbourCellRelations": [_relation_ie_v10(r) for r in rel_qs],
            "frequencyRelations": anr_kpm.freq_relations(),
            # limit 是 per-cell 語意(每 cell 的 NRT 條目上限),used 也必須 per-cell ——
            # 原本未指定 cell_id 時回全表 count(3 cell 滿載時 used=24 vs limit=8),
            # xApp 判 used==limit 會錯。usedByCell 逐 cell 給;used 保留為「最滿的
            # 那個 cell」向後相容(第 9 題的觸發 = 任一 source cell 滿載)。
            "nrtCapacity": (lambda _cnt: {
                "limit": get_int("ANR_NRT_CAPACITY", 32),
                "used": max(_cnt.values(), default=0),
                "usedByCell": _cnt,
            })({c.cell_id: rel_qs.filter(source_cell_id=c.cell_id).count()
                for c in cells}),
            "anrIntraEnabled": get_bool("ANR_INTRA_ENABLED", default=True),
            # 兩個容器分開,各自 50 筆 —— 不是一個 ring 塞兩種事件。
            # 理由(RIC 2026-08-25 §5 提出,我們採納):
            #   ADD/REMOVE 量大且可丟 —— 丟了頂多稽核不完整,不影響正確性
            #   FLAG 稀有但關鍵     —— 丟了是**正確性問題**:xApp 重啟後無從得知
            #                          自己設過哪些旗標(旗標在 v10 不可觀測),
            #                          孤兒旗標會讓那條關係永久呈現假的第 6 題
            # 實測他們那台的 50 筆是「REMOVE 32 + ADD 18」一格不剩,
            # 任何一筆 FLAG 進來會立刻被擠掉 —— 拉高上限只是把問題往後推。
            # 剪掉「指向已不存在的 cell」的事件 —— 換劇本後上一場的事件會殘留,
            # 而 xApp 用 flagChangeEvents 重建旗標帳本,殘留會讓它以為自己在
            # 一個根本不存在的 cell 上設過旗標(RIC 2026-08-25 在第12題 fixture
            # 看到上一場的 nbr_c0 事件)。
            # 用「cell 是否存在」而不是「切劇本就清空」:E2 重連時 cell 沒變、
            # 旗標也還在,清掉反而讓對方重建不出帳本 —— 那比殘留更糟。
            "relationChangeEvents": [
                {"action": e.action,
                 "sourceCellNcgi": e.source_cell_id,   # 第三十三輪:對齊 flag 事件
                 "targetCellGlobalId": e.target_cgi,
                 "by": e.by, "at": e.at.isoformat(), "detail": e.detail,
                 "reason": e.detail if e.action.endswith("_REJECTED") else None}
                for e in chg_qs.exclude(action__startswith="FLAG_")[:50]],
            "flagChangeEvents": [
                {"action": e.action,               # FLAG_SET / FLAG_CLEAR
                 # RIC 第二十五輪正式請求:target-only 在多條同 target 關係下
                 # 結構性無法歸屬(幽靈 FLAG_CLEAR 插曲);模型本就存 source。
                 "sourceCellNcgi": e.source_cell_id,
                 "targetCellGlobalId": e.target_cgi,
                 "flag": e.detail,                 # hoBlocklist / noRemove / xnBlocklist
                 "by": e.by, "at": e.at.isoformat()}
                for e in chg_qs.filter(action__startswith="FLAG_")[:50]],
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
