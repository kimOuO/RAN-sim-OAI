"""產物檔名規則(自 Omniverse map_actor 的 _safe_name 複製:改寫過的名字補短雜湊,避免中文名撞檔)。"""
from __future__ import annotations

import hashlib
import os
import re

from django.conf import settings

_NAME_RE = re.compile(r"[^A-Za-z0-9_\-]+")


def safe_name(name: str) -> str:
    raw = name.strip()
    safe = _NAME_RE.sub("_", raw)
    if safe != raw:
        safe = f"{safe}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:6]}"
    return safe


def asset_base(kind: str, name: str) -> str:
    """{SCANNED_ASSETS_DIR}/{kind}/{safe}(不含副檔名)。kind = scan | osm"""
    d = os.path.join(settings.SCANNED_ASSETS_DIR, kind)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, safe_name(name))
