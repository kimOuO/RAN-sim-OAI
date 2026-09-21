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
import re
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
PER_RUN_LOG_TAIL = int(getattr(settings, "PER_RUN_LOG_TAIL", 200000))   # 每個容器留最後這麼多行
HEALTH_PATH = {"cu": "/api/v0.1/CU/E2/E2NodeId/read", "du": "/api/v0.1/DU/Tick/TickController/read", "ru": "/api/v0.1/RU/State/RuStateReader/read", "ue": "/api/v0.1/UE/Status/read", "e2adapter": "/api/v0.1/E2Adapter/Status/AdapterStatusReader/read"}
# 2026-09-16 記憶體事故後:每個 per-run 容器都要有上限,洩漏時只 OOM 掉那一顆(restart policy 會拉回來),
# 不會把整台 VM 拖進 swap 卡死。memswap 設同值 = 不准用 swap。可用 RUN_MEM_LIMIT_<ROLE> 覆寫(docker 格式,如 1g)。
MEM_LIMIT_DEFAULT = {"cu": "1g", "du": "1g", "ru": "2g", "ue": "512m", "e2adapter": "512m"}


def mem_limit_for(role: str) -> str:
    return os.environ.get(f"RUN_MEM_LIMIT_{role.upper()}", MEM_LIMIT_DEFAULT.get(role, "1g"))


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


