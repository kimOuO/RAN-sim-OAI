"""E2 Adapter Django app config.

Adapter 主功能不在 HTTP 層，而是長駐 SCTP loop（在 ready() 啟動 daemon thread）。
HTTP 端只是給 Dashboard / ops 看的 status / link control endpoints。
"""
from __future__ import annotations

import sys

from django.apps import AppConfig


def _is_serving_http() -> bool:
    """只在實際 HTTP server process 啟 SCTP loop。

    Django runserver 跟 migrate 是兩個 process，每個都會跑 AppConfig.ready()
    → 不過濾會啟兩個 SCTP thread 同時連 RIC（RIC 看成 duplicate gNB 把第一個踢掉）。
    Management commands (migrate/makemigrations/shell/test) 應該 skip。
    """
    if len(sys.argv) < 2:
        return False
    cmd = sys.argv[1]
    return cmd in ("runserver", "runworker") or cmd.endswith("daphne") or cmd.endswith("gunicorn")


class E2AdapterConfig(AppConfig):
    name = "main.apps.e2_adapter"

    def ready(self) -> None:
        # 只在 HTTP serving process 啟 SCTP loop（避免 migrate 也啟一個重複連 RIC）
        if not _is_serving_http():
            return
        from main.apps.e2_adapter.services.optional.sctp_link import sctp_loop
        sctp_loop.start_if_enabled()
