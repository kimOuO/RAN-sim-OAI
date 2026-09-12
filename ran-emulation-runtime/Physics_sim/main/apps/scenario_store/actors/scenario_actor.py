"""ScenarioController — physics_db 上的劇本 CRUD,鏡像 Omniverse ScenarioController。

端點與請求/回應形狀刻意與 Omniverse 逐字相同,消費端只要把 base URL 指到 Physics
即可取得同樣行為(讓 RAN sim 脫離 Omniverse)。

差異:apply_to_scene 只寫 scene 表(Physics 無 Omniverse Kit,不做 3D push)。
"""
from __future__ import annotations

import json
import os

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.scenario_store.models import (
    BuildingObject,
    GnbConfig,
    Scenario,
    UeConfig,
)
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)

MAX_SCENARIOS = 20
_REQUIRED = ["scenario_id", "scene_id", "duration_sec", "tick_ms", "ues"]


def _parse_body(request):
    try:
        return json.loads(request.body or b"{}"), None
    except json.JSONDecodeError as exc:
        return None, error_response("invalid JSON", str(exc), http_status=400)


def _validate(raw: dict) -> tuple[bool, str]:
    for k in _REQUIRED:
        if k not in raw:
            return False, f"missing field: {k}"
    if not isinstance(raw["ues"], list) or len(raw["ues"]) == 0:
        return False, "ues must be non-empty list"
    for ue in raw["ues"]:
        if "name" not in ue or "positions" not in ue:
            return False, "each ue requires name and positions"
    return True, ""


