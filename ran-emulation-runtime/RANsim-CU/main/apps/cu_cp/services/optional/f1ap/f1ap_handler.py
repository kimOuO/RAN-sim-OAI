"""F1AP CU-side procedural helpers.

OAI ref:
  - openair2/F1AP/f1ap_cu_interface_management.c (CU_handle_F1_SETUP_REQUEST L89)
  - openair2/F1AP/f1ap_cu_rrc_message_transfer.c (CU_handle_UL_RRC_MESSAGE_TRANSFER L97)

These functions wrap dataclass conversion + transport. Database writes are
done by the calling Actor through SqlDbBusinessService.
"""
from __future__ import annotations

from typing import Any


class F1apHandler:
    @staticmethod
    def build_f1_setup_response(transaction_id: int, accepted: bool = True) -> dict[str, Any]:
        return {"transaction_id": transaction_id, "accepted": accepted}

    @staticmethod
    def build_dl_rrc_message_transfer(ue_id: str, rrc_msg_b64: str) -> dict[str, Any]:
        return {"ue_id": ue_id, "rrc_msg_b64": rrc_msg_b64}

    @staticmethod
    def build_ue_context_setup(
        ue_id: str,
        drbs: list[dict[str, Any]],
        rrc_msg_b64: str = "",
        serving_cell_id: str = "",
    ) -> dict[str, Any]:
        # serving_cell_id 對齊 OAI F1AP UE Context Setup Request 的 SpCell_ID IE：
        # CU-CP RRC 是 serving cell 唯一 source of truth，這裡帶下去通知 DU 該 UE 服務在哪個 cell。
        return {
            "ue_id": ue_id,
            "drbs": drbs,
            "rrc_message_b64": rrc_msg_b64,
            "serving_cell_id": serving_cell_id,
        }

    @staticmethod
    def build_ue_context_modification(
        ue_id: str, target_cell: str, rrc_msg_b64: str = "",
    ) -> dict[str, Any]:
        return {
            "ue_id": ue_id,
            "target_cell": target_cell,
            "rrc_message_b64": rrc_msg_b64,
        }
