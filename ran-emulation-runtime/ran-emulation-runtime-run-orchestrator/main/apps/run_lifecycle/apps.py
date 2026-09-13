import sys

from django.apps import AppConfig


def _is_serving() -> bool:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    return cmd in ("runserver",) or any(k in sys.argv[0] for k in ("gunicorn", "daphne"))


class RunLifecycleConfig(AppConfig):
    name = "main.apps.run_lifecycle"
    default_auto_field = "django.db.models.AutoField"

    def ready(self) -> None:
        """orchestrator 重啟後,執行中 run 的 archiver / 健康輪詢是 in-process thread,會跟著消失;
        這裡從 registry 找 status=running 的 run 接回來(P4-2 之後 per-run 容器仍在跑)。"""
        if not _is_serving():
            return
        import threading

        def _resume():
            import time
            time.sleep(3)
            try:
                from django.conf import settings
                from main.apps.run_lifecycle.services.optional import container_spawner, health_monitor, platform_clients
                from main.apps.run_telemetry_archive.services.optional import cu_archiver
                from main.utils.logger import get_logger
                log = get_logger(__name__)
                for r in platform_clients.list_running_runs():
                    run = r["scene_run_uuid"]
                    insts = {i["role"]: {"name": container_spawner.names_for(run)[i["role"]], "host_port": i.get("host_port"), "run_instance_uuid": i["run_instance_uuid"], "container_id": i.get("container_id")} for i in platform_clients.list_run_instances(run) if i["role"] in container_spawner.ROLES}
                    cu_host = insts["cu"]["name"] if settings.PER_RUN_ENABLED and "cu" in insts else None
                    e2_port = insts["e2adapter"]["host_port"] if settings.PER_RUN_ENABLED and "e2adapter" in insts else None
                    cu_archiver.start_archiver(run, int(r.get("sim_dt_ms") or 500), cu_host=cu_host, e2_port=e2_port)
                    if settings.PER_RUN_ENABLED and insts:
                        health_monitor.start_monitor(run, insts)
                    log.info("resumed archiver/health for running run %s (cu=%s e2_port=%s)", run, cu_host, e2_port)
            except Exception:  # noqa: BLE001
                import logging
                logging.getLogger(__name__).exception("resume running runs failed")
        threading.Thread(target=_resume, name="resume-runs", daemon=True).start()
