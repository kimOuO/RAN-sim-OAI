from django.apps import AppConfig


class F1apDuConfig(AppConfig):
    name = "main.apps.f1ap_du"
    label = "f1ap_du"

    def ready(self) -> None:
        # test / migrate / makemigrations / check / shell 等 management 指令
        # 不要去打 CU(會噴連線 warning)。
        import sys
        skip_cmds = {"test", "migrate", "makemigrations", "check", "shell", "collectstatic"}
        if any(c in sys.argv for c in skip_cmds) or "pytest" in sys.argv[0]:
            return
        try:
            from main.apps.f1ap_du.services.optional.lifecycle.du_bootstrap import (
                start_bootstrap_in_background,
            )
        except Exception:
            return
        start_bootstrap_in_background()
