"""CU HTTP client — 拉 UE list / Cell list / scene state。"""
from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 5.0


def list_sessions() -> list[dict[str, Any]] | None:
    """Fetch CU /Session/SessionController/list — 回傳 active UE sessions.

    每筆 dict 至少含: ue_id, serving_cell, rrc_state, traffic_profile (新欄位, 可能不存在)
    失敗回 **None**(非 []):「CU 不可達」與「真的沒 UE」必須可分 ——
    回 [] 會讓 manager 把全部執行緒判 removed 殺掉重建,重建執行緒間歇性
    不再驅動量測鏈(2026-08-25 16:23 UE 量測流默死事故,坑7)。"""
    url = f"{settings.SIM_CU_URL.rstrip('/')}/api/v0.1/CU/Session/SessionController/list"
    try:
        r = requests.post(url, json={}, timeout=_TIMEOUT_SEC)
    except requests.RequestException as exc:
        logger.warning("list_sessions HTTP failed: %s", exc)
        return None
    if not r.ok:
        logger.warning("list_sessions non-OK status %s", r.status_code)
        return None
    try:
        body = r.json()
    except ValueError:
        logger.warning("list_sessions returned non-JSON")
        return None
    # CU schema: {"data": [{ue_id, rrc_state, serving_cell, ...}, ...]}
    data = body.get("data", [])
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "sessions" in data:
        return data["sessions"]
    return []


