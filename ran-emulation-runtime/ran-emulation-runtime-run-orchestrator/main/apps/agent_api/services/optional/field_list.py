"""場域清單(介面 I-1)—— 對方列選單給使用者挑場域用。

每個場域要附「能怎麼跑」的選項:負載型態、可觸發的事件型別、上限值。
我方目前的實情與規格的假設不同,這裡如實反映而不是硬湊:

  load_profiles —— 規格假設我方內建 walk_normal / commute_flow / peak_hours 這種
    可參數化的人流型態。我方沒有這層抽象:UE 是每個場域寫死的路徑資料
    (走廊場域 = 18 人、912 個路徑點)。所以每個場域只回「它自己實際具備的那一種」,
    名稱取自場域名,`default_ue_count` 為實際 UE 數,並在 `note` 說明不可覆寫人數。
    若對方確實需要多種型態,需另行預算通道快取(一個 24h 場域約 15 小時)。

  event_types —— 只列**該場域在該模式下真的做得到**的型別。回假的型別名會讓對方
    設計出我方接不住的情境:cell_addition 需要預算時已納入但初始關閉的備用 cell,
    antenna_change 在 cached 模式根本不可能(天線已烘進通道快取)。

  limits.concurrent_runs —— 釘了 e2_slot 的場域同時只能一場(識別要固定給 xApp);
    沒釘的可並行,但那種場域也不該給對方用(識別會浮動)。
"""
from __future__ import annotations

from main.apps.agent_api.services.optional import scenario_events
from main.apps.agent_api.services.optional.e2_identity import field_e2_identity
from main.apps.agent_api.services.optional.field_config import (
    BASELINE_WINDOWS_REQUIRED,
    COORDINATE_CONVENTION,
    GRANULARITY_PERIOD_SEC,
    _cells_of,
    _cfg_version,
)

# 一次模擬的長度上限。cached 模式受限於通道快取的長度,這裡取場域自身的 run 設定;
# 沒有 run 設定時給一個保守值(24 小時)。
DEFAULT_MAX_DURATION_SEC = 86400


# 與前端 config/index.ts 的 SCENE_CATEGORIES 同一套規則;Scene.category 沒宣告時才用。
_CATEGORY_RULES = (
    ("anr", lambda i: i.startswith("anr_")),
    ("corridor", lambda i: i.startswith("corridor") or i.startswith("indoor")),
    ("intent", lambda i: i.startswith(("cco", "im", "es", "recover"))),
    ("scale", lambda i: i.startswith(("dt_", "full_day", "multi"))),
)


def _category_by_prefix(scene: dict) -> str:
    ident = str(scene.get("legacy_scenario_id") or scene.get("name") or "")
    return next((k for k, t in _CATEGORY_RULES if t(ident)), "other")


def _load_profile(tree: dict, scene: dict) -> dict:
    ues = tree.get("ues") or []
    n_wp = sum(len(u.get("waypoints") or []) for u in ues)
    windows = sum(len(u.get("active_windows") or []) for u in ues)
    return {
        "name": str(scene.get("name") or ""),
        "description": f"{scene.get('name')} 既有人流",
        "default_ue_count": len(ues),
        "mobility": "劇本寫定之路徑" + (f"(共 {n_wp} 個路徑點)" if n_wp else ""),
        "has_presence_windows": windows > 0,
        "note": "本場域之人流為寫定資料,ue_count 不可覆寫;需要其他人流請另行商定(需重算通道快取)",
    }


def build_one(tree: dict, run: dict | None = None) -> dict:
    """單一場域在 I-1 清單中的一列。"""
    scene = tree.get("scene") or {}
    pairs = _cells_of(tree)
    slot = scene.get("e2_slot")
    unavailable: list[str] = []

    e2 = None
    if slot:
        e2 = field_e2_identity(int(slot), [c.get("name") or "" for _g, c in pairs])
    else:
        # 識別會隨啟動槽位浮動 → xApp 無法事先訂閱。明講,而不是給一個會變的值。
        unavailable.append("e2_identity(場域未釘 e2_slot,識別要啟動後才確定)")

    dur = int((run or {}).get("duration_sec") or 0) or DEFAULT_MAX_DURATION_SEC
    max_windows = int(dur / GRANULARITY_PERIOD_SEC) if GRANULARITY_PERIOD_SEC else None

    return {
        "field_id": scene.get("scene_uuid"),
        "name": scene.get("name"),
        # 分類:註冊表有宣告就用宣告的;沒有就照前端同一套名字前綴規則推(標 inferred,
        # 讓對方知道那是猜的)。對方列選單時可以用 category 篩。
        "category": scene.get("category") or _category_by_prefix(scene),
        "category_inferred": not scene.get("category"),
        "site": None, "floor": None,          # registry 沒有建物/樓層欄位
        "config_version": _cfg_version(tree),
        "updated_at": scene.get("scene_updated_at"),
        "cell_count": len(pairs),
        "gnb_count": len(tree.get("gnbs") or []),
        "ue_count": len(tree.get("ues") or []),
        "load_profiles": [_load_profile(tree, scene)],
        "event_types": scenario_events.supported_types(
            [c.get("name") or "" for _g, c in pairs],
            [c.get("name") or "" for _g, c in pairs if c.get("is_active") is False],
            str((run or {}).get("mode") or "cached"),
        ),
        "event_param_schema": scenario_events.event_param_schema(),
        "intrinsic_features": None,           # 無場域固有屬性之登記
        "coordinate_convention": COORDINATE_CONVENTION,
        "limits": {
            "granularity_period_s": GRANULARITY_PERIOD_SEC,
            "max_duration_s": dur,
            "max_windows": max_windows,
            # 釘了槽位的場域識別固定,代價就是同時只能一場
            "concurrent_runs": 1 if slot else None,
            "baseline_windows_required": BASELINE_WINDOWS_REQUIRED,
        },
        "mode": (run or {}).get("mode"),
        "ready": bool((run or {}).get("cache_path")) if (run or {}).get("mode") == "cached" else True,
        "e2_identity": e2,
        "unavailable_fields": sorted(set(unavailable + ["site", "floor", "intrinsic_features", "event_types"])),
    }
