"""通知 UE driver:UE 的服務 cell 變了(多 gNB,2026-09-27)。

UE driver 的流量產生器扮演核心網,下行 SDU 直接送進 UE 目前服務的 DU。UE 經換手(同 DU、
跨 DU、跨 gNB)或重建換了 cell 之後,下行資料的去處也要跟著換 —— 等同真實網路裡
CU-UP 切 F1-U 隧道 / AMF Path Switch 後 UPF 改送新的 gNB。

只在 env HTTP_UE_HOST 有設時送(per-run 容器);單一 DU 的舊部署不需要。
送出走單一背景執行緒、依序送(同一個 UE 連續換手兩次,順序不能顛倒);失敗只記 log ——
UE driver 還有 CU session 同步當後備。
"""
from __future__ import annotations

import queue
import threading

import requests

from main.utils.env_loader import get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)

_q: "queue.Queue[tuple[str, str]]" = queue.Queue(maxsize=10000)
_worker: threading.Thread | None = None
_guard = threading.Lock()
_session = requests.Session()


def _url() -> str:
    host = get_str("HTTP_UE_HOST", "")
    if not host:
        return ""
    return f"http://{host}:{get_str('HTTP_UE_PORT', '8000')}/api/v0.1/UE/UserPlane/path_update"


def _run() -> None:
    while True:
        ue_id, cell_id = _q.get()
        url = _url()
        if not url:
            continue
        try:
            _session.post(url, json={"ue_id": ue_id, "cell_id": cell_id}, timeout=3.0)
        except requests.RequestException as exc:
            logger.warning("path_update %s → %s failed: %s", ue_id, cell_id, exc)


def path_update(ue_id: str, cell_id: str) -> None:
    global _worker
    if not ue_id or not cell_id or not _url():
        return
    with _guard:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_run, name="ue-path-update", daemon=True)
            _worker.start()
    try:
        _q.put_nowait((ue_id, cell_id))
    except queue.Full:
        logger.warning("path_update queue full; drop %s → %s", ue_id, cell_id)
