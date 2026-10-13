"""gNB 自主 ANR(2026-09-20)—— 量測報告看到沒有鄰區關係的 cell 就自己補上。

真實 gNB 的 ANR:UE 回報一個不認得的 PCI → 要求 UE 讀該 cell 的 CGI → 建立關係。
我們的量測報告本來就帶 cell_id(等同已完成 PCI→CGI 解析),所以只差「建立關係」這一步。

**預設關閉**(env `ANR_AUTO_ADD`)。原因:跨 gNB 的鄰區關係是 xApp 經 E2 下 `anr-add`
的職責,也是 RIC 端 ANR use case 的驗證標的。開著跑會讓關係自己長出來,xApp 的控制
就看不出效果。單機、沒有 RIC 的情境才開。

與 anr_control_actor 的差別:那邊是 xApp 指定 PCI/ARFCN 要求解析後新增(有容量上限、
會落 ADD_REJECTED 事件);這裡是本地自主,同樣受容量上限約束,但不產生 RIC 控制稽核。
"""
from __future__ import annotations

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.utils.env_loader import get_bool, get_int
from main.utils.logger import get_logger

logger = get_logger(__name__)


def enabled() -> bool:
    return get_bool("ANR_AUTO_ADD", default=False)


def observe_neighbors(serving_cell: str, neighbor_cell_ids: list[str]) -> int:
    """量測報告裡的鄰區:沒有關係的就補一筆。回傳新增筆數(0 = 沒事發生)。"""
    if not serving_cell or not neighbor_cell_ids:
        return 0
    # 只為本 gNB 的 cell 建鄰區關係(NRT 屬於 cell 所在的 gNB)
    if not CellConfig.objects.filter(cell_id=serving_cell).exists():
        return 0
    targets = {c for c in neighbor_cell_ids if c and c != serving_cell}
    if not targets:
        return 0
    known = set(
        NrCellRelation.objects.filter(source_cell_id=serving_cell, target_cgi__in=targets)
        .values_list("target_cgi", flat=True)
    )
    missing = sorted(targets - known)
    if not missing:
        return 0

    cap = get_int("ANR_NRT_CAPACITY", 32)
    used = NrCellRelation.objects.filter(source_cell_id=serving_cell).count()
    now = TimestampService.now()
    rows = {c.cell_id: c for c in CellConfig.objects.filter(cell_id__in=missing)}
    from main.apps.cu_cp.actors.anr_control_actor import _cell_ident
    from main.apps.cu_cp.services.business import xn
    added = 0
    for cgi in missing:
        if used + added >= cap:
            logger.warning("自主 ANR:%s 的 NRT 已達上限 %d,略過 %s", serving_cell, cap, cgi)
            break
        # 多 gNB:目標可以是本 gNB 或 Xn 鄰居 gNB 的 cell(Xn Setup 交換過 served cells 才認得)
        ident = _cell_ident(cgi)
        if ident is None:    # 量測報告帶了我們不認識的 cell —— 沒有 CGI 可解析,跳過
            logger.warning("自主 ANR:量測回報了未知 cell %s(不在本 gNB,也不在 Xn 鄰居),不建立關係", cgi)
            continue
        tgt = rows.get(cgi)
        plmn = tgt.served_plmn if tgt is not None else (getattr(xn.foreign_cell(cgi), "plmn", "") or "")
        _, created = NrCellRelation.objects.get_or_create(
            source_cell_id=serving_cell, target_cgi=cgi,
            defaults={
                "target_pci": ident[0], "target_arfcn": ident[1],
                "target_rat": "NR", "target_plmn": plmn,
                "is_ho_allowed": True, "is_remove_allowed": True, "is_xn_allowed": True,
                # 自主學到的關係尚未經過 Xn 建立,與 seed_from_cells 的同 gNB 關係不同
                "xn_x2_established": False, "ho_validated": False, "version": 1,
                "ho_blocklist": False, "no_remove": False, "xn_blocklist": False,
                "created_at": now, "updated_at": now,
            },
        )
        if created:
            added += 1
            logger.info("自主 ANR:新增鄰區關係 %s → %s(來源:UE 量測報告)", serving_cell, cgi)
            # 記進自主行為稽核 —— 外部 Agent 的 I-7 要靠它分辨「對方注入的事件」與
            # 「我方自己動的」。只寫 log 的話,對方刻意留空的鄰區被我方補上就查不出來。
            try:
                from main.apps.cu_cp.models.son_action_log import SonActionLog
                SonActionLog.objects.create(
                    object_type="neighbour_relation", object_id=f"{serving_cell}>{cgi}",
                    action="add", attribute="exists", before="false", after="true",
                    function="anr_auto", reason="UE 量測報告回報了未建立關係的鄰區", recorded_at=now)
            except Exception:  # noqa: BLE001 — 稽核寫不進去不該擋住關係建立
                logger.exception("自主 ANR:稽核寫入失敗 %s → %s", serving_cell, cgi)
            # 關係建立後還要跑 Xn Setup,否則換手會以 TXnRELOCprepExpiry 失敗。
            # 重用 xApp anr-add 用的同一條路徑(背景延遲、建反向關係、雙向標記 Xn 已建立),
            # 行為與經 RIC 新增的關係一致。
            try:
                from main.apps.cu_cp.actors.anr_control_actor import _schedule_xn_setup
                _schedule_xn_setup(serving_cell, cgi)
            except Exception:  # noqa: BLE001 — Xn 排程失敗不該中斷其餘關係的建立
                logger.exception("自主 ANR:排程 Xn Setup 失敗 %s → %s", serving_cell, cgi)
    return added
