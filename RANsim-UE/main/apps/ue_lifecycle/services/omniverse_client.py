"""Omniverse HTTP client — 把 UE 位置同步寫回 Omniverse 後端,讓 3D view 動起來。

Scene Editor 路徑(/editor)是直接呼叫這個 batch_move 寫 UE 位置;劇本端走
scenario_driver 時也用這條,讓劇本跑時 3D view 跟著 UE 移動。
"""
from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 2.0
# 連線復用:scenario_driver 高倍率下每 tick 對 Omniverse 推位置,需要避免 TCP handshake
_session = requests.Session()


def list_ues_in_db() -> list[str]:
    """GET 目前 Omniverse Django DB 裡的 UE name list。失敗回 []。"""
    url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/UE/UEReader/read"
    try:
        r = _session.post(url, json={}, timeout=_TIMEOUT_SEC)
        if not r.ok:
            return []
        data = r.json().get("data", [])
        return [u.get("name") for u in data if u.get("name")]
    except (requests.RequestException, ValueError):
        return []


def create_ue(name: str) -> bool:
    """POST UEController/create — idempotent,UE 已存在會回 4xx,當 success 處理。

    帶 preset_id="female_office" 對齊前端 ObjectForm 路徑 — 這樣 backend serializer 會:
      - 從 UsdAsset 表查到 usd_path = /app/assets/UE/female_office.usda
      - 套用 PRESET_TARGET_HEIGHTS["female_office"] = 50.0 (跟前端 UE 等高,
        不會比較矮 — 否則 Kit fallback 用 34m 預設)
    """
    url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/UE/UEController/create"
    try:
        r = _session.post(
            url,
            json={"name": name, "preset_id": "female_office"},
            timeout=_TIMEOUT_SEC,
        )
        return r.ok or r.status_code == 409 or "already" in r.text.lower()
    except requests.RequestException as exc:
        logger.warning("omniverse create_ue %s failed: %s", name, exc)
        return False


def delete_ue(name: str) -> bool:
    """POST UEController/delete — 刪 stray UE."""
    url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/UE/UEController/delete"
    try:
        r = _session.post(url, json={"name": name}, timeout=_TIMEOUT_SEC)
        return r.ok
    except requests.RequestException as exc:
        logger.warning("omniverse delete_ue %s failed: %s", name, exc)
        return False


def trigger_scene_build() -> bool:
    """POST SceneController/build — 把 DB 當下狀態推給 Kit(同步 prim list)。"""
    url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/Scene/SceneController/build"
    try:
        r = _session.post(url, json={}, timeout=_TIMEOUT_SEC)
        return r.ok
    except requests.RequestException as exc:
        logger.warning("omniverse scene_build failed: %s", exc)
        return False


def list_buildings_in_db() -> list[str]:
    """GET Omniverse DB 內 building name list。失敗回 []。"""
    url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/Scene/BuildingController/read"
    try:
        r = _session.post(url, json={}, timeout=_TIMEOUT_SEC)
        if not r.ok:
            return []
        data = r.json().get("data", [])
        return [b.get("name") for b in data if b.get("name")]
    except (requests.RequestException, ValueError):
        return []


def upsert_building(spec: dict[str, Any]) -> bool:
    """create_or_update building by name。spec 必含 name,其餘 position/size/color/rot
    都是 optional。無條件帶 preset_id="brownstone01" → backend 自動套 Brownstone01 USD。

    遇到 name 已存在時走「delete → create」而不是 update,理由:
      BuildingWriteSerializer._validate_update 只 patch 顯式給的欄位,不會去 preset
      取 default_size / default_rotation;只有 _validate_write(走 create)會在 size/
      rotation 沒傳時用 preset 預設填補。要讓劇本完全參照 brownstone01 預設大小/旋轉
      (跟前端 /editor Build 同條路徑),就必須走 create。
    建築在 sim 期間不移動,delete+create 對畫面只會閃一下,可接受。
    """
    name = spec.get("name")
    if not name:
        return False
    body = {**spec, "preset_id": "brownstone01"}  # 統一 USD,跟前端 ObjectForm 路徑一致
    create_url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/Scene/BuildingController/create"
    try:
        r = _session.post(create_url, json=body, timeout=_TIMEOUT_SEC)
        if r.ok:
            return True
        # 已存在 → 先 delete 再 create,讓 preset 預設覆蓋舊紀錄
        if r.status_code in (400, 409) or "exist" in r.text.lower() or "unique" in r.text.lower():
            delete_building(name)
            r2 = _session.post(create_url, json=body, timeout=_TIMEOUT_SEC)
            if r2.ok:
                return True
            logger.warning(
                "omniverse re-create building %s after delete failed: %d %s",
                name, r2.status_code, r2.text[:200],
            )
        else:
            logger.warning("omniverse create building %s failed: %d %s", name, r.status_code, r.text[:200])
        return False
    except requests.RequestException as exc:
        logger.warning("omniverse upsert_building %s failed: %s", name, exc)
        return False