def release_stale(keep_ue_ids: list[str], force: bool = False) -> bool:
    """POST CU /Session/SessionController/release_stale — 把不在 keep 名單裡的 UE
    標 IDLE(或 force=True 直接刪掉),同時 fan-out 通知 DU 清掉對應 UE。

    給 scenario_driver start() 用,跟 Dashboard handleStartSim C.5 一樣的清理動作,
    避免上一場 sim 殘留的 CONNECTED UE 在 /logs 的 KpmReporter 視圖裡冒出來。
    """
    url = f"{settings.SIM_CU_URL.rstrip('/')}/api/v0.1/CU/Session/SessionController/release_stale"
    body = {"keep_ue_ids": list(keep_ue_ids), "force": bool(force)}
    try:
        r = requests.post(url, json=body, timeout=_TIMEOUT_SEC)
        if not r.ok:
            logger.warning("release_stale non-OK %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("release_stale HTTP failed: %s", exc)
        return False


def update_traffic_profile(ue_id: str, profile: dict[str, Any]) -> bool:
    """POST CU /Session/SessionController/update_traffic_profile to re-establish
    F1AP UE Context Setup (which auto-creates RLC entity on DU).

    AL3 — 給 traffic_gen.tick() 在 inject_sdu "RLC entity not found" 時
    呼叫做自我修復, 對齊 DU restart / RLC entity 被清除的場景.
    """
    url = f"{settings.SIM_CU_URL.rstrip('/')}/api/v0.1/CU/Session/SessionController/update_traffic_profile"
    body = {"ue_id": ue_id, "traffic_profile": profile}
    try:
        r = requests.post(url, json=body, timeout=_TIMEOUT_SEC)
        return r.ok
    except requests.RequestException as exc:
        logger.warning("update_traffic_profile HTTP failed for %s: %s", ue_id, exc)
        return False


# Phase B B.x — 給 scenario_driver 用的 attach helpers,複製 Dashboard handleStartSim 流程。
import base64
import json as _json


def _rrc_b64(msg_type: str, payload: dict | None = None) -> str:
    body = {"type": msg_type, "payload": payload or {}}
    return base64.b64encode(_json.dumps(body).encode()).decode()


def is_ue_connected(ue_id: str) -> bool:
    """看 CU session list 確認 UE 是否已在 CONNECTED 狀態。"""
    url = f"{settings.SIM_CU_URL.rstrip('/')}/api/v0.1/CU/Session/SessionController/list"
    try:
        r = requests.post(url, json={}, timeout=_TIMEOUT_SEC)
        if not r.ok:
            return False
        sessions = r.json().get("data", [])
        for s in sessions:
            if s.get("ue_id") == ue_id and s.get("rrc_state") == "CONNECTED":
                return True
        return False
    except requests.RequestException:
        return False


def list_cells() -> list[dict[str, Any]]:
    """CU 認得的 cell(只回 is_active 的)。UE 選網後要拿它驗證 —— Physics 回的是
    scene 裡的 gNB 標籤(如 "gnb1#0"),不是 CU 的 cell_id("gnb1_c0"),
    直接拿去 attach 會把 phantom 名稱寫進 serving_cell(2026-08-20 踩到)。"""
    url = f"{settings.SIM_CU_URL.rstrip('/')}/api/v0.1/CU/E2/NodeInfo/read"
    try:
        r = requests.post(url, json={}, timeout=_TIMEOUT_SEC)
        if not r.ok:
            return []
        return ((r.json() or {}).get("data") or {}).get("servingCells") or []
    except (requests.RequestException, ValueError) as exc:
        logger.debug("list_cells failed: %s", exc)
        return []


def rrc_attach(ue_id: str) -> bool:
    """走 RRC SetupRequest + SetupComplete 兩步,把 UE 帶到 CONNECTED。

    Idempotent:已 CONNECTED 就直接回 True 不重發(否則 CU RRC handler 會 500)。
    """
    if is_ue_connected(ue_id):
        logger.info("rrc_attach %s: already CONNECTED, skip", ue_id)
        return True
    url = f"{settings.SIM_CU_URL.rstrip('/')}/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message"
    for msg_type, payload in (
        ("RRCSetupRequest", {}),
        ("RRCSetupComplete", {"transaction_id": 1}),
    ):
        try:
            r = requests.post(
                url,
                json={"ue_id": ue_id, "rrc_msg_b64": _rrc_b64(msg_type, payload)},
                timeout=_TIMEOUT_SEC,
            )
            if not r.ok:
                logger.warning(
                    "rrc_attach %s %s non-OK %s: %s",
                    ue_id, msg_type, r.status_code, r.text[:200],
                )
                return False
        except requests.RequestException as exc:
            logger.warning("rrc_attach HTTP failed: %s %s: %s", ue_id, msg_type, exc)
            return False
    return True


def force_serving_cell(ue_id: str, target_cell: str) -> bool:
    """走 SessionController/handover 強制把 UE serving_cell 設成 target_cell。
    (對 driver 沒先驗 measurement_report 的情境用 — 一刀切先設好讓後續 inject 找得到。)
    """
    url = f"{settings.SIM_CU_URL.rstrip('/')}/api/v0.1/CU/Session/SessionController/handover"
    body = {"ue_id": ue_id, "target_cell": target_cell}
    try:
        r = requests.post(url, json=body, timeout=_TIMEOUT_SEC)
        if not r.ok:
            logger.warning(
                "force_serving_cell %s → %s non-OK %s: %s",
                ue_id, target_cell, r.status_code, r.text[:200],
            )
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("force_serving_cell HTTP failed: %s: %s", ue_id, exc)
        return False


def set_a3(enabled: bool, *, offset_db: float | None = None,
           hys_db: float | None = None, ttt_ms: int | None = None) -> bool:
    """設 CU A3 自動換手開關 + 門檻(Mobility/A3Controller/set)。
    CCO 等「RC 手動換到較弱 cell」的劇本要關掉 A3,否則 A3 看訊號把 UE 彈回強 cell。
    offset/hys/ttt None = 不覆寫(用 CU env 預設,offset 5 + hys 6 = 11dB 門檻)。
    ANR 缺漏鄰區 demo 要低門檻(offset 2 hys 1)才在健康區換手 —— 劇本帶參數。
    """
    url = f"{settings.SIM_CU_URL.rstrip('/')}/api/v0.1/CU/Mobility/A3Controller/set"
    payload: dict = {"enabled": bool(enabled)}
    if offset_db is not None:
        payload["offset_db"] = float(offset_db)
    if hys_db is not None:
        payload["hys_db"] = float(hys_db)
    if ttt_ms is not None:
        payload["ttt_ms"] = int(ttt_ms)
    try:
        r = requests.post(url, json=payload, timeout=_TIMEOUT_SEC)
        if not r.ok:
            logger.warning("set_a3 enabled=%s non-OK %s: %s", enabled, r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as exc:
        logger.warning("set_a3 HTTP failed: %s", exc)
        return False


def start_anr_fixture(scenario_id: str) -> bool:
    """請 CU 起這個劇本的病徵時間軸(Anr/Fixture/start)。

    在此之前時間軸得由人手動 docker exec 起 —— 「劇本會自己跑」只做到一半:
    節奏是宣告在劇本裡的,但啟動仍然依賴外部觸發。前端 Start Sim 之後
    要能自動佈病,這一步就得由場景套用流程負責。

    沒有 anr_fixture 區塊的劇本會回 started=false,不是錯誤(多數劇本沒有)。
    失敗不擋場景啟動:佈病失敗頂多是這一輪沒病,場景本身仍然可用。
    """
    url = f"{settings.SIM_CU_URL.rstrip('/')}/api/v0.1/CU/Anr/Fixture/start"
    # 重試:場景切換時 CU 會重啟,這個呼叫常打在重啟中的 CU 上。
    # 失敗的話「現行劇本」檔停留在上一題,連補跑都會被 guard 擋掉
    # (2026-08-28 Q7 實測:自動佈病靜默失效,病沒佈成)。
    # 最多等 60 秒 —— CU 重啟約 20~25 秒,60 秒還不通就是真的壞了。
    import time as _t
    last_exc: Exception | None = None
    for attempt in range(6):
        try:
            r = requests.post(url, json={"scenario_id": scenario_id}, timeout=_TIMEOUT_SEC)
            if r.ok:
                d = (r.json() or {}).get("data") or {}
                if d.get("started"):
                    logger.info("scenario %s 病徵時間軸已啟動(%s 步,第 %d 次嘗試)",
                                scenario_id, d.get("steps"), attempt + 1)
                return bool(d.get("started"))
            logger.warning("start_anr_fixture non-OK %s(第 %d 次): %s",
                           r.status_code, attempt + 1, r.text[:150])
        except requests.RequestException as exc:
            last_exc = exc
        _t.sleep(10)
    logger.warning("start_anr_fixture 六次皆失敗: %s", last_exc)
    return False
