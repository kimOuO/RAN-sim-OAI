"""Omniverse Kit HTTP client — 寫 UE 視覺化位置。

Kit endpoint: POST /ue/{name}/move {x, y, z}
最佳 effort, 失敗不影響 RAN 模擬

★ 非阻塞節流發佈(latest-wins)★
背景:Kit 的 HTTP server 與每幀 Python 工作共搶同一把 GIL。trajectory loop
以 6 UE × 10Hz = 60 req/s 同步直打 Kit 時:
  (1) Kit 卡頓會反過來拖住整個 UE 迴圈(每個呼叫最多 1.5s timeout);
  (2) 60 req/s 的請求處理本身就是 GIL 壓力,把 Kit HTTP 擠到間歇性餓死。

改成:
  trajectory loop → publish()  只更新「每個 UE 的最新位置」快照(微秒級,不阻塞)
  單一背景 worker → 每 _MIN_INTERVAL_SEC 取最新快照批次推 Kit(≈3Hz/UE)

latest-wins 無佇列:Kit 慢時中間格被最新值覆蓋丟棄 —— 3D 顯示的永遠是
「現在的位置」,更新變疏但不會回放舊軌跡、不會執行緒爆量、天然有序。
RAN 模擬走 ru_client,與此完全無關。
"""
from __future__ import annotations

import logging
import threading
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Kit 卡住時不要佔住 worker — 寧可丟這格,下一輪推最新的
_TIMEOUT_SEC = 0.4
# worker 每輪最小間隔 → 每 UE 約 3Hz。Kit 端請求量從 60/s 降到 ~20/s。
_MIN_INTERVAL_SEC = 0.3


class _KitPositionPublisher:
    """每個 UE 只保留最新位置,由單一背景執行緒節流推送(latest-wins)。"""

    def __init__(self) -> None:
        self._latest: dict[str, tuple[float, float, float]] = {}
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        # 可觀測性:dropped 高=Kit 跟不上(視覺變疏,模擬不受影響);failed 高=Kit 掛
        self.sent = 0
        self.dropped = 0
        self.failed = 0

    def publish(self, ue_id: str, x: float, y: float, z: float) -> None:
        """非阻塞:只寫入最新位置快照,立即返回。"""
        with self._lock:
            if ue_id in self._latest:
                self.dropped += 1
            self._latest[ue_id] = (x, y, z)
        self._wake.set()
        self._ensure_worker()

    def _ensure_worker(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="kit-pos-publisher", daemon=True
        )
        self._thread.start()

    def _drain_once(self) -> None:
        with self._lock:
            batch = self._latest
            self._latest = {}
        for ue_id, (x, y, z) in batch.items():
            if _post_move(ue_id, x, y, z):
                self.sent += 1
            else:
                self.failed += 1

    def _run(self) -> None:
        while True:
            self._wake.wait(timeout=1.0)
            self._wake.clear()
            try:
                self._drain_once()
            except Exception:  # noqa: BLE001
                logger.exception("kit position publisher drain failed")
            time.sleep(_MIN_INTERVAL_SEC)

    def stats(self) -> dict[str, int]:
        return {"sent": self.sent, "dropped": self.dropped, "failed": self.failed}


_publisher = _KitPositionPublisher()


def _post_move(ue_id: str, x: float, y: float, z: float) -> bool:
    base = settings.OMNIVERSE_KIT_URL.rstrip('/')
    url = f"{base}/ue/{ue_id}/move"
    try:
        r = requests.post(url, json={"x": x, "y": y, "z": z}, timeout=_TIMEOUT_SEC)
        return r.ok
    except requests.RequestException:
        # Kit 可能沒跑 / 正在卡 — 不算 error,下一輪推最新位置即可
        return False


def move_ue(ue_id: str, x: float, y: float, z: float) -> bool:
    """非阻塞節流發佈 UE 位置給 Kit(視覺化用)。永遠立即返回。"""
    _publisher.publish(ue_id, x, y, z)
    return True


def move_ue_sync(ue_id: str, x: float, y: float, z: float) -> bool:
    """同步推送(舊行為)。只在確實需要等 Kit 確認時使用。"""
    return _post_move(ue_id, x, y, z)


def publisher_stats() -> dict[str, int]:
    return _publisher.stats()
