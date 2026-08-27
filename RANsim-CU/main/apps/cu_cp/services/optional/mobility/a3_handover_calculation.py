"""A3 event handover with TimeToTrigger — TS 38.331 §5.5.4.4.

Adapted from XAPP_DT/Physics_sim/_legacy/cu_candidates/rrc_event_tracker.py.
The original was a per-tick stateful tracker; here we expose a stateless
``evaluate()`` that takes the prior pending-state map and returns a verdict
and the new state. This lets cu_cp persist the state per UE (in-memory dict
is enough — the same UE always hits the same Django process).

Trigger:  Mn − hys > Mp + offset    (equivalently: nb_rsrp − hys > serving_rsrp + offset)
TTT:      condition must hold for at least ``ttt_ms`` to fire.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.utils.env_loader import get_bool, get_float, get_int

logger = logging.getLogger(__name__)

# A3 預設值 — 對齊 3GPP TS 38.331 範例值，但對 sim 場景偏保守
# Sim 場景因為 antenna pattern + 固定位置常常 RSRP 差距小，為了 demo 容易看到
# 自動 HO，預設值調軟一些（仍可用 env var 覆蓋回保守值）
A3_OFFSET_DEFAULT = 1.0     # 真實 spec 通常 0-3 dB；我們用 1 dB 讓 demo 容易觸發
A3_HYS_DEFAULT = 0.5        # 真實 spec 0-15 dB；用 0.5 加快響應
TTT_DEFAULT = 80            # 真實 spec 40-5120 ms；用 80 ms 快響應


@dataclass
class A3PendingState:
    neighbor_cell: str
    first_met_ms: int


@dataclass
class A3UeState:
    serving_cell: str = ""
    pending: dict[str, A3PendingState] = field(default_factory=dict)


@dataclass
class A3Verdict:
    triggered: bool
    target_cell: str = ""
    elapsed_ms: int = 0


@dataclass
class A3Config:
    """Runtime config (Dashboard / HTTP 可改). 預設從 env 來, 之後 store override."""
    enabled: bool
    offset_db: float
    hys_db: float
    ttt_ms: int


# Module-level singleton config (per Django process). Default from env, override via HTTP.
_CONFIG: A3Config = A3Config(
    enabled=get_bool("HO_A3_ENABLED", default=False),  # 預設關:CCO 等 RC 手動換手不被 A3 彈回;要自動 A3 設 HO_A3_ENABLED=on 或劇本 a3_enabled
    offset_db=get_float("HO_A3_OFFSET_DB", default=A3_OFFSET_DEFAULT),
    hys_db=get_float("HO_A3_HYSTERESIS_DB", default=A3_HYS_DEFAULT),
    ttt_ms=get_int("HO_TTT_MS", default=TTT_DEFAULT),
)


def get_a3_config() -> A3Config:
    return _CONFIG


_OVERRIDE_PATH = "/app/tmp/a3_override.json"


def _persist_override() -> None:
    """把當前 A3 組態寫檔,讓 CU 重啟後還原。

    2026-08-27 中性場實測:劇本宣告 a3_enabled=true,套用後 CU 重啟一次,
    組態回到 env 預設(false),但觀測面照樣把 a3Enabled 回報出去 ——
    **觀測面在說謊**,而 xApp 才剛把 a3Enabled 接成第 12 題的訊號⑥。
    A3 覆寫是劇本宣告的環境設定,不是一次性指令,它必須跟著場景活著。
    """
    import json
    import os
    import tempfile
    try:
        os.makedirs(os.path.dirname(_OVERRIDE_PATH), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(_OVERRIDE_PATH))
        with os.fdopen(fd, "w") as f:
            json.dump({"enabled": _CONFIG.enabled, "offset_db": _CONFIG.offset_db,
                       "hys_db": _CONFIG.hys_db, "ttt_ms": _CONFIG.ttt_ms}, f)
        os.replace(tmp, _OVERRIDE_PATH)
    except OSError:
        pass


def load_persisted_override() -> bool:
    """啟動時還原劇本套過的 A3 覆寫;沒有檔案就沿用 env 預設。"""
    import json
    try:
        with open(_OVERRIDE_PATH) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return False
    _CONFIG.enabled = bool(d.get("enabled", _CONFIG.enabled))
    _CONFIG.offset_db = float(d.get("offset_db", _CONFIG.offset_db))
    _CONFIG.hys_db = float(d.get("hys_db", _CONFIG.hys_db))
    _CONFIG.ttt_ms = int(d.get("ttt_ms", _CONFIG.ttt_ms))
    return True


def clear_persisted_override() -> None:
    """場景停止時清掉 —— 否則下一場會沿用上一場的 A3,是跨場污染。"""
    import os
    try:
        os.remove(_OVERRIDE_PATH)
    except OSError:
        pass


def set_a3_config(*, enabled: bool | None = None, offset_db: float | None = None,
                  hys_db: float | None = None, ttt_ms: int | None = None) -> A3Config:
    global _CONFIG
    if enabled is not None:
        _CONFIG.enabled = bool(enabled)
    if offset_db is not None:
        _CONFIG.offset_db = float(offset_db)
    if hys_db is not None:
        _CONFIG.hys_db = float(hys_db)
    if ttt_ms is not None:
        _CONFIG.ttt_ms = int(ttt_ms)
    _persist_override()
    return _CONFIG


def _ho_blocklisted_targets(serving_cell: str) -> set[str]:
    """回傳 serving_cell 目前不可用於換手的鄰區 target(hoBlocklist 或 xnBlocklist)。
    env ANR_ENFORCE_HO_BLOCKLIST=off 可停用(rollback);DB 出錯不擋換手。"""
    if not serving_cell:
        return set()
    if not get_bool("ANR_ENFORCE_HO_BLOCKLIST", default=True):
        return set()
    try:
        from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
        # xnBlocklist 與 hoBlocklist 都會讓換手不可用,語意不同但對 A3 的效果一樣:
        #   hoBlocklist — TS 28.313 §6.4.1.3.5 Handover Blocklisting(封而不刪)
        #   xnBlocklist — §6.4.1.3.7 Xn 換手路徑禁用(不拆線,交管理面修 Xn)
        # v10 第 6 題的正解就是 set xnBlocklist;不在這裡擋掉的話設了等於沒設。
        from django.db.models import Q
        return set(
            NrCellRelation.objects.filter(
                Q(ho_blocklist=True) | Q(xn_blocklist=True),
                source_cell_id=serving_cell,
            ).values_list("target_cgi", flat=True)
        )
    except Exception:  # noqa: BLE001 — DB 問題不應擋換手決策
        logger.exception("ANR ho_blocklist lookup failed for %s", serving_cell)
        return set()


def _nrt_allowed_targets(serving_cell: str) -> set[str] | None:
    """回傳 serving_cell 在 NRT 有關係且 is_ho_allowed 的 target 集(對齊 3GPP:
    換手必須有 NrCellRelation)。env `ANR_REQUIRE_NRT`=off 時回 None = 不 gate(舊行為)。

    2026-08-12:補上「缺漏關係 → 換不了」的因果 —— 這是 ANR use-case 的地基。
    None(不 gate)與 空集(有 gate 但無任何關係)語意不同,caller 要分辨。
    """
    if not get_bool("ANR_REQUIRE_NRT", default=True):
        return None
    try:
        from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
        return set(
            NrCellRelation.objects.filter(
                source_cell_id=serving_cell, is_ho_allowed=True,
            ).values_list("target_cgi", flat=True)
        )
    except Exception:
        logger.exception("ANR NRT lookup failed for %s", serving_cell)
        return None  # 出錯不擋換手


class A3HandoverCalculation:
    def __init__(self) -> None:
        # Read from runtime config store (which defaults from env).
        # AK11: each evaluate() call reads current store snapshot → Dashboard 改完即時生效.
        cfg = get_a3_config()
        self.enabled = cfg.enabled
        self.offset_db = cfg.offset_db
        self.hys_db = cfg.hys_db
        self.ttt_ms = cfg.ttt_ms

    def evaluate(
        self,
        ue_state: A3UeState,
        serving_cell: str,
        serving_rsrp: float,
        neighbors: list[tuple[str, float]],
    ) -> A3Verdict:
        """Update ``ue_state`` in place and return whether HO fires *this call*.

        ``neighbors``: list of (cell_id, rsrp_dbm) excluding serving.
        """
        if not self.enabled:
            # A3 disabled via Dashboard — no HO triggered regardless of RSRP
            return A3Verdict(triggered=False)
        now_ms = TimestampService.now_ms()
        ue_state.serving_cell = serving_cell
        verdict = A3Verdict(triggered=False)

        # E2SM-ANR M4(A 級行為):xApp 用 SONTRIG_ANR_FLAG_REQUEST 封鎖的鄰區關係
        # (ho_blocklist=True)→ A3 換手決策直接略過該目標(封而不刪,止血)。
        blocked = _ho_blocklisted_targets(serving_cell)
        # 缺漏鄰區 gate:target 必須在 NRT(3GPP 換手前提)。None = 不 gate。
        allowed = _nrt_allowed_targets(serving_cell)

        for nb_cell, nb_rsrp in neighbors:
            if nb_cell == serving_cell:
                continue
            if nb_cell in blocked:
                logger.info("A3 skip blocklisted target ue serving=%s nb=%s (ANR ho_blocklist)",
                            serving_cell, nb_cell)
                ue_state.pending.pop(nb_cell, None)
                continue
            if allowed is not None and nb_cell not in allowed:
                # 缺漏鄰區:NRT 無此關係 → 換不了(UE 只能撐到 RLF → 重建)。
                # xApp 對此該下 ANR ADD 建立關係,而非 FLAG。
                ue_state.pending.pop(nb_cell, None)
                continue
            condition_met = (nb_rsrp - self.hys_db) > (serving_rsrp + self.offset_db)
            pending = ue_state.pending.get(nb_cell)

            # 只在 condition 滿足時 log;一般 eval 不洗版
            if condition_met:
                logger.info(
                    "A3 condition MET ue serving=%s rsrp_s=%.1f nb=%s rsrp_n=%.1f delta=%.1f (need>%.1f)",
                    serving_cell, serving_rsrp, nb_cell, nb_rsrp,
                    nb_rsrp - serving_rsrp, self.offset_db + self.hys_db,
                )

            if condition_met:
                if pending is None:
                    ue_state.pending[nb_cell] = A3PendingState(nb_cell, now_ms)
                else:
                    elapsed = now_ms - pending.first_met_ms
                    if elapsed >= self.ttt_ms and not verdict.triggered:
                        verdict.triggered = True
                        verdict.target_cell = nb_cell
                        verdict.elapsed_ms = elapsed
                        ue_state.pending.clear()
                        return verdict
            else:
                ue_state.pending.pop(nb_cell, None)

        return verdict


# Per-process UE-state registry (process-local, mirrors OAI _ue_ho_state).
_UE_STATE_REGISTRY: dict[str, A3UeState] = {}


def get_ue_state(ue_id: str) -> A3UeState:
    return _UE_STATE_REGISTRY.setdefault(ue_id, A3UeState())


def reset_state() -> None:
    _UE_STATE_REGISTRY.clear()
