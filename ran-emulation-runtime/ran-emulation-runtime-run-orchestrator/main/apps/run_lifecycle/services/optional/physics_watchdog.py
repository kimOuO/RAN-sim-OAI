"""Physics GPU 看門狗(2026-09-19)。

2026-09-18 事故:physics 容器跑著跑著失去 GPU 存取權(容器內 `nvidia-smi` 回
`Failed to initialize NVML: Unknown Error`,主機端正常),沒有任何告警。
GPU 掉了之後 precompute / live / 覆蓋熱圖全部失效或悄悄退成 CPU,人沒發現就一直錯。

做法:週期打 physics 的 HealthChecker(它本來就回 `gpu.available`),連續數次不可用
就重啟 physics 容器。有每小時重啟上限,避免主機 GPU 真的壞掉時無限重啟。

env:
  PHYSICS_WATCHDOG_ENABLED        預設 on
  PHYSICS_WATCHDOG_SEC            檢查間隔,預設 60
  PHYSICS_WATCHDOG_FAILS          連續幾次不可用才重啟,預設 3
  PHYSICS_WATCHDOG_MAX_RESTARTS   每小時上限,預設 3
  PHYSICS_CONTAINER_NAME          預設 ransim-physics
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request

from main.utils.env_loader import get_bool, get_int, get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)

HEALTH_PATH = "/api/v0.1/Physics/RanSignal/HealthChecker/read"
_thread: threading.Thread | None = None
_lock = threading.Lock()
_restarts: list[float] = []


def _cfg() -> dict:
    return {
        "enabled": get_bool("PHYSICS_WATCHDOG_ENABLED", default=True),
        "period": get_int("PHYSICS_WATCHDOG_SEC", default=60),
        "fails": get_int("PHYSICS_WATCHDOG_FAILS", default=3),
        "max_restarts": get_int("PHYSICS_WATCHDOG_MAX_RESTARTS", default=3),
        "name": get_str("PHYSICS_CONTAINER_NAME", "ransim-physics"),
        "url": f"http://{get_str('HTTP_PHYSICS_HOST', 'physics')}:{get_int('HTTP_PHYSICS_PORT', 8000)}{HEALTH_PATH}",
    }


def probe(url: str, timeout: float = 5.0) -> tuple[bool, str]:
    """回 (GPU 可用?, 說明)。打不到 physics 不算 GPU 壞(可能只是在重啟)。"""
    try:
        req = urllib.request.Request(url, data=b"{}", headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode() or "{}")
            data = body.get("data") if isinstance(body, dict) else None
    except Exception as exc:  # noqa: BLE001
        return True, f"health 打不到({type(exc).__name__}),不判定"
    gpu = data.get("gpu") if isinstance(data, dict) else None   # 回應形狀不對 → 不判定(不是 GPU 的問題)
    if not isinstance(gpu, dict):
        return True, "health 回應沒有 gpu 欄位,不判定"
    if gpu.get("available"):
        return True, str(gpu.get("name") or "gpu")
    return False, str(gpu.get("error") or "gpu.available=false")


def _restart(name: str) -> bool:
    try:
        import docker
        c = docker.from_env().containers.get(name)
        c.restart(timeout=30)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("physics watchdog: 重啟 %s 失敗", name)
        return False


def _loop() -> None:
    cfg = _cfg()
    logger.info("physics GPU watchdog started (每 %d s,連續 %d 次不可用就重啟 %s)",
                cfg["period"], cfg["fails"], cfg["name"])
    bad = 0
    while True:
        time.sleep(max(10, cfg["period"]))
        cfg = _cfg()   # 每輪重讀,env 改了不用重啟 orchestrator
        if not cfg["enabled"]:
            continue
        ok, detail = probe(cfg["url"])
        if ok:
            if bad:
                logger.info("physics GPU 恢復:%s", detail)
            bad = 0
            continue
        bad += 1
        logger.warning("physics GPU 不可用(%d/%d):%s", bad, cfg["fails"], detail)
        if bad < cfg["fails"]:
            continue
        now = time.time()
        with _lock:
            _restarts[:] = [t for t in _restarts if now - t < 3600]
            if len(_restarts) >= cfg["max_restarts"]:
                logger.error("physics GPU 仍不可用,但 1 小時內已重啟 %d 次 → 停止自動重啟,請人工檢查主機 GPU",
                             len(_restarts))
                bad = 0
                continue
            _restarts.append(now)
        logger.error("physics GPU 連續 %d 次不可用 → 重啟 %s(%s)", bad, cfg["name"], detail)
        bad = 0
        if _restart(cfg["name"]):
            time.sleep(20)   # 給它時間起來,下一輪再驗


def start() -> None:
    global _thread
    if not get_bool("PHYSICS_WATCHDOG_ENABLED", default=True):
        return
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, name="physics-gpu-watchdog", daemon=True)
    _thread.start()
