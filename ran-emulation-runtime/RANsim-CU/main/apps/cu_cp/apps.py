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

            try:
                from main.apps.cu_cp.services.optional.mobility import (
                    a3_handover_calculation as _a3,
                )
                if _a3.load_persisted_override():
                    import logging
                    c = _a3.get_a3_config()
                    logging.getLogger(__name__).warning(
                        "[a3] 還原劇本覆寫 enabled=%s offset=%s hys=%s",
                        c.enabled, c.offset_db, c.hys_db)
            except Exception:
                import logging
                logging.exception("Failed to restore A3 override")

            _resume_anr_fixture()


def _resume_anr_fixture() -> None:
    """CU 啟動時把中斷的病徵時間軸接回來。

    時間軸跑在 CU 容器內,CU 重啟就跟著死。2026-08-26 第 6 題因此死在等待步驟,
    最後由人手動補完最後一步 —— 那一輪的「無人值守」就不能算數。
    這裡讀進度檔續跑,並把該步驟已經過的時間帶過去(否則 300 秒的維運等待
    會在每次重啟後從頭算起,節奏就跟劇本宣告的不一樣了)。

    多個 worker 都會執行 ready(),重複啟動由時間軸自己的互斥鎖擋掉,
    這裡不另外判斷 —— 兩處各判一次,遲早會不一致。
    """
    import json
    import logging
    import os
    import subprocess
    import time

    import sys
    # 只有「伺服器行程」該續跑 —— 這個 hook 在每個 Django 行程的 ready() 都會跑,
    # 包括 manage.py shell / 一次性命令:2026-08-29 Q5r2 實錄,prepare 自己的
    # shell 啟動先把舊時間軸復活,清理永遠追不上復活(殭屍家族第四員:
    # 復活鉤 vs 清理者)。shell/命令行程一律不續跑。
    argv = " ".join(sys.argv)
    if ("runserver" not in argv and "daphne" not in argv
            and "runworker" not in argv and "gunicorn" not in argv
            and "manage.py" in argv):
        return
    # 抑制閥:prepare 清場期間豎旗,任何行程都不得續跑
    if os.path.exists("/app/tmp/anr_fixture.suppress"):
        return
    path = "/app/tmp/anr_fixture.progress.json"
    try:
        with open(path) as f:
            p = json.load(f)
    except (OSError, ValueError):
        return                                  # 沒有中斷的時間軸,正常情形
    sid = p.get("scenario")
    step = int(p.get("step") or 1)
    elapsed = max(0.0, time.time() - float(p.get("step_started") or 0))
    if not sid:
        return
    try:
        subprocess.Popen(
            ["python", "/app/manage.py", "anr_fixture", sid,
             "--from-step", str(step), "--resume-elapsed", f"{elapsed:.0f}"],
            stdout=open("/app/tmp/fixture_resume.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,             # 不隨這個 worker 一起被收掉
            env={**os.environ},
        )
        logging.getLogger(__name__).warning(
            "[fixture] 續跑 %s 第 %d 步(該步已過 %.0fs)", sid, step, elapsed)
    except OSError:
        logging.getLogger(__name__).exception("[fixture] 續跑啟動失敗")
