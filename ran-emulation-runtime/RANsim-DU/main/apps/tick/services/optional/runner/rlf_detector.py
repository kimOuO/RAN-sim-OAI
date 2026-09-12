"""RLF detector — per-UE 無線鏈路失敗判定(P1-1,2026-08-12)。

對齊 3GPP TS 38.331 §5.3.10 的 T310/N310/N311 精神(簡化版):
  - SINR < RLF_QOUT_SINR_DB(對齊 Qout「out-of-sync」門檻)持續累計 →
    連續 N310 次量測 out-of-sync → 啟動 T310 計時器
  - T310 期間 SINR 回到 > RLF_QIN_SINR_DB(Qin)連續 N311 次 → 復原(取消 T310)
  - T310 到期仍未復原 → 宣告 RLF

用 sim-time 計時(對齊 KPM window / 排程器,加速跑不失真)。
狀態機純記憶體 per-UE;tick loop 每 tick 對每個 CONNECTED UE 餵一次 observe()。
宣告 RLF 的 UE 由 caller(tick_runner)發 rlf_report 給 CU 並清出 registry。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from main.utils.env_loader import get_float, get_int
from main.utils.logger import get_logger

logger = get_logger(__name__)

# 門檻(env 可覆寫,劇本可依題型調靈敏度)
_QOUT_SINR_DB = get_float("RLF_QOUT_SINR_DB", -6.0)   # 低於此 = out-of-sync
_QIN_SINR_DB = get_float("RLF_QIN_SINR_DB", -4.0)     # 高於此 = in-sync(遲滯,避免抖動)
_N310 = get_int("RLF_N310", 2)                        # 連續 out-of-sync 幾次才起 T310
_N311 = get_int("RLF_N311", 2)                        # T310 中連續 in-sync 幾次算復原
_T310_MS = get_float("RLF_T310_MS", 1000.0)           # T310 sim-ms(38.331 預設 1000ms)
_ENABLED = get_int("RLF_ENABLED", 1)                  # 0 = 關(維持舊行為:UE 永不掉線)


@dataclass
class _UeRlfState:
    oos_count: int = 0          # 連續 out-of-sync 計數
    in_count: int = 0           # T310 中連續 in-sync 計數
    t310_active: bool = False
    t310_started_sim_ms: float = 0.0
    last_sinr: float = 0.0


class RlfDetector:
    """所有 UE 共用一個 detector。stateful,per-UE 狀態。"""

    def __init__(self) -> None:
        self._st: dict[str, _UeRlfState] = {}

    def reset(self) -> None:
        self._st.clear()

    def remove(self, ue_id: str) -> None:
        self._st.pop(ue_id, None)

    def observe(self, ue_id: str, sinr_db: float, now_sim_ms: float) -> dict[str, Any] | None:
        """餵一次量測。回傳 None(正常)或 RLF 宣告 dict(caller 據此上報 + 清 UE)。

        RLF dict: {ue_id, sinr_at_rlf, t310_ms, reason}
        """
        if not _ENABLED:
            return None
        st = self._st.get(ue_id)
        if st is None:
            st = _UeRlfState()
            self._st[ue_id] = st
        st.last_sinr = sinr_db

        if not st.t310_active:
            # 未在 T310:累計 out-of-sync
            if sinr_db < _QOUT_SINR_DB:
                st.oos_count += 1
                if st.oos_count >= _N310:
                    st.t310_active = True
                    st.t310_started_sim_ms = now_sim_ms
                    st.in_count = 0
                    logger.info("[RLF] ue=%s T310 started (sinr=%.1f < Qout=%.1f, %d oos)",
                                ue_id, sinr_db, _QOUT_SINR_DB, st.oos_count)
            else:
                st.oos_count = 0
            return None

        # T310 進行中
        if sinr_db > _QIN_SINR_DB:
            st.in_count += 1
            if st.in_count >= _N311:
                # 復原 — 取消 T310
                logger.info("[RLF] ue=%s T310 recovered (sinr=%.1f > Qin=%.1f)",
                            ue_id, sinr_db, _QIN_SINR_DB)
                st.t310_active = False
                st.oos_count = 0
                st.in_count = 0
            return None
        else:
            st.in_count = 0

        # 檢查 T310 是否到期
        if now_sim_ms - st.t310_started_sim_ms >= _T310_MS:
            logger.warning("[RLF] ue=%s RLF DECLARED (T310 %gms expired, sinr=%.1f)",
                           ue_id, _T310_MS, sinr_db)
            self._st.pop(ue_id, None)  # 宣告後清狀態(UE 將被移出 registry)
            return {
                "ue_id": ue_id,
                "sinr_at_rlf": round(sinr_db, 1),
                "t310_ms": _T310_MS,
                "reason": "T310_EXPIRY",
            }
        return None


_singleton: RlfDetector | None = None


def get_rlf_detector() -> RlfDetector:
    global _singleton
    if _singleton is None:
        _singleton = RlfDetector()
    return _singleton