def _scenario_summary(s: "Scenario") -> dict:
    return {
        "scenario_id": s.scenario_id,
        "scene_id": s.scene_id,
        "duration_sec": s.duration_sec,
        "tick_ms": s.tick_ms,
        "ue_count": s.ue_count,
        "precompute_status": s.precompute_status,
        "precompute_progress": s.precompute_progress,
        "precompute_error": s.precompute_error,
        "cache_path": s.cache_path,
        "cache_size_bytes": s.cache_size_bytes,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


class ScenarioController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def upload(request):
        """Body 直接是 scenario JSON。覆寫同 scenario_id 的舊紀錄。"""
        data, err = _parse_body(request)
        if err:
            return err
        ok, msg = _validate(data)
        if not ok:
            return error_response(f"Invalid scenario JSON: {msg}", http_status=400)

        scenario_id = str(data["scenario_id"])
        try:
            obj, created = Scenario.objects.update_or_create(
                scenario_id=scenario_id,
                defaults={
                    "scene_id": str(data["scene_id"]),
                    "raw_json": data,
                    "duration_sec": float(data["duration_sec"]),
                    "tick_ms": int(data["tick_ms"]),
                    "ue_count": len(data["ues"]),
                    "precompute_status": "pending",
                    "precompute_progress": 0.0,
                    "precompute_error": "",
                    "cache_path": "",
                    "cache_size_bytes": 0,
                },
            )
            pruned = _prune_old() if created else 0
            logger.info("Scenario %s: %s (ues=%d)", scenario_id,
                        "created" if created else "updated", len(data["ues"]))
            return success_response(
                {**_scenario_summary(obj), "created": created,
                 "pruned_old": pruned, "max_scenarios": MAX_SCENARIOS},
                message=f"Scenario {'created' if created else 'updated'}",
                http_status=201 if created else 200,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("upload failed")
            return error_response(f"Failed to upload scenario: {e}", http_status=500)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def list(request):
        _, err = _parse_body(request)
        if err:
            return err
        rows = [_scenario_summary(s) for s in Scenario.objects.all()]
        return success_response({"scenarios": rows, "count": len(rows)})

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        data, err = _parse_body(request)
        if err:
            return err
        scenario_id = data.get("scenario_id")
        if not scenario_id:
            return error_response("Missing scenario_id", http_status=400)
        try:
            s = Scenario.objects.get(scenario_id=scenario_id)
        except Scenario.DoesNotExist:
            return error_response(f"Scenario {scenario_id} not found", http_status=404)
        return success_response({**_scenario_summary(s), "raw_json": s.raw_json})

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def delete(request):
        data, err = _parse_body(request)
        if err:
            return err
        scenario_id = data.get("scenario_id")
        if not scenario_id:
            return error_response("Missing scenario_id", http_status=400)
        try:
            s = Scenario.objects.get(scenario_id=scenario_id)
        except Scenario.DoesNotExist:
            return error_response(f"Scenario {scenario_id} not found", http_status=404)
        _delete_cache(s)
        s.delete()
        return success_response({"scenario_id": scenario_id}, message="Scenario deleted")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def precompute(request):
        data, err = _parse_body(request)
        if err:
            return err
        scenario_id = data.get("scenario_id")
        if not scenario_id:
            return error_response("Missing scenario_id", http_status=400)
        try:
            s = Scenario.objects.get(scenario_id=scenario_id)
        except Scenario.DoesNotExist:
            return error_response(f"Scenario {scenario_id} not found", http_status=404)
        s.precompute_status = "pending"
        s.precompute_progress = 0.0
        s.precompute_error = ""
        s.cache_path = ""
        s.cache_size_bytes = 0
        s.save(update_fields=["precompute_status", "precompute_progress",
                              "precompute_error", "cache_path", "cache_size_bytes"])
        return success_response({"scenario_id": scenario_id, "precompute_status": "pending"},
                                message="Precompute job queued")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def update_status(request):
        """precompute worker 回呼:更新 status/progress/cache。"""
        data, err = _parse_body(request)
        if err:
            return err
        scenario_id = data.get("scenario_id")
        if not scenario_id:
            return error_response("Missing scenario_id", http_status=400)
        try:
            s = Scenario.objects.get(scenario_id=scenario_id)
        except Scenario.DoesNotExist:
            return error_response(f"Scenario {scenario_id} not found", http_status=404)
        updates = []
        for field in ("precompute_status", "precompute_progress",
                      "precompute_error", "cache_path", "cache_size_bytes"):
            if field in data:
                setattr(s, field, data[field])
                updates.append(field)
        if updates:
            s.save(update_fields=updates)
        return success_response({"scenario_id": s.scenario_id,
                                 "precompute_status": s.precompute_status,
                                 "precompute_progress": s.precompute_progress,
                                 "cache_path": s.cache_path})

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def apply_to_scene(request):
        """把劇本拓樸寫進 scene 表(GnbConfig/UeConfig/BuildingObject),整批覆蓋。
        座標:劇本 position=[x,y,z];UE positions=[t,x,y,z](丟 t,waypoints 存 [x,y,z])。"""
        data, err = _parse_body(request)
        if err:
            return err
        scenario_id = data.get("scenario_id")
        if not scenario_id:
            return error_response("Missing scenario_id", http_status=400)
        try:
            s = Scenario.objects.get(scenario_id=scenario_id)
        except Scenario.DoesNotExist:
            return error_response(f"Scenario {scenario_id} not found", http_status=404)

        raw = s.raw_json or {}
        try:
            GnbConfig.objects.all().delete()
            UeConfig.objects.all().delete()
            BuildingObject.objects.all().delete()

            n_gnb = 0
            for g in raw.get("gnbs", []) or []:
                name = g.get("name")
                if not name:
                    continue
                pos = g.get("position", [0, 0, 0]) or [0, 0, 0]
                GnbConfig.objects.create(
                    gnb_uuid=f"gnb-{name}", name=name,
                    freq_mhz=float(g.get("frequency_ghz", 3.5)) * 1000.0,
                    power_dbm=float(g.get("power_dbm", 10.0)),
                    bw_hz=float(g.get("bandwidth_mhz", 40.0)) * 1_000_000.0,
                    active=bool(g.get("active", True)),
                    pos_x=float(pos[0]), pos_y=float(pos[1]), pos_z=float(pos[2]),
                    cells=g.get("cells") or [],
                )
                n_gnb += 1

            n_ue = 0
            for u in raw.get("ues", []) or []:
                name = u.get("name")
                positions = u.get("positions") or []
                if not name or not positions:
                    continue
                wps = [[float(p[1]), float(p[2]), float(p[3])] for p in positions]
                first = wps[0]
                UeConfig.objects.create(
                    ue_uuid=f"ue-{name}", name=name, waypoints_json=wps,
                    pos_x=first[0], pos_y=first[1], pos_z=first[2], loop=False,
                )
                n_ue += 1

            n_bld = 0
            for b in raw.get("buildings", []) or []:
                name = b.get("name")
                if not name:
                    continue
                pos = b.get("position", [0, 0, 0]) or [0, 0, 0]
                size = b.get("size", [10, 10, 10]) or [10, 10, 10]
                BuildingObject.objects.create(
                    building_uuid=f"bld-{name}", name=name,
                    scene_id=str(raw.get("scene_id", "")),
                    pos_x=float(pos[0]), pos_y=float(pos[1]), pos_z=float(pos[2]),
                    size_x=float(size[0]), size_y=float(size[1]), size_z=float(size[2]),
                )
                n_bld += 1

            logger.info("Scenario %s applied to scene: gnbs=%d ues=%d buildings=%d",
                        scenario_id, n_gnb, n_ue, n_bld)
            return success_response(
                {"scenario_id": scenario_id, "gnbs": n_gnb, "ues": n_ue,
                 "buildings": n_bld, "kit_pushed": False},
                message=f"Scene populated from scenario {scenario_id}",
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("apply_to_scene failed")
            return error_response(f"apply_to_scene failed: {e}", http_status=500)


def _prune_old() -> int:
    qs = Scenario.objects.order_by("created_at")
    count = qs.count()
    if count <= MAX_SCENARIOS:
        return 0
    deleted = 0
    for s in qs[: count - MAX_SCENARIOS]:
        _delete_cache(s)
        s.delete()
        deleted += 1
    return deleted


def _delete_cache(scenario: "Scenario") -> bool:
    if scenario.cache_path and os.path.exists(scenario.cache_path):
        try:
            os.remove(scenario.cache_path)
            return True
        except OSError:
            pass
    return False