def _free_host_port() -> int:
    """向 OS 要一個目前空閒的 host port(bind 0 再放掉;與 docker 分配間有極短競態,實務可接受)。"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0)); return int(s.getsockname()[1])


PORT_RETRIES = 5


def _port_conflict(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "address already in use" in msg or "port is already allocated" in msg


# ── DU 設定:registry 的 du_config_template(+ du.config_override)→ DU 容器 env(2026-09-19)──
# 以前 DU 全吃自己的 env 預設,registry 上的 DU 模板等於裝飾品(改了不生效)。
_SCHEDULER_ENV = {"pf": "PF", "rr": "RR", "max_thp": "MAXTHROUGHPUT"}


def du_env_from_template(tpl_cfg: dict | None, override: dict | None = None) -> dict[str, str]:
    """DU 模板欄位 → DU 認得的 env。沒給的欄位不注入(DU 用自己的預設)。"""
    cfg = {**(tpl_cfg or {}), **(override or {})}
    env: dict[str, str] = {}
    m = {"n_prb": "SIM_DEFAULT_PRB_PER_CELL", "min_prb": "SCHED_MIN_PRB", "pf_alpha": "PF_ALPHA",
         "target_bler": "TARGET_BLER", "rlc_discard_timer_ms": "SLOT_DISCARD_TIMER_MS",
         "rlc_tx_maxsize_bytes": "RLC_TX_MAXSIZE_BYTES", "harq_max_retx": "HARQ_MAX_RETX"}
    for k, e in m.items():
        if cfg.get(k) is not None:
            env[e] = str(cfg[k])
    if cfg.get("harq_max_retx") is not None:
        env["RLC_MAX_RETX"] = str(cfg["harq_max_retx"])
    if cfg.get("qos_gbr_first") is not None:
        env["QOS_GBR_FIRST"] = "on" if cfg["qos_gbr_first"] else "off"
    if cfg.get("scheduler"):
        env["SIM_SCHEDULER"] = _SCHEDULER_ENV.get(str(cfg["scheduler"]).lower(), "PF")
    if cfg.get("numerology") is not None:   # 每個 frame 的 slot 數 = 10×2^μ
        env["SIM_SLOTS_PER_FRAME"] = str(10 * 2 ** int(cfg["numerology"]))
    if cfg.get("tdd_pattern"):              # 例 "DDDDDDDSUU" → UL 佔比(S 算半個)
        pat = str(cfg["tdd_pattern"]).upper()
        n = len(pat) or 1
        ul = (pat.count("U") + 0.5 * pat.count("S")) / n
        env["TDD_UL_SLOT_RATIO"] = f"{ul:.3f}"
    return env


def spawn(scene_run_uuid: str, mode: str, gnb_id_hex: str | None = None, slot: int = 1, roles: tuple[str, ...] = ROLES, cu_host_port: int | None = None,
          du_env: dict[str, str] | None = None, cu_env: dict[str, str] | None = None) -> dict[str, dict]:
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
        # run 唯一 cell 標籤 = gNB ID 低 12 bit(與 RIC 看到的 E2 node 同源);UE loader 加、DU/RU 轉 tx 名時剝
        env["CELL_ID_TAG"] = f"{(GNB_ID_BASE | slot) & 0xfff:03x}"
        if role == "ru":
            env["RU_CHANNEL_MODE"] = mode
        if role == "du" and du_env:
            env.update(du_env)   # registry DU 模板 → DU 行為(排程器、PRB、BLER 目標…)
        if role == "cu" and cu_env:
            env.update(cu_env)   # run knob → CU 行為(目前:anr_auto_add)
        if role in ("du", "ru"):
            env["CHANNEL_MODE_FILE"] = f"/data/channel_cache/.mode.{rid}"   # per-run 交接檔,不共用 .mode
        vols = {v["source"]: {"bind": v["target"], "mode": "ro" if v["ro"] else "rw"} for v in spec["volumes"]}
        old = client.containers.list(all=True, filters={"name": f"^{names[role]}$"})
        for c in old:
            c.remove(force=True)
        host_net = spec.get("network_mode") == "host"
        # host port 明確綁定(而非 None 隨機):docker restart 後 port 不變,adapter 的 SIM_CU_URL / registry host_port 才不會失效(2026-09-15 事故)
        # _free_host_port 挑完到 docker 綁定之間,port 可能被別的程式搶走(2026-09-18 實遇 address already in use)→ 換 port 重試
        for attempt in range(PORT_RETRIES):
            net_kw = {"network_mode": "host"} if host_net else {"network": settings.PER_RUN_NETWORK, "ports": {"8000/tcp": _free_host_port()}, "hostname": names[role]}
            try:
                c = client.containers.run(spec["image"], name=names[role], detach=True, environment=env, volumes=vols, **net_kw,
                                          mem_limit=mem_limit_for(role), memswap_limit=mem_limit_for(role),
                                          restart_policy={"Name": "unless-stopped"},   # OOM 被砍後自己回來
                                          cap_add=["SYS_PTRACE"],   # 2026-09-15 CU 卡死抓不到堆疊:給 py-spy dump 用
                                          extra_hosts={h.split("=")[0]: h.split("=")[1] for h in (spec.get("extra_hosts") or [])} or None,
                                          command=spec.get("command"), labels={"ransim.scene_run_uuid": scene_run_uuid, "ransim.role": role})
                break
            except docker.errors.APIError as exc:
                if host_net or attempt == PORT_RETRIES - 1 or not _port_conflict(exc):
                    raise
                logger.warning("spawn %s: host port 衝突,換 port 重試(%d/%d):%s", names[role], attempt + 1, PORT_RETRIES, exc)
                for c in client.containers.list(all=True, filters={"name": f"^{names[role]}$"}):
                    c.remove(force=True)
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


def _dump_logs(c, role: str, scene_run_uuid: str) -> None:
    """移除容器前把 log 落地。2026-09-20:RIC 回報一場排查期間 e01 斷線重連 24 次,
    我們收工時容器已被移除、log 一併消失,完全無法事後追。每個 run 留一份。"""
    d = Path(settings.PER_RUN_LOG_DIR) / rid_of(scene_run_uuid)
    try:
        d.mkdir(parents=True, exist_ok=True)
        data = c.logs(tail=PER_RUN_LOG_TAIL)
        (d / f"{role}.log").write_bytes(data)
    except Exception as exc:  # noqa: BLE001 — 留不下 log 不該擋收工
        logger.warning("dump logs failed %s/%s: %s", scene_run_uuid, role, exc)


def teardown(scene_run_uuid: str, drop_db: bool = True) -> dict[str, str]:
    client = docker.from_env(); names = names_for(scene_run_uuid); res = {}
    for r, n in names.items():
        for c in client.containers.list(all=True, filters={"name": f"^{n}$"}):
            _dump_logs(c, r, scene_run_uuid)
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


# ── 預算(precompute)獨立容器(2026-09-14)──────────────────────────
# 以前 precompute 是 `docker exec` 進共用 physics 容器跑,physics 一重啟就死。改成每個 run 一個一次性容器
# `precompute-<rid>`(同 physics image、同 bind mount、要 GPU),跑完 orchestrator 把 registry scene_run 標 ready。
def precompute_name(scene_run_uuid: str) -> str:
    return f"precompute-{rid_of(scene_run_uuid)}"


def spawn_precompute(scene_run_uuid: str, scenario_id: str, segment_ticks: int = 10000,
                     solver_env: dict | None = None) -> dict:
    """solver_env:射線追蹤旋鈕覆寫(SIM_DIFFUSE_REFLECTION / SIM_SAMPLES_PER_SRC /
    SIM_MAX_DEPTH)。給設定實驗用;不帶就是 physics 模板的既有值。"""
    tpl = _load_template()["physics"]; client = docker.from_env(); name = precompute_name(scene_run_uuid)
    for c in client.containers.list(all=True, filters={"name": f"^{name}$"}):
        c.remove(force=True)
    env = dict(tpl["env"]); env["SCENARIO_STORE_URL"] = f"http://{settings.HTTP_REGISTRY_HOST}:{settings.HTTP_REGISTRY_PORT}"; env["SCENE_RUN_UUID"] = scene_run_uuid
    for k, v in (solver_env or {}).items():
        env[str(k)] = str(v)
    vols = {v["source"]: {"bind": v["target"], "mode": "ro" if v["ro"] else "rw"} for v in tpl["volumes"]}
    c = client.containers.run(tpl["image"], name=name, detach=True, environment=env, volumes=vols, network=settings.PER_RUN_NETWORK,
                              command=["sh", "/app/precompute/run_precompute_segmented.sh", scenario_id, str(int(segment_ticks))],
                              device_requests=[docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])],
                              extra_hosts={h.split("=")[0]: h.split("=")[1] for h in (tpl.get("extra_hosts") or [])} or None,
                              labels={"ransim.scene_run_uuid": scene_run_uuid, "ransim.role": "precompute", "ransim.scenario_id": scenario_id})
    logger.info("spawned %s for scenario %s", name, scenario_id)
    return {"name": name, "container_id": c.id[:12], "scenario_id": scenario_id}


_PROG_RE = re.compile(r"\[precompute\] (\d+)/(\d+) \(([0-9.]+)%\) rate=([0-9.]+) t/s ETA=(\d+)s")


def precompute_status(scene_run_uuid: str) -> dict:
    client = docker.from_env(); name = precompute_name(scene_run_uuid)
    lst = client.containers.list(all=True, filters={"name": f"^{name}$"})
    if not lst:
        return {"state": "absent"}
    c = lst[0]; c.reload()
    # 進度在 run_precompute_segmented.sh 寫的 log 檔(不是 stdout);orchestrator 以唯讀 bind mount 讀同一個目錄
    sid = c.labels.get("ransim.scenario_id") or ""
    tail = ""
    try:
        with open(f"{settings.PRECOMPUTE_LOG_DIR}/{sid}.precompute.log", "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()[-400:]
            tail = "".join(lines)
    except OSError:
        tail = c.logs(tail=400).decode("utf-8", "replace")
    prog = None
    for m in _PROG_RE.finditer(tail):
        prog = {"tick": int(m.group(1)), "total": int(m.group(2)), "pct": float(m.group(3)), "rate_tps": float(m.group(4)), "eta_sec": int(m.group(5))}
    done = "[precompute] DONE" in tail or "status=ready" in tail
    exit_code = c.attrs.get("State", {}).get("ExitCode")
    return {"state": c.status, "exit_code": exit_code, "done": done, "progress": prog, "scenario_id": c.labels.get("ransim.scenario_id"),
            "last_lines": [l for l in tail.strip().splitlines()[-3:]]}


def stop_precompute(scene_run_uuid: str) -> str:
    client = docker.from_env(); name = precompute_name(scene_run_uuid)
    for c in client.containers.list(all=True, filters={"name": f"^{name}$"}):
        c.remove(force=True); return "removed"
    return "absent"
