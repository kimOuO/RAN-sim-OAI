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
import time
from typing import Any

from main.apps.ue_lifecycle.services import du_client

logger = logging.getLogger(__name__)


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

        elapsed_ms = now - self.last_inject_at_ms
        if elapsed_ms <= 0:
            return 0

        # 計算 elapsed window 內 CBR 該傳的 byte 量
        # bytes = rate_bps × elapsed_s / 8
        bytes_to_inject = int(rate_mbps * 1e6 * elapsed_ms / 1000 / 8)
        if bytes_to_inject <= 0:
            return 0

        # 安全閥: 防止 elapsed 過大 (system pause 之後 tick 重啟) 一次注幾百 MB
        max_per_tick = 10 * 1024 * 1024  # 10 MB
        if bytes_to_inject > max_per_tick:
            bytes_to_inject = max_per_tick

        if du_client.inject_sdu(self.ue_id, bytes_to_inject, bearer_id=bearer_id):
            self.injected_call_count += 1
            self.injected_bytes += bytes_to_inject
            self.last_inject_at_ms = now
            return bytes_to_inject
        # inject 失敗 — 不更新 last_inject_at_ms, 下次 tick 再試 (累積 elapsed)
        return 0
