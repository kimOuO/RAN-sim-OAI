"""Traffic generator — 依 UE traffic_profile 計算注 SDU 時序。

Patterns:
  - "idle":      不注
  - "cbr":       constant bitrate, 每 tick 一次 inject 大 SDU
                   bytes_per_tick = rate_mbps × elapsed_ms / 1000 / 8
  - "piecewise": rate 依 sim-time 段切換,scenario 用
                   profile = {
                     pattern: "piecewise",
                     schedule: [[t_sec, dl_kbps], ...],  # sim-second
                     sim_speed_x: 1.0,                    # wallclock → sim-time 倍率
                     bearer_id?: 1,
                   }
                   tick 時用 (wallclock_elapsed × sim_speed_x) 查 schedule 找對應 rate
  - "bursty":    (Phase C v2 才實作)

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

from main.apps.ue_lifecycle.services import cu_client, du_client, sim_speed

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
        self.profile_installed_at_ms = 0  # update_profile 時設,piecewise 算 sim-time elapsed 用
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
            now = _now_ms()
            self.last_inject_at_ms = now
            self.profile_installed_at_ms = now
            logger.info("UE[%s] traffic profile updated: %s", self.ue_id, self.profile)

    def _effective_sim_speed_x(self) -> float:
        """P1 (2026-06-01) — 注入量該用的 sim_speed_x。

        過去直接用 profile 設定值(例如 10),但 DU 實際只跑到 achieved(例如 6.7),
        造成 10/6.7 ≈ 1.49× 慢性過量注入。改讀 DU 實際達成倍速;尚未量到(0.0,剛
        啟動)或拉不到時 fallback 回設定值。3x 無漂移時 achieved == 設定 → 行為不變。
        """
        configured = float(self.profile.get("sim_speed_x", 1.0) or 1.0)
        achieved = sim_speed.get_achieved_speed()
        return achieved if achieved > 0.1 else configured

    def _current_rate_mbps(self, now_ms: int) -> float:
        """Resolve effective rate_mbps for this tick based on pattern.

        cbr        → profile.rate_mbps
        piecewise  → schedule lookup at sim-elapsed (= wallclock_elapsed × sim_speed_x)
        其他       → 0
        """
        pattern = self.profile.get("pattern")
        if pattern == "cbr":
            return float(self.profile.get("rate_mbps", 0) or 0)
        if pattern == "piecewise":
            schedule = self.profile.get("schedule") or []
            if not schedule:
                return 0.0
            sim_speed_x = self._effective_sim_speed_x()  # P1 — 用實際達成,非設定值
            elapsed_sim_sec = (now_ms - self.profile_installed_at_ms) / 1000.0 * sim_speed_x
            if elapsed_sim_sec < float(schedule[0][0]):
                return 0.0
            kbps = 0.0
            for entry in schedule:
                if not entry:
                    continue
                if float(entry[0]) <= elapsed_sim_sec:
                    kbps = float(entry[1]) if len(entry) > 1 else 0.0
                else:
                    break
            return kbps / 1000.0
        return 0.0

    def _current_ul_rate_mbps(self, now_ms: int) -> float:
        """最小可用 UL:讀 piecewise schedule 第 3 欄 ul_kbps([t, dl_kbps, ul_kbps])。
        沒第 3 欄 → 0(向後相容只給 DL 的舊劇本)。cbr 用 profile['ul_rate_mbps']。"""
        pattern = self.profile.get("pattern")
        if pattern == "cbr":
            return float(self.profile.get("ul_rate_mbps", 0) or 0)
        if pattern == "piecewise":
            schedule = self.profile.get("schedule") or []
            if not schedule:
                return 0.0
            sim_speed_x = self._effective_sim_speed_x()
            elapsed_sim_sec = (now_ms - self.profile_installed_at_ms) / 1000.0 * sim_speed_x
            if elapsed_sim_sec < float(schedule[0][0]):
                return 0.0
            kbps = 0.0
            for entry in schedule:
                if not entry:
                    continue
                if float(entry[0]) <= elapsed_sim_sec:
                    kbps = float(entry[2]) if len(entry) > 2 else 0.0
                else:
                    break
            return kbps / 1000.0
        return 0.0

    def tick(self) -> int:
        """每 manager tick 呼一次. 回傳本 tick inject 的 byte 數 (0 = idle / 還沒到時間)."""
        if not self.profile or self.profile.get("pattern") not in ("cbr", "piecewise"):
            return 0
        rate_mbps = self._current_rate_mbps(_now_ms())
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

        # 2026-05-23 bugfix: rate_mbps 是 sim-time 的速率(對齊 OAI KPM 報的是 sim-time),
        # 但 elapsed_ms 是 wall-clock 流逝;在 sim_speed_x > 1 時 sim-time 流逝 = wall × x。
        # 若直接用 wall elapsed,inject rate 在 sim-time 上會被縮小 sim_speed_x 倍 →
        # PRB% / avg throughput 偏低、RLC delay 偏高。乘 sim_speed_x 還原 sim-time 等效量。
        # P1 (2026-06-01): 用「實際達成」倍速而非設定值 — 設定 10 但 DU 只跑 6.7 時,
        # 用設定值會多灌 1.49× 造成 buffer/delay/throughput 失真。見 sim_speed.py。
        sim_speed_x = self._effective_sim_speed_x()
        elapsed_sim_ms = elapsed_ms * sim_speed_x

        # 最小可用 UL:同窗算 UL 需求 bytes 推給 DU(DU 用 UL 時隙容量 drain → 真 ThpUl/PrbUl/VolUL)
        ul_rate_mbps = self._current_ul_rate_mbps(now)
        if ul_rate_mbps > 0:
            ul_bytes = int(ul_rate_mbps * 1e6 * elapsed_sim_ms / 1000 / 8)
            if ul_bytes > 0:
                try:
                    du_client.report_ul_traffic(self.ue_id, ul_bytes)
                except Exception:  # noqa: BLE001 — UL 報失敗不擋 DL inject
                    pass

        # 計算 elapsed window 內 CBR 該傳的 byte 量
        # bytes = rate_bps × elapsed_sim_s / 8
        bytes_to_inject = int(rate_mbps * 1e6 * elapsed_sim_ms / 1000 / 8)
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
