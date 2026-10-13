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
                _sync_statuses(log)
                for r in platform_clients.list_running_runs():
                    run = r["scene_run_uuid"]
                    # 多 gNB:實例鍵(cu-0、du-1、e2adapter-0…)取自容器 label;registry 的 run_instance 以 container_id 對回
                    ri_by_cid = {(i.get("container_id") or "")[:12]: i for i in platform_clients.list_run_instances(run)}
                    insts = {}
                    for c in container_spawner.run_containers(run):
                        role = c.labels.get("ransim.role") or ""
                        if role not in container_spawner.ROLES + ("amf",):
                            continue
                        key = c.labels.get("ransim.instance") or role
                        ri = ri_by_cid.get(c.id[:12]) or {}
                        insts[key] = {"role": role, "name": c.name, "host_port": ri.get("host_port"),
                                      "run_instance_uuid": ri.get("run_instance_uuid"), "container_id": c.id[:12],
                                      "gnb": c.labels.get("ransim.gnb") or "", "du": c.labels.get("ransim.du") or ""}
                    cu_keys = sorted(k for k, v in insts.items() if v["role"] == "cu")
                    e2_keys = sorted(k for k, v in insts.items() if v["role"] == "e2adapter")
                    cu_host = insts[cu_keys[0]]["name"] if settings.PER_RUN_ENABLED and cu_keys else None
                    e2_port = insts[e2_keys[0]]["host_port"] if settings.PER_RUN_ENABLED and e2_keys else None
                    topo = container_spawner.topology_of(run) if settings.PER_RUN_ENABLED else None
                    if topo is not None:
                        meids = {n.get("node_id"): n.get("meid") for n in (r.get("e2_nodes") or []) if isinstance(n, dict)}
                        arch_nodes = [{"node_id": g.name, "meid": meids.get(g.name) or "", "cu_host": g.cu_host,
                                       "e2_port": (insts.get(f"e2adapter-{g.e2_index}") or {}).get("host_port")} for g in topo.gnbs]
                        du0 = next((v["name"] for k, v in sorted(insts.items()) if v["role"] == "du"), None)
                        cu_archiver.start_archiver(run, int(r.get("sim_dt_ms") or 500), new_run=False, nodes=arch_nodes,
                                                   ue_host=(insts.get("ue") or {}).get("name"), du_host=du0)
                    else:
                        cu_archiver.start_archiver(run, int(r.get("sim_dt_ms") or 500), cu_host=cu_host, e2_port=e2_port, new_run=False)
                    if settings.PER_RUN_ENABLED and insts:
                        health_monitor.start_monitor(run, insts)
                    # 2026-09-22:外部 Agent 經 I-3 注入的事件也要接回 ——
                    # 排程器同樣是 in-process thread,不接回的話後面的事件永遠不會發生。
                    try:
                        from main.apps.agent_api.services.optional import event_scheduler
                        n = event_scheduler.resume(
                            run, cu_archiver.active_run_seq(run),
                            container_spawner.names_for(run))
                        if n:
                            log.info("resumed %d pending agent event(s) for run %s", n, run)
                    except Exception:  # noqa: BLE001 — 接不回不該擋住其他 run 的接回
                        log.exception("resume agent events failed for run %s", run)
                    log.info("resumed archiver/health for running run %s (cu=%s e2_port=%s)", run, cu_host, e2_port)
            except Exception:  # noqa: BLE001
                import logging
                logging.getLogger(__name__).exception("resume running runs failed")
        threading.Thread(target=_resume, name="resume-runs", daemon=True).start()

        # physics 的 GPU 掉了不會有人通知(2026-09-18 實遇),看門狗定期驗、連續失敗就重啟
        try:
            from main.apps.run_lifecycle.services.optional import physics_watchdog
            physics_watchdog.start()
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).exception("physics watchdog start failed")


def _sync_statuses(log) -> None:
    """場次狀態只有 idle / precomputing / running(2026-09-28)。orchestrator 起來時校正一次:
    - running 但容器已不在(orchestrator 當掉、主機重開)→ idle,last_result=failed
    - precomputing 但 precompute 容器已不在 → idle
    - 有預算快取檔、cache_path 卻是空的(舊劇本匯入)→ 補上 cache_path,前端「已預算」標籤才準"""
    from main.apps.run_lifecycle.services.optional import channel_cache, container_spawner, platform_clients
    try:
        for r in platform_clients.list_runs_by_status("running"):
            if not container_spawner.run_containers(r["scene_run_uuid"]):
                platform_clients.update_scene_run(r["scene_run_uuid"], status="idle", last_result="failed",
                                                  notes="orchestrator 重啟時容器已不在")
                log.warning("run %s 標記 running 但容器不在 → idle / failed", r["scene_run_uuid"])
        for r in platform_clients.list_runs_by_status("precomputing"):
            if (container_spawner.precompute_status(r["scene_run_uuid"]) or {}).get("state") in (None, "absent", "exited", "dead"):
                platform_clients.update_scene_run(r["scene_run_uuid"], status="idle")
        scenes = {s.get("scene_uuid"): s for s in (platform_clients.list_scenes() or {}).get("data") or []}
        for r in platform_clients.list_scene_runs().get("data") or []:
            sc = scenes.get(r.get("f_scene_uuid")) or {}
            if not r.get("cache_path") and channel_cache.available(sc):
                platform_clients.update_scene_run(r["scene_run_uuid"], cache_path=channel_cache.cache_path_for(sc))
                log.info("run %s 補上 cache_path(場景 %s 已有預算檔)", r["scene_run_uuid"], sc.get("name"))
    except Exception:  # noqa: BLE001 — 校正失敗不擋啟動
        log.exception("sync scene_run statuses failed")