def delete_building(name: str) -> bool:
    url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/Scene/BuildingController/delete"
    try:
        r = _session.post(url, json={"name": name}, timeout=_TIMEOUT_SEC)
        return r.ok
    except requests.RequestException as exc:
        logger.warning("omniverse delete_building %s failed: %s", name, exc)
        return False


def sync_buildings_to_scenario(scenario_buildings: list[dict[str, Any]]) -> dict[str, int]:
    """把 Omniverse 建築對齊到劇本(強制對齊,與 UE 的 sync_scene_to_scenario 一致):
      - 在 DB 但不在劇本的建築 → delete(含上一場殘留、前端手動建的)
      - 在劇本但不在 DB 的 → upsert
      - 劇本沒帶 buildings(空 list)→ wanted 為空 → 清空所有建築
    最後一律 Scene/build 讓 Kit 反映。這樣「跑無建築劇本 → 3D 就沒建築」。
    傳入 [{name, position:[x,y,z], size:[x,y,z], color, rotation_xyz_deg, material, ...}]
    """
    scenario_buildings = scenario_buildings or []
    existing = set(list_buildings_in_db())
    wanted_names = {b["name"] for b in scenario_buildings}
    to_del = existing - wanted_names

    n_del = 0
    for name in to_del:
        if delete_building(name):
            n_del += 1
    n_up = 0
    for b in scenario_buildings:
        if upsert_building(b):
            n_up += 1
    trigger_scene_build()
    logger.info(
        "sync_buildings_to_scenario: upserted=%d deleted=%d (wanted=%s)",
        n_up, n_del, sorted(wanted_names),
    )
    return {"upserted": n_up, "deleted": n_del}


def list_gnbs_in_db() -> list[str]:
    """GET 目前 Omniverse DB 裡的 gNB name list。失敗回 []。"""
    url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/GNB/GNBReader/read"
    try:
        r = _session.post(url, json={}, timeout=_TIMEOUT_SEC)
        if not r.ok:
            return []
        data = r.json().get("data", [])
        return [g.get("name") for g in data if g.get("name")]
    except (requests.RequestException, ValueError):
        return []


def upsert_gnb(spec: dict[str, Any]) -> bool:
    """create_or_update gNB by name。spec 應有:
       name, position:[x,y,z], frequency_ghz, bandwidth_mhz, power_dbm, active, cells:[...]
    先 create,409 已存在則 update。
    """
    name = spec.get("name")
    if not name:
        return False
    create_url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/GNB/GNBController/create"
    update_url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/GNB/GNBController/update"
    try:
        r = _session.post(create_url, json=spec, timeout=_TIMEOUT_SEC)
        if r.ok:
            return True
        # 已存在 → update
        if r.status_code in (400, 409) or "exist" in r.text.lower() or "unique" in r.text.lower():
            ur = _session.post(update_url, json=spec, timeout=_TIMEOUT_SEC)
            if ur.ok:
                return True
            logger.warning("omniverse update gnb %s failed: %d %s", name, ur.status_code, ur.text[:200])
        else:
            logger.warning("omniverse create gnb %s failed: %d %s", name, r.status_code, r.text[:200])
        return False
    except requests.RequestException as exc:
        logger.warning("omniverse upsert_gnb %s failed: %s", name, exc)
        return False


def delete_gnb(name: str) -> bool:
    url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/GNB/GNBController/delete"
    try:
        r = _session.post(url, json={"name": name}, timeout=_TIMEOUT_SEC)
        return r.ok
    except requests.RequestException as exc:
        logger.warning("omniverse delete_gnb %s failed: %s", name, exc)
        return False


def sync_gnbs_to_scenario(scenario_gnbs: list[dict[str, Any]]) -> dict[str, int]:
    """如果劇本帶 gnbs 設定,把 Omniverse DB 拓樸對齊到那組。
    傳入 scenario_gnbs = [{name, position:[x,y,z], frequency_ghz, bandwidth_mhz,
                          power_dbm, active, cells:[{cell_id, pci, azimuth_deg}], ...}]
    沒帶 gnbs 的劇本 → 不動 Omniverse(回 {}),保留現有拓樸。
    """
    if not scenario_gnbs:
        return {}
    existing = set(list_gnbs_in_db())
    wanted_names = {g["name"] for g in scenario_gnbs}
    to_del = existing - wanted_names

    n_del = 0
    for name in to_del:
        if delete_gnb(name):
            n_del += 1
    n_up = 0
    for g in scenario_gnbs:
        if upsert_gnb(g):
            n_up += 1
    trigger_scene_build()
    logger.info(
        "sync_gnbs_to_scenario: upserted=%d deleted=%d (wanted=%s)",
        n_up, n_del, sorted(wanted_names),
    )
    return {"upserted": n_up, "deleted": n_del}


