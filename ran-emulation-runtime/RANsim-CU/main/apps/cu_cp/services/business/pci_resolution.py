"""以 PCI 解析鄰區(真實 ANR 的做法)—— 取代直接拿量測報告裡的 cell_id 比對。

為什麼要這樣做:
    真實 RAN 裡 UE 量測鄰區只讀得到 PCI(0~1007)與載波頻率,讀不到對方是誰。
    網路要知道身分,得再要求 UE 去讀該 cell 的 SIB1(CGI 解析)。
    我們的量測報告一直直接帶 cell_id —— 等於跳過整個 PCI 這一層,ANR 永遠不會錯,
    而「缺漏鄰區」「PCI 混淆」這兩種現象在模型裡根本無法發生。

    模糊性必須來自「網路的鄰區關係表裡查不到 / 查到多個」,而不是「我們把資料藏起來」。

判定(對齊 TS 38.300 §15.3 ANR):
    查 NrCellRelation(source_cell_id, target_pci, target_arfcn)
      剛好一筆 → 已知鄰區,不動作
      零筆     → 缺漏鄰區 → 發起 CGI 解析
      多筆     → PCI 混淆 → 也要 CGI 解析才分得出是哪一個

CGI 解析在模擬裡的實作:報告裡的 cell_id 就是「UE 去讀 SIB1 會讀到什麼」的真值。
用它不算作弊 —— 那正是這個程序在真實網路裡會得到的結果。可設失敗率模擬訊號
太弱讀不到 SIB1 的情況;失敗與否由 (serving, pci, arfcn) 的雜湊決定,**同參數重跑結果相同**
(規格要求決定性)。

預設關閉(env `ANR_PCI_LOOKUP`)。開啟會改變既有場景的 ANR 行為 ——
關係不再瞬間建立,要等解析成功,換手時機因而改變。
"""
from __future__ import annotations

import hashlib

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.utils.env_loader import get_bool, get_float, get_int
from main.utils.logger import get_logger

logger = get_logger(__name__)

# 判定結果
KNOWN = "known"
MISSING = "missing_neighbour"
CONFUSED = "pci_confusion"


def enabled() -> bool:
    return get_bool("ANR_PCI_LOOKUP", default=False)


def _resolve_fails(serving_cell: str, pci: int, arfcn: int) -> bool:
    """CGI 解析是否失敗。用雜湊而非亂數 —— 同一組參數重跑必須得到相同結果。"""
    rate = max(0.0, min(1.0, get_float("ANR_CGI_FAIL_RATE", default=0.0)))
    if rate <= 0.0:
        return False
    h = hashlib.sha1(f"{serving_cell}|{pci}|{arfcn}".encode()).digest()
    return (int.from_bytes(h[:2], "big") / 65535.0) < rate


_NOWRITE_AUDIT_AT: dict[str, object] = {}


def classify(serving_cell: str, pci: int | None, arfcn: int | None) -> tuple[str, list[str]]:
    """這個 (PCI, ARFCN) 在 serving 的鄰區關係表裡是什麼狀況。回 (判定, 命中的 target_cgi)。"""
    if pci is None:
        return KNOWN, []          # 舊 DU 沒帶 PCI → 不做判定,維持原行為
    q = NrCellRelation.objects.filter(source_cell_id=serving_cell, target_pci=int(pci))
    if arfcn is not None:
        # target_arfcn 為 0 是「舊資料沒填」,不當成不相符
        q = q.filter(target_arfcn__in=[int(arfcn), 0])
    hits = list(q.values_list("target_cgi", flat=True))
    if len(hits) == 1:
        return KNOWN, hits
    return (MISSING if not hits else CONFUSED), hits


def _audit(object_id: str, action: str, before: str, after: str, reason: str) -> None:
    """記進自主行為稽核 —— 對外的 I-6 cgi_resolution / I-7 都從這裡來。"""
    try:
        from main.apps.cu_cp.models.son_action_log import SonActionLog
        SonActionLog.objects.create(
            object_type="cgi_resolution", object_id=object_id, action=action,
            attribute="resolved_ncgi", before=before, after=after,
            function="anr_cgi", reason=reason, recorded_at=TimestampService.now())
    except Exception:  # noqa: BLE001 — 稽核失敗不該擋住解析
        logger.exception("CGI 解析稽核寫入失敗 %s", object_id)


