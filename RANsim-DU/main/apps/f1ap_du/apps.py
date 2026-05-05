from django.apps import AppConfig


class F1apDuConfig(AppConfig):
    name = "main.apps.f1ap_du"
    label = "f1ap_du"

    def ready(self) -> None:
        # 啟動時非阻塞觸發 F1Setup retry loop。
        # 真正執行延遲到 worker process 起來、env 讀完、protocol 可用之後。
        try:
            from main.apps.f1ap_du.services.optional.lifecycle.du_bootstrap import (
                start_bootstrap_in_background,
            )
        except Exception:
            return
        start_bootstrap_in_background()