def sync_scene_to_scenario(scenario_ue_names: list[str]) -> dict[str, int]:
    """同步 Omniverse scene UE list 到 scenario.ues:
      - 在 DB 但不在 scenario 的 UE → delete(包含 demo_xxx、其他劇本殘留)
      - 在 scenario 但不在 DB 的 → create
      - 最後 Scene/build → Kit 重建 prim

    回傳 {"deleted": N, "created": M, "kept": K} for logging。
    """
    existing = set(list_ues_in_db())
    wanted = set(scenario_ue_names)
    to_del = existing - wanted
    to_add = wanted - existing
    kept = existing & wanted

    n_del = 0
    for name in to_del:
        if delete_ue(name):
            n_del += 1
    n_add = 0
    for name in to_add:
        if create_ue(name):
            n_add += 1

    # 即使沒人變動也 build 一次 — 確保 Kit 的 prim 跟 DB 一致
    trigger_scene_build()

    logger.info(
        "sync_scene_to_scenario: deleted=%d created=%d kept=%d (wanted=%s)",
        n_del, n_add, len(kept), sorted(wanted),
    )
    return {"deleted": n_del, "created": n_add, "kept": len(kept)}


def ingest_signals(signals: list[dict[str, Any]], session_uuid: str | None = None) -> bool:
    """POST Omniverse /api/v0.1/RAN/Ingest/SignalIngestor/create — 把 per-UE 訊號落
    signal_history 表(Playback 用)。

    signals = [{ue_name, serving_cell, rsrp_dbm, sinr_db, rsrp_map?, throughput_dl_mbps?,
                throughput_ul_mbps?, mcs_dl?, prb_used_dl?, mimo_rank?, position?}, ...]
    session_uuid 沒提供時 SignalHistory.session_uuid 會是 NULL,Playback 無法 group 該 sim。
    失敗只 warn,不擋 UE loop。
    """
    if not signals:
        return True
    url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/Ingest/SignalIngestor/create"
    body: dict[str, Any] = {"signals": signals}
    if session_uuid:
        body["session_uuid"] = session_uuid
    try:
        r = _session.post(url, json=body, timeout=_TIMEOUT_SEC)
        if not r.ok:
            logger.warning("omniverse ingest_signals non-OK: %d %s", r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("omniverse ingest_signals HTTP failed: %s", exc)
        return False


def batch_move_ues(
    ues: list[dict[str, Any]],
    signals: dict[str, dict[str, Any]] | None = None,
    update_db: bool = False,
) -> bool:
    """POST Omniverse /api/v0.1/RAN/UE/UEController/batch_move.

    輸入:
      ues = [{id, position:{x,y,z}}, ...]  ← ru_client 的 schema
      signals = {ue_name: {sinr_db, rsrp_dbm, serving_cell, ...}}
              選填,DU 算出的最新 per-UE 訊號 — 跟著位置一起更新 Omniverse UE label。
    回傳 False 不擋 driver loop,只 warning(Omniverse 不在線時 RAN sim 仍要能跑)。
    """
    if not ues:
        return True
    signals = signals or {}
    payload_ues = []
    for u in ues:
        name = u.get("id") or u.get("name")
        pos = u.get("position", {})
        entry: dict[str, Any] = {
            "name": name,
            "x": float(pos.get("x", 0.0)),
            "y": float(pos.get("y", 0.0)),
            "z": float(pos.get("z", 0.0)),
        }
        sig = signals.get(name) or {}
        # 只在有有效值時帶上(避免覆蓋成 None — Omniverse 端 push_signal 收到 None 會 skip)
        if sig.get("rsrp_dbm") is not None:
            entry["rsrp_dbm"] = float(sig["rsrp_dbm"])
        if sig.get("sinr_db") is not None:
            entry["sinr_db"] = float(sig["sinr_db"])
        if sig.get("serving_cell"):
            entry["serving_cell"] = sig["serving_cell"]
        payload_ues.append(entry)
    url = f"{settings.OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/UE/UEController/batch_move"
    body: dict[str, Any] = {"ues": payload_ues}
    if update_db:
        body["update_db"] = True
    try:
        r = _session.post(url, json=body, timeout=_TIMEOUT_SEC)
        if not r.ok:
            logger.warning("omniverse batch_move non-OK: %d %s", r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("omniverse batch_move HTTP failed: %s", exc)
        return False
