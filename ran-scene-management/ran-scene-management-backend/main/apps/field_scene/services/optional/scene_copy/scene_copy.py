"""整個場景深複製(2026-09-17):建築、gNB/DU/cell/RU、鄰區種子、UE 與其路徑/流量/在場時段、run 設定(draft)。

用途:同一個場景跑多個副本做對照(例如 live 與 cached 同時跑)。
以前只能 export_v1 → import_v1,但劇本格式不帶天線 preset 與 RU 覆寫,複製出來會不一樣。
"""
from __future__ import annotations

from typing import Any

from django.db import models

from main.apps.equipment_ran.models.cell import Cell
from main.apps.equipment_ran.models.du import Du
from main.apps.equipment_ran.models.gnb import Gnb
from main.apps.equipment_ran.models.neighbor_seed import NeighborSeed
from main.apps.equipment_ran.models.ru import Ru
from main.apps.equipment_ue.models.ue import Ue
from main.apps.equipment_ue.models.ue_active_window import UeActiveWindow
from main.apps.equipment_ue.models.ue_traffic import UeTraffic
from main.apps.equipment_ue.models.ue_waypoint import UeWaypoint
from main.apps.field_scene.models.building import Building
from main.apps.field_scene.models.scene import Scene
from main.apps.field_scene.services.common.timestamp_service import TimestampService
from main.apps.field_scene.services.common.uuid_service import UUIDService
from main.apps.simulation_run.models.run_knob import RunKnob
from main.apps.simulation_run.models.scene_run import SceneRun


def _uuid_field(model: type[models.Model]) -> str:
    return next(f.name for f in model._meta.fields if f.name.endswith("_uuid") and f.unique)


def _clone(obj: models.Model, **overrides: Any) -> models.Model:
    """同欄位複製一列:新 pk、新 uuid、新時間戳,外鍵由 overrides 指到新父物件。"""
    model = type(obj)
    uf = _uuid_field(model)
    prefix = uf[: -len("_uuid")]
    now = TimestampService.get_current_timestamp()
    data = {}
    for f in model._meta.concrete_fields:
        if f.primary_key or f.name == uf:
            continue
        data[f.attname] = getattr(obj, f.attname)
        if f.name.endswith(("_created_at", "_updated_at")):
            data[f.attname] = now
    new = model(**data, **{uf: UUIDService.generate_uuid(prefix)})
    for k, v in overrides.items():
        setattr(new, k, v)
    new.save()
    return new


def copy_scene(scene_uuid: str, *, name: str, legacy_scenario_id: str | None = None) -> Scene:
    src = Scene.objects.get(scene_uuid=scene_uuid)
    dst = _clone(src, name=name, legacy_scenario_id=legacy_scenario_id if legacy_scenario_id is not None else name)
    for b in Building.objects.filter(scene=src):
        _clone(b, scene=dst)
    cell_map: dict[str, Cell] = {}
    for g in Gnb.objects.filter(scene=src).order_by("id"):
        ng = _clone(g, scene=dst)
        for d in Du.objects.filter(gnb=g).order_by("id"):
            nd = _clone(d, gnb=ng)
            for c in Cell.objects.filter(du=d).order_by("id"):
                nc = _clone(c, du=nd)
                cell_map[c.cell_uuid] = nc
                for r in Ru.objects.filter(cell=c):
                    _clone(r, cell=nc)
    for s in NeighborSeed.objects.filter(source_cell__cell_uuid__in=list(cell_map)):
        if s.target_cell_id in cell_map:
            _clone(s, source_cell=cell_map[s.source_cell_id], target_cell=cell_map[s.target_cell_id])
    for u in Ue.objects.filter(scene=src).order_by("id"):
        nu = _clone(u, scene=dst)
        for m in (UeWaypoint, UeTraffic, UeActiveWindow):
            for row in m.objects.filter(ue=u).order_by("id"):
                _clone(row, ue=nu)
    run = SceneRun.objects.filter(scene=src).order_by("id").first()
    if run is not None:   # 只帶設定,不帶狀態 / cache
        nr = _clone(run, scene=dst, status="draft", cache_path="", e2_node_id="", gnb_id_hex="",
                    started_at=None, stopped_at=None, notes=f"copied from {src.name}")
        for k in RunKnob.objects.filter(scene_run=run):
            _clone(k, scene_run=nr)
    return dst
