"""RU 回報(CQI / CRC indication)的套用 —— HTTP 端點與 dl/ul_tti 回應本體共用。

2026-09-22:以前 RU 對每個 UE 各發一次同步 HTTP 回 DU,而 DU 是單 process,
tick 一忙 RU 就卡在等 DU、DU 又在等 RU 的 dl_tti 回應 —— 互等。DU 逾時後判 UE 為 RLF,
掉線重連再加重負載(走廊 30x 實測 10 分鐘 2035 次逾時、731 次假 RLF)。
其實 RU 的 dl_tti 回應本體早就帶了同一批 CQI;DU 直接從回應套用就不需要那條回呼。
把套用邏輯抽到這裡,端點保留給相容/除錯用,tick 路徑走回應本體。
"""
from __future__ import annotations

from typing import Any

from main.apps.mac.services.common.timestamp_service import TimestampService
from main.utils.env_loader import get_float
from main.utils.logger import get_logger

logger = get_logger(__name__)

_UL_LOG_N = 0
_LAYER_LOG_N = 0


def apply_cqi(v: dict[str, Any]) -> tuple[int, float]:
    """套用一筆已驗證的 CQI indication。回 (new_mcs, smoothed_bler)。"""
    global _UL_LOG_N, _LAYER_LOG_N
    # 延遲載入:tick_runner 也會走到這裡,模組頂層互相 import 會成環
    from main.apps.mac.services.optional.link_adaptation.mcs_controller import get_mcs_controller
    from main.apps.tick.services.optional.runner.tick_runner import get_tick_runner

    new_mcs, smoothed_bler = get_mcs_controller().update(
        v["ue_id"], v["sinr_db"], TimestampService.now_ms(),
    )
    rsrp_real = float(v.get("rsrp_dbm", -200.0))
    if rsrp_real > -150.0:
        rsrp_for_pm = rsrp_real
    else:
        rsrp_for_pm = get_float("DU_NOISE_FLOOR_DBM", -95.0) + float(v["sinr_db"])  # legacy fallback
    get_tick_runner().update_ue_sinr(
        v["ue_id"], float(v["sinr_db"]), rsrp_dbm=rsrp_for_pm, rank=v.get("rank"),
        sinr_layers=v.get("sinr_per_layer_db") or None, ul_sinr_db=v.get("ul_sinr_db"),
        pmi=v.get("pmi"), beam_id=v.get("beam_id"), array_gain_db=v.get("array_gain_db"),
        beam_top=v.get("beam_rsrp_top"), rsrq_db=v.get("rsrq_db"), cqi=v.get("cqi"))
    neighbors = v.get("neighbors") or []
    if neighbors:
        get_tick_runner().update_ue_neighbors(v["ue_id"], list(neighbors))
    logger.debug("CQI ind ue=%s sinr=%.1f cqi=%d → mcs=%d bler=%.3f rsrp=%.1f%s neighbors=%d rank=%s layers=%s",
                 v["ue_id"], v["sinr_db"], v["cqi"], new_mcs, smoothed_bler, rsrp_for_pm,
                 "" if rsrp_real > -150.0 else " (estimated)", len(neighbors), v.get("rank"), v.get("sinr_per_layer_db"))
    if v.get("ul_sinr_db") is not None:
        _UL_LOG_N += 1
        if _UL_LOG_N % 100 == 1:
            logger.debug("UL sinr ue=%s dl=%.1f ul=%.1f dB", v["ue_id"], v["sinr_db"], v["ul_sinr_db"])
    if v.get("rank", 1) > 1 and v.get("sinr_per_layer_db"):
        _LAYER_LOG_N += 1
        if _LAYER_LOG_N % 50 == 1:
            logger.info("MIMO cqi ue=%s rank=%d sinr=%.1f layers=%s", v["ue_id"], v["rank"], v["sinr_db"], v["sinr_per_layer_db"])
    return new_mcs, smoothed_bler


def apply_crc(v: dict[str, Any]):
    """套用一筆已驗證的 CRC indication(UL HARQ 回饋)。回 HARQ state 或 None。"""
    from main.apps.mac.services.optional.harq.harq_manager import get_harq_manager
    return get_harq_manager().handle_feedback(v["ue_id"], v["harq_pid"], "UL", v["success"])


def apply_from_response(body: dict[str, Any] | None, kind: str) -> int:
    """從 RU 的 dl_tti / ul_tti 回應本體套用 indication。回套用筆數。

    kind = "cqi"(dl_tti → data.cqi_indications)或 "crc"(ul_tti → data.crc_indications)。
    驗證走與 HTTP 端點同一個 serializer,壞資料一樣被擋。
    """
    from main.apps.fapi_north.serializers.fapi_message_serializers import (
        CqiIndicationSerializer, CrcIndicationSerializer,
    )
    data = (body or {}).get("data") or {}
    items = data.get("cqi_indications" if kind == "cqi" else "crc_indications") or []
    ser_cls, fn = (CqiIndicationSerializer, apply_cqi) if kind == "cqi" else (CrcIndicationSerializer, apply_crc)
    n = 0
    for it in items:
        ser = ser_cls(data=it)
        if not ser.is_valid():
            logger.warning("%s indication(回應本體)驗證失敗: %s", kind, ser.errors)
            continue
        try:
            fn(ser.validated_data)
            n += 1
        except Exception:  # noqa: BLE001 — 一筆壞不該讓整個 tick 的其他 UE 沒回報
            logger.exception("%s indication 套用失敗 ue=%s", kind, it.get("ue_id"))
    return n
