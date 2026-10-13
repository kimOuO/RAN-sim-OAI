"""目標 gNB 收下一個從別的 gNB 過來的 UE(Xn 換手、NG 換手、跨 gNB 重建共用)—— 多 gNB P6。

目標端要做的事(TS 38.423 §8.2.1 / 38.413 §8.4.2 的目標側):
  1. 允入判斷:目標 cell 在本 gNB、啟用中、沒被 barred
  2. 配本 gNB 的 RAN UE NGAP ID,建 UE context(服務 cell、所在 DU、流量設定、從哪裡來)
  3. 對目標 cell 所屬的 DU 送 F1 UE Context Setup(SpCell + DRB)
UE 真的「到了」之後(Xn:收到 SN Status Transfer;NG:由目標自己判定)再送 Path Switch / Handover Notify。
"""
from __future__ import annotations

from typing import Any

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.services.business.du_client_operations import DuClientBusinessService
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.apps.cu_cp.services.common.uuid_service import UUIDService
from main.apps.cu_cp.services.optional.f1ap.f1ap_handler import F1apHandler
from main.utils.logger import get_logger

logger = get_logger(__name__)


class AdmissionRejected(Exception):
    def __init__(self, cause: str, detail: str = ""):
        super().__init__(f"{cause}: {detail}")
        self.cause, self.detail = cause, detail


def drbs_for_profile(profile: dict | None) -> list[dict[str, Any]]:
    """UE 的承載:接入時 AMF 的 PDU session 一律建 DRB 1(5QI 9);流量設定可指定 bearer / 5QI。"""
    p = profile or {}
    return [{"drb_id": int(p.get("bearer_id", 1) or 1), "qos_5qi": int(p.get("qos_5qi", 9) or 9), "rlc_mode": "AM"}]


def check_target_cell(cell_id: str) -> CellConfig:
    from main.apps.cu_cp.services.common.fixture_state import is_cell_barred
    cell = CellConfig.objects.filter(cell_id=cell_id).first()
    if cell is None:
        raise AdmissionRejected("CellNotAvailable", f"{cell_id} not served by this gNB")
    if not cell.is_active:
        raise AdmissionRejected("CellNotAvailable", f"{cell_id} inactive")
    if is_cell_barred(cell.cell_id, bool(cell.is_barred)):
        raise AdmissionRejected("CellNotAvailable", f"{cell_id} barred")
    from main.apps.cu_cp.services.common.fixture_state import admission_blocked
    if admission_blocked(cell.cell_id, bool(cell.is_barred)):
        raise AdmissionRejected("CellNotAvailable", f"{cell_id} entering energy saving")
    return cell


def admit_incoming_ue(*, ue_id: str, target_cell: str, amf_ue_ngap_id: int | None, traffic_profile: dict | None,
                      source_gnb_id: int | None, source_cell: str, ho_uuid: str, via: str) -> dict[str, Any]:
    """允入並建好目標端的 UE context 與 DU 資源。回 {ran_ue_ngap_id, gnb_du_id}。失敗丟 AdmissionRejected。"""
    from main.apps.cu_cp.services.business import xn
    cell = check_target_cell(target_cell)
    now = TimestampService.now()
    ran = xn.ran_ue_ngap_id_for(ue_id)
    defaults = {
        "rrc_state": "CONNECTED", "serving_cell": cell.cell_id, "gnb_du_id": cell.served_by_du_id,
        "rrc_ue_id": ran, "ran_ue_ngap_id": ran, "traffic_profile_json": dict(traffic_profile or {}),
        "last_ho_source_gnb": source_gnb_id, "last_ho_source_cell": source_cell or "",
        "last_ho_uuid": ho_uuid or "", "last_ho_at": now, "updated_at": now,
    }
    if amf_ue_ngap_id:
        defaults["amf_ue_ngap_id"] = int(amf_ue_ngap_id)
    UeContext.objects.update_or_create(
        ue_id=ue_id, defaults=defaults,
        create_defaults={**defaults, "ue_uuid": UUIDService.generate_uuid("ue", ue_id), "created_at": now})
    resp = DuClientBusinessService.post_ue_context_setup(
        F1apHandler.build_ue_context_setup(ue_id, drbs_for_profile(traffic_profile), serving_cell_id=cell.cell_id),
        gnb_du_id=cell.served_by_du_id)
    from main.apps.cu_cp.services.business.du_client_operations import du_ok
    if not du_ok(resp):
        UeContext.objects.filter(ue_id=ue_id).update(rrc_state="IDLE", serving_cell="", updated_at=now)
        raise AdmissionRejected("RadioResourcesNotAvailable", f"DU UE Context Setup failed: {resp}")
    logger.info("UE %s admitted via %s → %s (DU#%s, ran_ue_ngap_id=%s, from gNB %s cell %s)",
                ue_id, via, cell.cell_id, cell.served_by_du_id, ran,
                f"0x{source_gnb_id:06x}" if source_gnb_id else "-", source_cell or "-")
    return {"ran_ue_ngap_id": ran, "gnb_du_id": cell.served_by_du_id}


def complete_arrival(ue_id: str, via: str) -> None:
    """UE 已到本 gNB:NG 關聯改到本 gNB(Xn → Path Switch;NG → Handover Notify),UE driver 改下行路由。"""
    from main.apps.cu_cp.services.business import amf_client, ue_notify
    ue = UeContext.objects.filter(ue_id=ue_id).first()
    if ue is None:
        return
    ue_notify.path_update(ue_id, ue.serving_cell)
    if not amf_client.enabled():
        return
    body = {"gnb_id": amf_client.gnb_id(), "ran_ue_ngap_id": int(ue.ran_ue_ngap_id),
            "amf_ue_ngap_id": int(ue.amf_ue_ngap_id), "cell_id": ue.serving_cell}
    try:
        if via == "NG":
            amf_client.post("handover_notify", body)
        else:
            ack = amf_client.post("path_switch_request", body)
            if ack.get("amf_ue_ngap_id"):
                UeContext.objects.filter(ue_id=ue_id).update(amf_ue_ngap_id=int(ack["amf_ue_ngap_id"]))
    except Exception as exc:  # noqa: BLE001 — AMF 回不來不影響無線側(UE 已在本 gNB)
        logger.warning("%s → AMF failed for %s: %s", "Handover Notify" if via == "NG" else "Path Switch", ue_id, exc)
