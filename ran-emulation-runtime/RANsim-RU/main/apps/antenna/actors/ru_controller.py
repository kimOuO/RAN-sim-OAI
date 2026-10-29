"""RuController — backend_rule §13：Actor 處理 HTTP + 編排業務。

Endpoints:
  POST /api/v0.1/RU/Config/RuController/update_antenna
  POST /api/v0.1/RU/Config/RuController/update_cells
  POST /api/v0.1/RU/Config/RuController/update_ues
  POST /api/v0.1/RU/Config/RuController/set_channel_mode  (Phase B B.6)
"""
import json
import os

from django.db import transaction
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.antenna.models.antenna_config import AntennaConfig
from main.apps.antenna.models.cell import Cell
from main.apps.antenna.models.ue_position import UePosition
from main.apps.antenna.serializers.antenna_serializers import (
    AntennaConfigReadSerializer,
    AntennaConfigWriteSerializer,
)
from main.apps.antenna.serializers.cell_serializers import (
    BeamControlWriteSerializer,
    CellListWriteSerializer,
    CellReadSerializer,
)
from main.apps.antenna.serializers.ue_position_serializers import (
    UePositionListWriteSerializer,
    UePositionReadSerializer,
)
from main.apps.antenna.services.business.relational_db import SqlDbBusinessService
from main.apps.antenna.services.common.timestamp_service import TimestampService
from main.apps.antenna.services.common.uuid_service import UUIDService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


logger = get_logger(__name__)


def _parse_body(request):
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


