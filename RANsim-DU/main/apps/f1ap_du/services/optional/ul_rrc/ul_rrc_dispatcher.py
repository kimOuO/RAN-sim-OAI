"""UL RRC outbound — DU 收到 UE 送來的 RRC PDU,轉成 UlRrcMessageTransfer 推給 CU。

對齊 OAI:
  - openair2/F1AP/f1ap_du_rrc_message_transfer.c
  - DU_send_INITIAL_UL_RRC_MESSAGE_TRANSFER  (RA Msg3 attaching CCCH SRB0 PDU)
  - DU_send_UL_RRC_MESSAGE_TRANSFER          (connected 後 SRB1/2 PDU)

兩種輸入:
  - bytes:  原始 RRC PDU,我們 base64 encode 後送
  - str:    已 base64 編碼,先 validate 再送(invalid 直接 raise)
"""
from __future__ import annotations

import base64

from ran_sim_protocol.f1ap import UlRrcMessageTransfer

from main.apps.f1ap_du.services.business.cu_client_operations import CuClientBusinessService
from main.apps.f1ap_du.services.optional.message_codec.f1ap_codec import encode_ul_rrc
from main.utils.logger import get_logger

logger = get_logger(__name__)


class UlRrcDispatcher:
    """DU → CU 上行 RRC 轉發。"""

    @staticmethod
    def to_b64(rrc_msg: bytes | str) -> str:
        if isinstance(rrc_msg, bytes):
            return base64.b64encode(rrc_msg).decode("ascii")
        if isinstance(rrc_msg, str):
            try:
                base64.b64decode(rrc_msg, validate=True)
            except Exception as e:
                raise ValueError(f"invalid base64: {e}") from e
            return rrc_msg
        raise TypeError(f"rrc_msg must be bytes or str, got {type(rrc_msg).__name__}")

    @staticmethod
    def dispatch(ue_id: str, rrc_msg: bytes | str, *, timeout: float = 3.0) -> bool:
        """送 UL RRC PDU 給 CU,回傳 CU 是否回 200。"""
        if not ue_id:
            raise ValueError("ue_id is required")
        rrc_b64 = UlRrcDispatcher.to_b64(rrc_msg)
        msg = UlRrcMessageTransfer(ue_id=ue_id, rrc_msg_b64=rrc_b64)
        ok = CuClientBusinessService.post_ul_rrc_message(encode_ul_rrc(msg), timeout=timeout)
        logger.info("UL RRC dispatch ue=%s b64_len=%d ok=%s", ue_id, len(rrc_b64), ok)
        return ok
