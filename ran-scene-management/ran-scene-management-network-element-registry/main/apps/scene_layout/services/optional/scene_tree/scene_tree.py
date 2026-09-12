
"""整棵 scene 樹的組裝(Optional Service)。給 DU/RU/UE driver 一次拉完設定,run 期間不再打 registry。

形狀:
{
  scene, buildings[], gnbs[{..., dus[{..., config_template, cells[{..., ru{..., antenna_preset}}]}]}],
  ues[{..., waypoints[[t,x,y,z],…], traffic[], active_windows[[t0,t1],…]}], neighbor_seeds[],
  run{..., knobs{key: value}, instances[]}   # 指定 scene_run_uuid 才有;否則取該 scene 最早的 run
}
"""
from __future__ import annotations

from typing import Any

from main.apps.preset_catalog.serializers.antenna_preset_serializers import AntennaPresetReadSerializer
from main.apps.preset_catalog.serializers.du_config_template_serializers import DuConfigTemplateReadSerializer
from main.apps.preset_catalog.serializers.material_serializers import MaterialReadSerializer
from main.apps.radio_access_element.models.cell import Cell
from main.apps.radio_access_element.models.du import Du
from main.apps.radio_access_element.models.gnb import Gnb
from main.apps.radio_access_element.models.neighbor_seed import NeighborSeed
from main.apps.radio_access_element.models.ru import Ru
from main.apps.radio_access_element.serializers.cell_serializers import CellReadSerializer
from main.apps.radio_access_element.serializers.du_serializers import DuReadSerializer
from main.apps.radio_access_element.serializers.gnb_serializers import GnbReadSerializer
from main.apps.radio_access_element.serializers.neighbor_seed_serializers import NeighborSeedReadSerializer
from main.apps.radio_access_element.serializers.ru_serializers import RuReadSerializer
from main.apps.scene_layout.models.building import Building
from main.apps.scene_layout.models.scene import Scene
from main.apps.scene_layout.serializers.building_serializers import BuildingReadSerializer
from main.apps.scene_layout.serializers.scene_serializers import SceneReadSerializer
from main.apps.simulation_run.models.run_instance import RunInstance
from main.apps.simulation_run.models.run_knob import RunKnob
from main.apps.simulation_run.models.scene_run import SceneRun
from main.apps.simulation_run.serializers.run_instance_serializers import RunInstanceReadSerializer
from main.apps.simulation_run.serializers.scene_run_serializers import SceneRunReadSerializer
from main.apps.user_equipment.models.ue import Ue
from main.apps.user_equipment.models.ue_active_window import UeActiveWindow
from main.apps.user_equipment.models.ue_traffic import UeTraffic
from main.apps.user_equipment.models.ue_waypoint import UeWaypoint
from main.apps.user_equipment.serializers.ue_serializers import UeReadSerializer
from main.apps.user_equipment.serializers.ue_traffic_serializers import UeTrafficReadSerializer


def build_scene_tree(scene: Scene, run: SceneRun | None = None) -> dict[str, Any]:
    tree: dict[str, Any] = {"scene": SceneReadSerializer(scene).data}
    if scene.ground_material_id:
        tree["scene"]["ground_material"] = MaterialReadSerializer(scene.ground_material).data
    tree["buildings"] = []
    for b in Building.objects.filter(scene=scene).select_related("default_material").order_by("id"):
        bd = BuildingReadSerializer(b).data
        bd["default_material"] = MaterialReadSerializer(b.default_material).data if b.default_material_id else None
        tree["buildings"].append(bd)
    tree["gnbs"] = []
    cells_all: list[Cell] = []
    for g in Gnb.objects.filter(scene=scene).order_by("id"):
        gd = GnbReadSerializer(g).data; gd["dus"] = []
        for du in Du.objects.filter(gnb=g).select_related("config_template").order_by("id"):
            dd = DuReadSerializer(du).data
            dd["config_template"] = DuConfigTemplateReadSerializer(du.config_template).data if du.config_template_id else None
            dd["cells"] = []
            for c in Cell.objects.filter(du=du).order_by("id"):
                cd = CellReadSerializer(c).data
                ru = Ru.objects.filter(cell=c).select_related("antenna_preset").first()
                if ru is not None:
                    rd = RuReadSerializer(ru).data
                    rd["antenna_preset"] = AntennaPresetReadSerializer(ru.antenna_preset).data if ru.antenna_preset_id else None
                    cd["ru"] = rd
                else:
                    cd["ru"] = None
                dd["cells"].append(cd); cells_all.append(c)
            gd["dus"].append(dd)
        tree["gnbs"].append(gd)
    tree["neighbor_seeds"] = NeighborSeedReadSerializer(
        NeighborSeed.objects.filter(source_cell__in=cells_all).order_by("id"), many=True).data
    tree["ues"] = []
    for u in Ue.objects.filter(scene=scene).select_related("antenna_preset").order_by("id"):
        ud = UeReadSerializer(u).data
        ud["antenna_preset"] = AntennaPresetReadSerializer(u.antenna_preset).data if u.antenna_preset_id else None
        # 軌跡與在場時窗用緊湊陣列(消費端只要數值;18 UE × 8.8k waypoint 用完整列會到 2.7 MB / 3 s)
        ud["waypoints"] = [list(w) for w in UeWaypoint.objects.filter(ue=u).order_by("ord").values_list("t_sec", "x", "y", "z")]
        ud["traffic"] = UeTrafficReadSerializer(UeTraffic.objects.filter(ue=u).order_by("id"), many=True).data
        ud["active_windows"] = [list(w) for w in UeActiveWindow.objects.filter(ue=u).order_by("id").values_list("t0_sec", "t1_sec")]
        tree["ues"].append(ud)
    if run is None:
        run = SceneRun.objects.filter(scene=scene).order_by("id").first()
    if run is not None:
        rd = SceneRunReadSerializer(run).data
        rd["knobs"] = {k.key: k.value for k in RunKnob.objects.filter(scene_run=run)}
        rd["instances"] = RunInstanceReadSerializer(RunInstance.objects.filter(scene_run=run).order_by("id"), many=True).data
        tree["run"] = rd
    else:
        tree["run"] = None
    return tree