def observe(serving_cell: str, neighbors: list[dict]) -> int:
    """量測報告的鄰區清單 → PCI 查表 → 需要時做 CGI 解析並建立關係。回新增筆數。

    neighbors 是 f1ap 的 neighbor_cells(每筆有 pci / arfcn / cell_id)。
    """
    if not serving_cell or not neighbors:
        return 0
    cap = get_int("ANR_NRT_CAPACITY", 32)
    used = NrCellRelation.objects.filter(source_cell_id=serving_cell).count()
    now = TimestampService.now()
    added = 0
    seen: set[tuple[int, int]] = set()

    for n in neighbors:
        pci, arfcn = n.get("pci"), n.get("arfcn")
        truth = n.get("cell_id") or ""
        if pci is None or not truth or truth == serving_cell:
            continue
        key = (int(pci), int(arfcn or 0))
        if key in seen:           # 同一個視窗同一個 PCI 只處理一次
            continue
        seen.add(key)

        verdict, hits = classify(serving_cell, pci, arfcn)
        if verdict == KNOWN:
            continue

        oid = f"{serving_cell}|pci{pci}@{arfcn}"
        if used + added >= cap:
            _audit(oid, "skip", "", "", f"{verdict};NRT 已達上限 {cap}")
            logger.warning("CGI 解析:%s 的 NRT 已達上限 %d,略過 PCI %s", serving_cell, cap, pci)
            continue
        if _resolve_fails(serving_cell, int(pci), int(arfcn or 0)):
            # 真實情況:訊號太弱 / 時間不夠,UE 讀不到 SIB1。關係建不起來,缺漏持續存在。
            _audit(oid, "fail", "", "", f"{verdict};UE 讀取 SIB1 失敗")
            logger.info("CGI 解析失敗:%s 回報 PCI %s(%s)", serving_cell, pci, verdict)
            continue

        tgt = CellConfig.objects.filter(cell_id=truth).first()
        if tgt is None:
            _audit(oid, "fail", "", "", f"{verdict};解析出的 cell 不在 CellConfig")
            continue
        # 2026-09-23:ANR 自主建立關閉時,解析出 CGI 也**不寫 NRT**(交給 xApp / 管理面決定)。
        # 以前這條路沒受 ANR_AUTO_ADD 管:anr_auto_add=0 的場次,外部 Agent 經 I-3 remove 一條
        # 關係,2.5 s 後這裡就自己加回去 —— 對方注入的題目被我方自主行為蓋掉。
        # 真實 gNB 的 ANR 關閉時,CGI 回報後同樣不會自行寫入 NRT。
        from main.apps.cu_cp.services.business import anr_auto
        if not anr_auto.enabled():
            # 不寫 NRT 的話每個視窗都會再解析一次;同一個 (cell, pci) 每 5 分鐘只記一筆稽核,
            # 否則 I-7 會被灌爆(run 38 實測 20 分鐘 7282 筆 son_function)。
            _last = _NOWRITE_AUDIT_AT.get(oid)
            if _last is None or (now - _last).total_seconds() >= 300:
                _NOWRITE_AUDIT_AT[oid] = now
                _audit(oid, "resolve", "", truth, f"{verdict};ANR_AUTO_ADD=0 → 已解析但不寫 NRT(交 xApp)")
                logger.info("CGI 解析成功但 ANR 自主建立關閉:%s 的 PCI %s → %s,不寫 NRT", serving_cell, pci, truth)
            continue
        _, created = NrCellRelation.objects.get_or_create(
            source_cell_id=serving_cell, target_cgi=truth,
            defaults={
                "target_pci": tgt.pci, "target_arfcn": int(arfcn or 0),
                "target_rat": "NR", "target_plmn": tgt.served_plmn,
                "is_ho_allowed": True, "is_remove_allowed": True, "is_xn_allowed": True,
                # 剛解析出來的關係還沒跑 Xn Setup
                "xn_x2_established": False, "ho_validated": False, "version": 1,
                "ho_blocklist": False, "no_remove": False, "xn_blocklist": False,
                "created_at": now, "updated_at": now,
            },
        )
        _audit(oid, "resolve", "", truth, verdict)
        if created:
            added += 1
            logger.info("CGI 解析成功:%s 的 PCI %s → %s(%s)", serving_cell, pci, truth, verdict)
            try:
                from main.apps.cu_cp.actors.anr_control_actor import _schedule_xn_setup
                _schedule_xn_setup(serving_cell, truth)
            except Exception:  # noqa: BLE001
                logger.exception("Xn Setup 排程失敗 %s → %s", serving_cell, truth)
    return added
