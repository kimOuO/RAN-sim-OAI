"""佈病狀態的獨立載體 —— 不與協定狀態同居。

is_barred 住在 CellConfig 列裡,而那張表有多個協定寫入者(F1 Setup upsert、
stale-removal 刪除重建、場景佈建),旗標被週期性抹掉;執法迴圈每 5 秒寫回,
但覆寫與寫回之間的縫隙足以讓重建漏進 barred cell(2026-08-28 Q4:4 筆,
barred 第三漏)。獵巫成本高且治標 —— 治本是讓佈病狀態有自己的家:
一個只有 fixture 會寫的檔案,所有存取閘同時查 DB 旗標 OR 這個檔。
協定路徑不知道它的存在,自然永遠不會抹掉它。
"""
from __future__ import annotations

import json
import os
import time

_PATH = "/app/tmp/fixture_barred.json"
_cache: set[str] = set()
_mtime: float = -1.0


def fixture_barred() -> set[str]:
    """fixture 宣告的 barred cell 集合(mtime 快取,無檔 = 空集)。"""
    global _cache, _mtime
    try:
        m = os.stat(_PATH).st_mtime
    except OSError:
        if _mtime != -1.0:
            _cache, _mtime = set(), -1.0
        return _cache
    if m != _mtime:
        try:
            _cache = set(json.load(open(_PATH)) or [])
        except (OSError, ValueError):
            _cache = set()
        _mtime = m
    return _cache


def set_fixture_barred(cells: list[str]) -> None:
    import tempfile
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(_PATH))
    with os.fdopen(fd, "w") as f:
        json.dump(sorted(set(cells)), f)
    os.replace(tmp, _PATH)


def clear_fixture_barred() -> None:
    try:
        os.remove(_PATH)
    except OSError:
        pass


def is_cell_barred(cell_id: str, db_flag: bool) -> bool:
    """統一判準:DB 旗標 OR fixture 宣告。所有 barred 閘一律經此。"""
    return bool(db_flag) or cell_id in fixture_barred()


def admission_blocked(cell_id: str, db_flag: bool) -> bool:
    """接入閘(出生安置 / 換手目標 / 重建落點 / 鄰 gNB 轉入):barred,或正在進入節能(toBeEnergySaving)。

    節能兩階段是「先不收新 UE、再趕走既有 UE、清空才關」—— 以前 toBeEnergySaving 期間 cell 照收,
    RIC run 5 的 es-on 當下就有 UE 重建進來,cell 永遠關不掉。只用在接入判斷;對外觀測的 barred 欄位不變。"""
    if is_cell_barred(cell_id, db_flag):
        return True
    from main.apps.cu_cp.actors.e2_control_actor import get_cell_es_state
    return get_cell_es_state(cell_id) != "isNotEnergySaving"
