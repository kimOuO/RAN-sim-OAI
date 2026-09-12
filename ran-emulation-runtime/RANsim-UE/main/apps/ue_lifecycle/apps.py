"""UeLifecycle AppConfig — 啟動背景 thread 拉 CU UE list + 管 per-UE thread."""
from __future__ import annotations

import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class UeLifecycleConfig(AppConfig):
    name = "main.apps.ue_lifecycle"
    label = "ue_lifecycle"
    verbose_name = "UE Lifecycle Manager"

    def ready(self) -> None:
        # 防止 runserver auto-reload 重複起 thread
        if os.environ.get("RUN_MAIN") and os.environ.get("RUN_MAIN") != "true":
            return
        try:
            from main.apps.ue_lifecycle.services.manager import get_manager
            get_manager().start()
        except Exception:
            logger.exception("Failed to start UeLifecycleManager")
