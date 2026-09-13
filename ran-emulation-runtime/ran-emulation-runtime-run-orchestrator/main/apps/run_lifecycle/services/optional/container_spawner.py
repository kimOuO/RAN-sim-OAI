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
ROLES = ("cu", "du", "ru", "ue", "e2adapter")   # e2adapter 走 host network(SCTP 綁 host IP),每 run 一條 association → RIC 看到一個 E2 node
_TEMPLATE = Path(__file__).with_name("per_run_template.json")
HEALTH_PATH = {"cu": "/api/v0.1/CU/E2/E2NodeId/read", "du": "/api/v0.1/DU/Tick/TickController/read", "ru": "/api/v0.1/RU/State/RuStateReader/read", "ue": "/api/v0.1/UE/Status/read", "e2adapter": "/api/v0.1/E2Adapter/Status/AdapterStatusReader/read"}
E2ADAPTER_PORT_BASE = 8400   # per-run adapter HTTP port = 8400 + 槽位(host network,要唯一)


def health_url(role: str, name: str, host_port: int | None) -> str:
    """host network 的 e2adapter 不在 ransim-net,從 orchestrator 走 host.docker.internal:port"""
    if role == "e2adapter":
        return f"http://host.docker.internal:{host_port}{HEALTH_PATH[role]}"
    return f"http://{name}:8000{HEALTH_PATH[role]}"


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


# ── E2 node 身分(RIC e2mgr 以 PLMN + gNB ID 推導 meid,兩個 run 同 ID 會互相覆蓋)──
# PLMN 固定 208/95;gNB ID 22-bit,基底 0x000e00(OAI 對齊),低 9 bit(0x001–0x1ff)當 run 槽位。
# RIC 端看到的 inventoryName = gnb_208_095_000e01 … gnb_208_095_000fff。
GNB_ID_BASE = 0x000e00
GNB_ID_SLOTS = 0x1ff


def gnb_id_hex_for_slot(slot: int) -> str:
    assert 1 <= slot <= GNB_ID_SLOTS
    return f"0x{(GNB_ID_BASE | slot) & 0x3fffff:06x}"


def e2_node_name(gnb_id_hex: str, mcc: str = "208", mnc: str = "95") -> str:
    return f"gnb_{mcc}_{mnc.zfill(3)}_{int(gnb_id_hex, 16):06x}"


def allocate_slot(used_gnb_id_hex: list[str]) -> int:
    used = {int(h, 16) & GNB_ID_SLOTS for h in used_gnb_id_hex if h}
    for k in range(1, GNB_ID_SLOTS + 1):
        if k not in used:
            return k
    raise RuntimeError("E2 node 槽位用完(同時最多 511 個 run)")


def spawn(scene_run_uuid: str, mode: str, gnb_id_hex: str | None = None, slot: int = 1, roles: tuple[str, ...] = ROLES, cu_host_port: int | None = None) -> dict[str, dict]:
    """起四個容器;回傳 {role: {name, container_id, host_port}}。已存在同名容器先移除(上次沒清乾淨)。"""
    rid = rid_of(scene_run_uuid); names = names_for(scene_run_uuid); tpl = _load_template()
    client = docker.from_env()
    subst = {**names, "db_cu": f"cu_{rid}", "db_du": f"du_{rid}", "db_ru": f"ru_{rid}", "cu_port": "0", "e2_port": str(E2ADAPTER_PORT_BASE + slot)}
    if "cu" in roles:
        create_databases(rid)
    out: dict[str, dict] = {}
    for role in roles:
        spec = tpl[role]
        if role == "e2adapter":
            subst["cu_port"] = str(cu_host_port or out["cu"]["host_port"])   # adapter 在 host network,經 CU 的 host port 打 per-run CU
        env = {k: v.format(**subst) if "{" in v else v for k, v in spec["env"].items()}
        env["SCENE_RUN_UUID"] = scene_run_uuid
        if role == "cu" and gnb_id_hex:
            env["GNB_ID_HEX"] = gnb_id_hex
        if role == "ru":
            env["RU_CHANNEL_MODE"] = mode
        vols = {v["source"]: {"bind": v["target"], "mode": "ro" if v["ro"] else "rw"} for v in spec["volumes"]}
        old = client.containers.list(all=True, filters={"name": f"^{names[role]}$"})
        for c in old:
            c.remove(force=True)
        host_net = spec.get("network_mode") == "host"
        net_kw = {"network_mode": "host"} if host_net else {"network": settings.PER_RUN_NETWORK, "ports": {"8000/tcp": None}, "hostname": names[role]}
        c = client.containers.run(spec["image"], name=names[role], detach=True, environment=env, volumes=vols, **net_kw,
                                  extra_hosts={h.split("=")[0]: h.split("=")[1] for h in (spec.get("extra_hosts") or [])} or None,
                                  command=spec.get("command"), labels={"ransim.scene_run_uuid": scene_run_uuid, "ransim.role": role})
        c.reload()
        port = int(subst["e2_port"]) if host_net else int(c.attrs["NetworkSettings"]["Ports"]["8000/tcp"][0]["HostPort"])
        out[role] = {"name": names[role], "container_id": c.id[:12], "host_port": port}
        logger.info("spawned %s (%s) host_port=%d", names[role], c.id[:12], port)
    return out


def wait_healthy(instances: dict[str, dict], timeout_sec: float = 300.0) -> dict[str, bool]:
    """等每個容器的 HTTP 起來(entrypoint 會先 migrate,CU/DU 約 20–60 s)。instances = {role: {name, host_port}}"""
    ok = {r: False for r in instances}; t0 = time.time()
    while time.time() - t0 < timeout_sec and not all(ok.values()):
        for r, inst in instances.items():
            if ok[r]:
                continue
            try:
                req = urllib.request.Request(health_url(r, inst["name"], inst.get("host_port")), data=b"{}", headers={"content-type": "application/json"})
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
