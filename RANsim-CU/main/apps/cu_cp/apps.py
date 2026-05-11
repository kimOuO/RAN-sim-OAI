"""CU-CP app config — control plane (RRC, F1AP CU side, NGAP, E1AP)."""
import os

from django.apps import AppConfig


class CuCpConfig(AppConfig):
    name = "main.apps.cu_cp"
    label = "cu_cp"
    verbose_name = "CU Control Plane"

    def ready(self) -> None:
        # 啟動 E2 Indication producer（WebSocket push 用）
        # 防止 Django runserver auto-reload 重複啟動：只在 main process 開
        if os.environ.get("RUN_MAIN") == "true" or os.environ.get("RUN_MAIN") is None:
            try:
                from main.apps.cu_cp.services.optional.e2 import indication_producer
                indication_producer.start()
            except Exception:
                import logging
                logging.exception("Failed to start E2 indication producer")
