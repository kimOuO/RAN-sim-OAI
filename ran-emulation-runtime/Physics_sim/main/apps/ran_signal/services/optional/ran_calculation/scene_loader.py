"""讀 scene_config.json 並檢查必要欄位。"""
import json
from pathlib import Path
from typing import Any

from main.utils.logger import get_logger


logger = get_logger(__name__)


REQUIRED_GNB_FIELDS = {"name", "position", "frequency_ghz", "power_dbm", "bandwidth_mhz"}
RECOMMENDED_GNB_FIELDS = {"pci", "cell_id"}


def load(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"scene_config.json not found at {p}")

    with p.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 驗 gNB 必要欄位
    for i, g in enumerate(cfg.get("gnbs", [])):
        missing = REQUIRED_GNB_FIELDS - set(g.keys())
        if missing:
            raise ValueError(f"gnbs[{i}] ({g.get('name','?')}) missing fields: {missing}")

        rec_missing = RECOMMENDED_GNB_FIELDS - set(g.keys())
        if rec_missing:
            logger.warning(
                "gnbs[%d] %s missing recommended fields %s — will auto-assign",
                i, g.get("name"), rec_missing,
            )
            # 自動補 PCI / cell_id（若沒手寫）
            if "pci" not in g:
                g["pci"] = _auto_pci(g["name"])
            if "cell_id" not in g:
                g["cell_id"] = _auto_cell_id(g["name"])

    return cfg


def _auto_pci(name: str) -> int:
    # 3GPP PCI 範圍 0~1007
    import hashlib
    h = int(hashlib.sha256(name.encode()).hexdigest(), 16)
    return h % 1008


def _auto_cell_id(name: str) -> str:
    import hashlib
    h = hashlib.sha256(name.encode()).hexdigest()
    return f"99f966{h[:9]}"
