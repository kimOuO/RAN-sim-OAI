"""Traffic generator — 依 UE traffic_profile 計算注 SDU 時序。

Patterns:
  - "idle":    不注
  - "cbr":     constant bitrate, 每 tick 一次 inject 大 SDU
                 bytes_per_tick = rate_mbps × elapsed_ms / 1000 / 8
  - "bursty":  (Phase C v2 才實作, v1 先支援 cbr/idle)

設計:
  manager 每 ~100ms tick 一次. 我們不為每個 1500B SDU 開一個 HTTP request
  (太慢, HTTP roundtrip ~10ms 主導 throughput), 而是**對齊真實 OAI** 一次
  把整個 tick 該注的 byte 量包成一個大 SDU 給 RLC. RLC entity 內部會自然
  segmentation 成多個 RLC PDU 給 PHY, 對最後 throughput / volume / delay
  量測沒影響.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from main.apps.ue_lifecycle.services import cu_client, du_client

logger = logging.getLogger(__name__)

# AL3 — re-sync 節流參數 (避免 DU 全死時 CU 被 update_traffic_profile spam)
_RESYNC_COOLDOWN_MS = 10_000   # 10 秒只能 re-sync 一次


def _batch_mode_enabled() -> bool:
    """AL: 讀 env INJECT_BATCH_MODE — 控制是否走 batch inject 路徑.

    on / true / 1 → 用 inject_sdu_batch (per-packet ts, 對齊 OAI)
    off / false / 0 / 未設 → 用舊 inject_sdu (single big SDU, 向後相容)
    """
    val = (os.environ.get("INJECT_BATCH_MODE") or "off").strip().lower()
    return val in ("on", "true", "1", "yes")


def _now_ms() -> int:
    return int(time.time() * 1000)


class UeTrafficGen:
    """Per-UE traffic state held inside UeThread / Manager."""

    def __init__(self, ue_id: str) -> None:
        self.ue_id = ue_id
        self.last_inject_at_ms = 0     # 上次成功 inject 的 wallclock
        self.profile: dict[str, Any] = {}
        self.injected_call_count = 0   # 對 DU /RLC/inject_sdu 呼叫總次數
        self.injected_bytes = 0        # 累計注入 byte 數
        self.last_resync_at_ms = 0     # AL3 — 上次因 no_entity 觸發 re-sync 的時間

    # 向後相容: monitor 用 injected_sdu_count 名稱
    @property
    def injected_sdu_count(self) -> int:
        return self.injected_call_count

    def update_profile(self, profile: dict[str, Any]) -> None:
        if profile != self.profile:
            self.profile = dict(profile or {})
            # reset 計時 — 換 profile 立即開始 (or 停)
            self.last_inject_at_ms = _now_ms()
            logger.info("UE[%s] traffic profile updated: %s", self.ue_id, self.profile)

    def tick(self) -> int:
        """每 manager tick 呼一次. 回傳本 tick inject 的 byte 數 (0 = idle / 還沒到時間)."""
        if not self.profile or self.profile.get("pattern") != "cbr":
            return 0
        rate_mbps = float(self.profile.get("rate_mbps", 0))
        if rate_mbps <= 0:
            return 0
        bearer_id = int(self.profile.get("bearer_id", 1))

        now = _now_ms()
        if self.last_inject_at_ms == 0:
            # 第一次 tick — 標記起點, 下次 tick 才注
            self.last_inject_at_ms = now
            return 0

        # AL: 先 clamp elapsed_ms — 防止 inject 持續失敗時 elapsed 無上限累積 (batch
        # mode 會把 elapsed_ms 直接送 window_ms 參數, 超過 60s 會被 DU 拒).
        # 1000ms 上限 = 即使一個 tick 拉長 10×, batch payload 也算合理範圍 (10×625KB = 6MB).
        elapsed_ms = now - self.last_inject_at_ms
        if elapsed_ms <= 0:
            return 0
        if elapsed_ms > 1000:
            logger.debug("UE[%s] clamp elapsed_ms %d → 1000", self.ue_id, elapsed_ms)
            elapsed_ms = 1000

        # 計算 elapsed window 內 CBR 該傳的 byte 量
        # bytes = rate_bps × elapsed_s / 8
        bytes_to_inject = int(rate_mbps * 1e6 * elapsed_ms / 1000 / 8)
        if bytes_to_inject <= 0:
            return 0

        # 安全閥: 防止 elapsed 過大 (system pause 之後 tick 重啟) 一次注幾百 MB
        max_per_tick = 10 * 1024 * 1024  # 10 MB
        if bytes_to_inject > max_per_tick:
            bytes_to_inject = max_per_tick

        if _batch_mode_enabled():
            # AL: batch mode — 拆 packet, per-packet ts_offset_us 線性散布, 對齊 OAI inject.
            sdu_size = int(self.profile.get("sdu_size", 1500))
            if sdu_size <= 0:
                sdu_size = 1500
            n_full = bytes_to_inject // sdu_size
            remainder = bytes_to_inject % sdu_size
            items: list[dict[str, Any]] = []
            total_pkts = n_full + (1 if remainder > 0 else 0)
            if total_pkts == 0:
                return 0
            window_us = elapsed_ms * 1000
            for i in range(n_full):
                items.append({
                    "sdu_bytes": sdu_size,
                    "ts_offset_us": int(window_us * i / total_pkts),
                })
            if remainder > 0:
                items.append({
                    "sdu_bytes": remainder,
                    "ts_offset_us": int(window_us * (total_pkts - 1) / total_pkts),
                })
            result = du_client.inject_sdu_batch(
                self.ue_id, items, window_ms=elapsed_ms, bearer_id=bearer_id,
            )
        else:
            result = du_client.inject_sdu(self.ue_id, bytes_to_inject, bearer_id=bearer_id)
        if result == "ok":
            self.injected_call_count += 1
            self.injected_bytes += bytes_to_inject
            self.last_inject_at_ms = now
            return bytes_to_inject

        # AL3 — DU 回 "RLC entity not found" (常見於 DU restart 後): 觸發 CU
        # update_traffic_profile 走 F1AP UE Context Setup 重建 RLC entity.
        # Cooldown 防止 spam.
        if result == "no_entity" and (now - self.last_resync_at_ms) > _RESYNC_COOLDOWN_MS:
            self.last_resync_at_ms = now
            logger.warning(
                "UE[%s] inject_sdu got 'RLC entity not found' — auto re-sync via CU",
                self.ue_id,
            )
            cu_client.update_traffic_profile(self.ue_id, self.profile)
            # 不更新 last_inject_at_ms — 下個 tick 再注 (此 tick 的 SDU drop)

        # inject 失敗 — 不更新 last_inject_at_ms, 下次 tick 再試 (累積 elapsed)
        return 0