class RuController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def measure_cells(request):
        """UE initial/idle selection from this run's channel source, without advancing ticks."""
        import math
        from ran_sim_protocol.physics import UeSpec
        from main.apps.fapi_south.services.optional import dl_tti_pipeline as pipeline
        from main.apps.fapi_south.services.optional.channel_cache_loader import get_channel_cache, is_cached_mode
        from main.apps.physics_client.services.optional.payload_builder import build_path_solver_request
        from main.apps.physics_client.services.optional import physics_http
        try:
            body = _parse_body(request)
            ue_id, position = str(body.get('ue_id') or ''), body.get('position')
            if not ue_id or not isinstance(position, list) or len(position) != 3:
                raise ValueError('ue_id and position [x,y,z] required')
            position = [float(v) for v in position]
            if not all(math.isfinite(v) for v in position):
                raise ValueError('position must be finite')
            if is_cached_mode():
                cache = get_channel_cache()
                if cache is None:
                    return error_response('channel cache unavailable', None, 409)
                from main.apps.phy_low.services.optional.lockstep_clock import get_clock
                scene_ms = int(body.get('scene_sim_ms', get_clock().status()['scene_sim_ms']))
                gains, _ = cache.lookup(scene_ms // max(1, cache.tick_ms), ue_id)
            else:
                req = build_path_solver_request([])
                req.ue_positions = [UeSpec(id=ue_id, position=position)]
                response = physics_http.compute_paths(req)
                gains = (response.path_gain or {}).get(ue_id) or {}
            cell_to_tx = pipeline._build_cell_to_tx_map()
            values = {c.name: pipeline._path_gain_to_rsrp_dbm(float(gains[cell_to_tx[c.name]]), cell_power_dbm=c.power_dbm)
                      for c in Cell.objects.filter(is_active=True)
                      if cell_to_tx.get(c.name) in gains and float(gains[cell_to_tx[c.name]]) > 0}
            return success_response(values, 'cell RSRP', 200)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return error_response('Validation failed', str(exc), 400)
        except physics_http.PhysicsHttpError as exc:
            return error_response('cell measurement unavailable', str(exc), 502)


    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def update_antenna(request):
        try:
            payload = _parse_body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)

        ser = AntennaConfigWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)

        validated = ser.validated_data
        now = TimestampService.get_current_timestamp()
        uuid = UUIDService.generate_uuid("antenna", "")  # 一律新建一筆，取 latest

        entity_data = {
            "antenna_config_uuid": uuid,
            "antenna_config_created_at": now,
            "antenna_config_updated_at": now,
            **validated,
        }
        entity = SqlDbBusinessService.create_entity(AntennaConfig, entity_data)
        logger.info("update_antenna ok: %s rows=%d cols=%d %s/%s",
                    uuid, validated["rows"], validated["cols"],
                    validated["polarization"], validated["pattern"])

        return success_response(AntennaConfigReadSerializer(entity).data, "antenna config updated", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def set_cell_active(request):
        """開/關單一 cell 的發射。body: {cell_id | name, is_active}

        2026-09-22:關站與節能在 DU 端是「不排程」,但 RU 這邊若照舊發射,
        UE 仍然量得到該 cell 的 RSRP —— 與物理相反,也讓 cell_outage /
        energy_saving_state / cell_addition 三種事件在觀測上看不出差別。
        """
        try:
            payload = _parse_body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        name = str(payload.get("cell_id") or payload.get("name") or "").strip()
        if not name:
            return error_response("Validation failed", {"cell_id": "required"}, 400)
        if payload.get("is_active") is None:
            return error_response("Validation failed", {"is_active": "required"}, 400)
        want = bool(payload["is_active"])

        cell = SqlDbBusinessService.filter_entities(Cell).filter(name=name).first()
        if cell is None:
            return error_response("cell not found", name, 404)
        before = bool(cell.is_active)
        cell.is_active = want
        cell.cell_updated_at = TimestampService.get_current_timestamp()
        cell.save(update_fields=["is_active", "cell_updated_at"])
        logger.info("set_cell_active %s: %s → %s", name, before, want)
        return success_response({"cell_id": name, "is_active_before": before,
                                 "is_active_after": want}, "cell active updated", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def set_cell_antenna(request):
        """改單一 cell 的天線方位／下傾。body: {cell_id | name, azimuth_deg?, tilt_deg?}

        2026-09-22:給外部 Agent 的 antenna_change 事件(I-3)用。
        兩個角度都是可選的,只給一個就只改一個。

        ⚠ 只有 live 模式改得動實際物理。cached 模式下 path gain 是預算時
        用當時的方位射線追蹤出來的,烘在 .npz 裡,執行期改這張表不會改變任何
        傳播結果 —— 所以 orchestrator 端在 cached 模式會直接退回這個事件,
        不會走到這支。這裡不自行判斷模式,保持單一職責。
        """
        try:
            payload = _parse_body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)

        name = str(payload.get("cell_id") or payload.get("name") or "").strip()
        if not name:
            return error_response("Validation failed", {"cell_id": "required"}, 400)
        if payload.get("azimuth_deg") is None and payload.get("tilt_deg") is None:
            return error_response("Validation failed",
                                  {"azimuth_deg/tilt_deg": "至少要給一個"}, 400)

        cell = SqlDbBusinessService.filter_entities(Cell).filter(name=name).first()
        if cell is None:
            return error_response("cell not found", name, 404)

        before = {"azimuth_deg": float(cell.azimuth_deg),
                  "tilt_deg": float(cell.tilt_deg or 0.0)}
        fields = []
        for key in ("azimuth_deg", "tilt_deg"):
            if payload.get(key) is None:
                continue
            try:
                setattr(cell, key, float(payload[key]))
            except (TypeError, ValueError):
                return error_response("Validation failed", {key: "must be a number"}, 400)
            fields.append(key)
        cell.cell_updated_at = TimestampService.get_current_timestamp()
        cell.save(update_fields=[*fields, "cell_updated_at"])
        after = {"azimuth_deg": float(cell.azimuth_deg),
                 "tilt_deg": float(cell.tilt_deg or 0.0)}
        logger.info("set_cell_antenna %s: %s → %s", name, before, after)
        return success_response({"cell_id": name, "before": before, "after": after,
                                 "changed": fields},
                                "cell antenna updated", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def set_cell_power(request):
        """改單一 cell 的發射功率(dBm)。body: {cell_id | name, power_dbm}

        2026-09-22:給外部 Agent 的 tx_power_change 事件(I-3)用。
        不走 update_cells —— 那是全量替換,要改一顆得把整份清單重送,
        少送任何一顆就會被刪掉。執行期的單點改動用單點介面才安全。

        發射功率在 RU 是執行期疊到(快取的)path gain 上的,所以 cached 模式也改得動。
        """
        try:
            payload = _parse_body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)

        name = str(payload.get("cell_id") or payload.get("name") or "").strip()
        if not name:
            return error_response("Validation failed", {"cell_id": "required"}, 400)
        if payload.get("power_dbm") is None:
            return error_response("Validation failed", {"power_dbm": "required"}, 400)
        try:
            power = float(payload["power_dbm"])
        except (TypeError, ValueError):
            return error_response("Validation failed", {"power_dbm": "must be a number"}, 400)

        cell = SqlDbBusinessService.filter_entities(Cell).filter(name=name).first()
        if cell is None:
            return error_response("cell not found", name, 404)

        before = float(cell.power_dbm)
        cell.power_dbm = power
        cell.cell_updated_at = TimestampService.get_current_timestamp()
        cell.save(update_fields=["power_dbm", "cell_updated_at"])
        logger.info("set_cell_power %s: %.1f → %.1f dBm", name, before, power)
        return success_response(
            {"cell_id": name, "power_dbm_before": before, "power_dbm_after": power},
            "cell power updated", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def update_cells(request):
        try:
            payload = _parse_body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)

        ser = CellListWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)

        cells_in = ser.validated_data["cells"]
        if not cells_in:
            return error_response("cells must not be empty", "use POST with at least 1 cell", 400)

        now = TimestampService.get_current_timestamp()

        # 全量替換策略：先清掉沒在這次列表的 cell，再 upsert 提交的
        incoming_names = [c["name"] for c in cells_in]
        SqlDbBusinessService.filter_entities(Cell).exclude(name__in=incoming_names).delete()

        result = []
        for c in cells_in:
            uuid = UUIDService.generate_uuid("cell", c["name"])
            defaults = {
                "cell_uuid": uuid,
                "pci": c["pci"],
                "azimuth_deg": c["azimuth_deg"],
                "tilt_deg": float(c.get("tilt_deg", 0.0) or 0.0),
                "position_x": c["position"]["x"],
                "position_y": c["position"]["y"],
                "position_z": c["position"]["z"],
                "frequency_ghz": c["frequency_ghz"],
                "bandwidth_mhz": c["bandwidth_mhz"],
                "gnb_id": c.get("gnb_id", ""),
                "power_dbm": c.get("power_dbm", 23.0),
                # 起始啟用狀態。False = 備用 cell,不發射(見 _build_active_cell_set)
                "is_active": bool(c.get("is_active", True)),
                "cell_updated_at": now,
                "cell_created_at": now,
            }
            obj = SqlDbBusinessService.upsert_entity(Cell, lookup={"name": c["name"]}, defaults=defaults)
            result.append(obj)

        logger.info("update_cells ok: %d cells", len(result))
        return success_response(
            CellReadSerializer(result, many=True).data,
            f"updated {len(result)} cells",
            200,
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def update_ues(request):
        try:
            payload = _parse_body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)

        ser = UePositionListWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)

        ues_in = ser.validated_data["ues"]
        if not ues_in:
            return error_response("ues must not be empty", "use POST with at least 1 ue", 400)

        now = TimestampService.get_current_timestamp()

        # `clear_stale` 預設 True(對齊原行為);scenario_driver 高倍率 per-tick 推位置
        # 時改傳 False 跳過 DELETE,把 18ms/call 壓到 ~3ms。stale 在 scenario start
        # 由 sync_scene_to_scenario 那條 path 清過了。
        clear_stale = bool(payload.get("clear_stale", True))
        if clear_stale:
            incoming_ids = [u["id"] for u in ues_in]
            deleted, _ = SqlDbBusinessService.filter_entities(UePosition).exclude(ue_id__in=incoming_ids).delete()
            if deleted:
                logger.info("update_ues cleared %d stale UEs", deleted)

        result = []
        for u in ues_in:
            uuid = UUIDService.generate_uuid("ue", u["id"])
            velocity = u.get("velocity") or {"x": 0.0, "y": 0.0, "z": 0.0}
            defaults = {
                "ue_position_uuid": uuid,
                "position_x": u["position"]["x"],
                "position_y": u["position"]["y"],
                "position_z": u["position"]["z"],
                "velocity_x": velocity["x"],
                "velocity_y": velocity["y"],
                "velocity_z": velocity["z"],
                "ue_position_updated_at": now,
                "ue_position_created_at": now,
            }
            obj = SqlDbBusinessService.upsert_entity(
                UePosition, lookup={"ue_id": u["id"]}, defaults=defaults,
            )
            result.append(obj)

        logger.debug("update_ues ok: %d UEs", len(result))
        return success_response(
            UePositionReadSerializer(result, many=True).data,
            f"updated {len(result)} ues",
            200,
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def set_channel_mode(request):
        """Phase B B.6 — runtime 切 RU channel mode (live / cached) + 載入 cache。

        Body: {"mode": "live" | "cached", "scenario_id": str (cached 時必填)}

        side effects:
          - 設 os.environ RU_CHANNEL_MODE / RU_SCENARIO_ID
          - 若 mode=cached:呼 channel_cache_loader.reload_cache() 即時 load 對應 npz
          - 若 mode=live :singleton 不 reload (下次 dl_tti 自動走 physics path)

        Returns: { mode, scenario_id, loaded, ues, cells, total_ticks }
        """
        try:
            payload = _parse_body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        mode = str(payload.get("mode", "")).lower().strip()
        scenario_id = str(payload.get("scenario_id", "")).strip()
        if mode not in ("live", "cached"):
            return error_response("mode must be 'live' or 'cached'", {}, 400)
        if mode == "cached" and not scenario_id:
            return error_response("mode=cached requires scenario_id", {}, 400)

        os.environ["RU_CHANNEL_MODE"] = mode
        os.environ["RU_SCENARIO_ID"] = scenario_id if mode == "cached" else ""

        from main.apps.fapi_south.services.optional.channel_cache_loader import (
            reload_cache, write_mode_file,
        )
        # 寫 disk file 讓所有 gunicorn worker 看到 mode 改變(不僅 env)
        write_mode_file(mode, scenario_id if mode == "cached" else "")
        info = {
            "mode": mode,
            "scenario_id": os.environ.get("RU_SCENARIO_ID") or "",
            "loaded": False,
            "ues": 0,
            "cells": 0,
            "total_ticks": 0,
        }
        if mode == "cached":
            cache = reload_cache()
            if cache is None:
                return error_response(
                    f"Failed to load channel cache for scenario_id={scenario_id}",
                    {}, 500,
                )
            info.update({
                "loaded": True,
                "ues": len(cache.ue_names),
                "cells": len(cache.cell_names),
                "total_ticks": cache.total_ticks,
            })
        logger.info("set_channel_mode: %s", info)
        return success_response(info, f"channel mode set to {mode}", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def set_inter_freq(request):
        """runtime 設 RU live SINR 的 inter_freq(劇本 start 套用,免 RU 專用 env)。
        Body: {"inter_freq": bool}。True = 各 cell 不同頻不互擾,live SINR 跳過他 cell 干擾累加
        (對齊 DU cached);讓 CCO 等劇本的 inter_freq 也接到 live SINR 路徑。"""
        try:
            payload = _parse_body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        enabled = bool(payload.get("inter_freq", False))
        from main.apps.fapi_south.services.optional.dl_tti_pipeline import set_inter_freq
        set_inter_freq(enabled)
        logger.info("set_inter_freq: %s", enabled)
        return success_response({"inter_freq": enabled}, "inter_freq applied", 200)


class BeamController:
    """B2(2026-09-16):RIC 可控的波束狀態(per cell)。

    O-RAN 語意:electrical_tilt / active_beam_ids 是 O1 / OFH M-plane 的慢迴路,
    max_layers 是 E2 的快迴路。我方目前只有 E2 通道,所以三者都經 CU 的 RC (2,8) 進來,
    註記在這裡,之後接 O1 模擬端點時再分流。
    """

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def set(request: HttpRequest):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        ser = BeamControlWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        v = ser.validated_data
        cell = Cell.objects.filter(name=v["cell_id"]).first()
        if cell is None:
            return error_response("Not found", f"cell {v['cell_id']}", 404)
        changed = {}
        if v.get("electrical_tilt_deg") is not None:
            cell.electrical_tilt_deg = float(v["electrical_tilt_deg"]); changed["electrical_tilt_deg"] = cell.electrical_tilt_deg
        if v.get("active_beam_ids") is not None:
            cell.active_beam_ids = [int(x) for x in v["active_beam_ids"]]; changed["active_beam_ids"] = cell.active_beam_ids
        if v.get("max_layers") is not None:
            cell.max_layers = int(v["max_layers"]); changed["max_layers"] = cell.max_layers
        if v.get("trx_active_ratio") is not None:
            cell.trx_active_ratio = float(v["trx_active_ratio"]); changed["trx_active_ratio"] = cell.trx_active_ratio
        if v.get("beam_taper") is not None:
            cell.beam_taper = "" if v["beam_taper"] == "none" else v["beam_taper"]; changed["beam_taper"] = cell.beam_taper
        if v.get("beam_power_offsets_db") is not None:
            cell.beam_power_offsets_db = {str(int(k)): float(x) for k, x in v["beam_power_offsets_db"].items()}
            changed["beam_power_offsets_db"] = cell.beam_power_offsets_db
        if changed:
            cell.cell_updated_at = TimestampService.get_current_timestamp()
            cell.save()
        logger.info("set_beam_control %s → %s", cell.name, changed)
        return success_response({"cell_id": cell.name, "changed": changed,
                                 "electrical_tilt_deg": cell.electrical_tilt_deg,
                                 "active_beam_ids": cell.active_beam_ids,
                                 "max_layers": cell.max_layers,
                                 "trx_active_ratio": cell.trx_active_ratio, "beam_taper": cell.beam_taper,
                                 "beam_power_offsets_db": cell.beam_power_offsets_db}, "beam control applied", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request: HttpRequest):
        rows = [{"cell_id": c.name, "electrical_tilt_deg": c.electrical_tilt_deg,
                 "active_beam_ids": c.active_beam_ids or [], "max_layers": c.max_layers,
                 "trx_active_ratio": c.trx_active_ratio, "beam_taper": c.beam_taper,
                 "beam_power_offsets_db": c.beam_power_offsets_db or {},
                 "mechanical_tilt_deg": c.tilt_deg, "azimuth_deg": c.azimuth_deg}
                for c in Cell.objects.all().order_by("name")]
        return success_response(rows, "ok", 200)
