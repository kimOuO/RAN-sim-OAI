"""跨系統呼叫 registry(backend_rule §12-2:跨 repo 只傳 uuid)。"""
from __future__ import annotations

import json
import urllib.request

from django.conf import settings


def _post(path: str, body: dict, timeout: float = 15.0) -> dict:
    url = f"http://{settings.HTTP_REGISTRY_HOST}:{settings.HTTP_REGISTRY_PORT}/api/v0.1/Scene_management_backend/{path}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def create_building(*, scene_uuid: str, name: str, source: str, geometry_ref: str, materials_npz: str = "",
                    position=None, rotation=None, scale=None, size=None, default_material_uuid: str | None = None) -> dict:
    body = {"f_scene_uuid": scene_uuid, "name": name, "source": source, "geometry_ref": geometry_ref,
            "materials_npz": materials_npz, "position": position or [0, 0, 0], "rotation": rotation or [],
            "scale": scale or [], "size": size or []}
    if default_material_uuid:
        body["f_material_uuid"] = default_material_uuid
    return _post("Field_scene/BuildingController/create", body)
