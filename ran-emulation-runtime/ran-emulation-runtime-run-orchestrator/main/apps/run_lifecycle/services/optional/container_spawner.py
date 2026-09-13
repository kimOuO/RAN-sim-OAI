"""per-run 容器(P4-1):每個 scene_run 起自己的 cu/du/ru/ue 四個容器 + 三個 DB。
容器規格來自 per_run_template.json(由 docker compose config 產生,host 名 / DB 名用 {cu} {db_cu} 佔位)。
- 名稱:{role}-{rid},rid = scene_run_uuid 後 8 碼;同一 docker network(PER_RUN_NETWORK)內用名稱互打
- DB:cu_{rid} / du_{rid} / ru_{rid},在 Postgres 上 CREATE,stop 時 DROP(計畫 §4.4「per-run schema,stop 即清乾淨」)
- host port:容器內 8000 → host 隨機 port(給監控前端),寫進 registry run_instance.host_port
- GNB_ID_HEX per run 不同 → 之後 E2Adapter 多 node 時 RIC 才分得開
- RU_CHANNEL_MODE 依 scene_run.mode;live 同時最多 1 個(計畫 §7-3)
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

import docker
import psycopg2
from django.conf import settings

from main.utils.logger import get_logger

logger = get_logger(__name__)
ROLES = ("cu", "du", "ru", "ue")
_TEMPLATE = Path(__file__).with_name("per_run_template.json")
HEALTH_PATH = {"cu": "/api/v0.1/CU/E2/E2NodeId/read", "du": "/api/v0.1/DU/Tick/TickController/read", "ru": "/api/v0.1/RU/State/RuStateReader/read", "ue": "/api/v0.1/UE/Status/read"}


def rid_of(scene_run_uuid: str) -> str:
    return scene_run_uuid[-8:]


def names_for(scene_run_uuid: str) -> dict[str, str]:
    rid = rid_of(scene_run_uuid)
    return {r: f"{r}-{rid}" for r in ROLES}


def _load_template() -> dict[str, Any]:
    return json.loads(_TEMPLATE.read_text())


def _pg_admin():
    conn = psycopg2.connect(host=settings.DB_HOST, port=settings.DATABASES["default"]["PORT"], user=settings.DATABASES["default"]["USER"],
                            password=settings.DATABASES["default"]["PASSWORD"], dbname=settings.PER_RUN_PG_ADMIN_DB)
    conn.autocommit = True
    return conn


def create_databases(rid: str) -> list[str]:
    names = [f"{r}_{rid}" for r in ("cu", "du", "ru")]
    conn = _pg_admin()   # 不能用 `with conn:`:那會開 transaction,CREATE DATABASE 不允許
    try:
        with conn.cursor() as cur:
            for n in names:
                cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (n,))
                if not cur.fetchone():
                    cur.execute(f'CREATE DATABASE "{n}" OWNER "{settings.DATABASES["default"]["USER"]}"')
    finally:
        conn.close()
    return names


def drop_databases(rid: str) -> None:
    conn = _pg_admin()
    try:
        with conn.cursor() as cur:
            for r in ("cu", "du", "ru"):
                n = f"{r}_{rid}"
                cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (n,))
                cur.execute(f'DROP DATABASE IF EXISTS "{n}"')
    finally:
        conn.close()


def _gnb_id_hex(rid: str) -> str:
    # 22-bit;OAI 對齊的 0xe00 為基底,per run 加一個 8-bit 位移(不同 run → 不同 E2 node id)
    return f"0x{(0x000e00 + (int(rid, 16) % 0xff) + 1) & 0x3fffff:06x}"


def spawn(scene_run_uuid: str, mode: str) -> dict[str, dict]:
    """起四個容器;回傳 {role: {name, container_id, host_port}}。已存在同名容器先移除(上次沒清乾淨)。"""
    rid = rid_of(scene_run_uuid); names = names_for(scene_run_uuid); tpl = _load_template()
    client = docker.from_env()
    subst = {**names, "db_cu": f"cu_{rid}", "db_du": f"du_{rid}", "db_ru": f"ru_{rid}"}
    create_databases(rid)
    out: dict[str, dict] = {}
    for role in ROLES:
        spec = tpl[role]
        env = {k: v.format(**subst) if "{" in v else v for k, v in spec["env"].items()}
        env["SCENE_RUN_UUID"] = scene_run_uuid
        if role == "cu":
            env["GNB_ID_HEX"] = _gnb_id_hex(rid)
        if role == "ru":
            env["RU_CHANNEL_MODE"] = mode
        vols = {v["source"]: {"bind": v["target"], "mode": "ro" if v["ro"] else "rw"} for v in spec["volumes"]}
        old = client.containers.list(all=True, filters={"name": f"^{names[role]}$"})
        for c in old:
            c.remove(force=True)
        c = client.containers.run(spec["image"], name=names[role], hostname=names[role], detach=True, environment=env, volumes=vols, network=settings.PER_RUN_NETWORK,
                                  ports={"8000/tcp": None}, extra_hosts={h.split("=")[0]: h.split("=")[1] for h in (spec.get("extra_hosts") or [])} or None,
                                  command=spec.get("command"), labels={"ransim.scene_run_uuid": scene_run_uuid, "ransim.role": role})
        c.reload()
        port = int(c.attrs["NetworkSettings"]["Ports"]["8000/tcp"][0]["HostPort"])
        out[role] = {"name": names[role], "container_id": c.id[:12], "host_port": port}
        logger.info("spawned %s (%s) host_port=%d", names[role], c.id[:12], port)
    return out


def wait_healthy(names: dict[str, str], timeout_sec: float = 300.0) -> dict[str, bool]:
    """等每個容器的 HTTP 起來(entrypoint 會先 migrate,CU/DU 約 20–60 s)。"""
    ok = {r: False for r in ROLES}; t0 = time.time()
    while time.time() - t0 < timeout_sec and not all(ok.values()):
        for r in ROLES:
            if ok[r]:
                continue
            try:
                req = urllib.request.Request(f"http://{names[r]}:8000{HEALTH_PATH[r]}", data=b"{}", headers={"content-type": "application/json"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    ok[r] = resp.status < 500
            except Exception:  # noqa: BLE001
                pass
        if not all(ok.values()):
            time.sleep(2)
    return ok


def container_status(scene_run_uuid: str) -> dict[str, str]:
    client = docker.from_env(); names = names_for(scene_run_uuid); st = {}
    for r, n in names.items():
        lst = client.containers.list(all=True, filters={"name": f"^{n}$"})
        st[r] = lst[0].status if lst else "absent"
    return st


def teardown(scene_run_uuid: str, drop_db: bool = True) -> dict[str, str]:
    client = docker.from_env(); names = names_for(scene_run_uuid); res = {}
    for r, n in names.items():
        for c in client.containers.list(all=True, filters={"name": f"^{n}$"}):
            try:
                c.stop(timeout=10)
            except Exception:  # noqa: BLE001
                pass
            c.remove(force=True); res[r] = "removed"
        res.setdefault(r, "absent")
    if drop_db:
        try:
            drop_databases(rid_of(scene_run_uuid)); res["db"] = "dropped"
        except Exception as exc:  # noqa: BLE001
            logger.warning("drop db failed %s: %s", scene_run_uuid, exc); res["db"] = f"error: {exc}"
    return res


def live_run_exists(exclude_uuid: str) -> bool:
    """live 模式同時最多 1 個:看有沒有別的 run 的 ru 容器在跑且 RU_CHANNEL_MODE=live。"""
    client = docker.from_env()
    for c in client.containers.list(filters={"label": "ransim.role=ru"}):
        if c.labels.get("ransim.scene_run_uuid") == exclude_uuid:
            continue
        env = dict(e.split("=", 1) for e in c.attrs["Config"]["Env"] if "=" in e)
        if env.get("RU_CHANNEL_MODE") == "live":
            return True
    return False
