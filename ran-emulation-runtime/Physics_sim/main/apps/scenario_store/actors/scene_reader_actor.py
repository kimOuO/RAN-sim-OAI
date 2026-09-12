"""Scene readers — 鏡像 Omniverse 的 GNBReader / UEReader / BuildingController /
SceneLayoutReader,輸出形狀逐字相同,讓 Physics scene_gateway 與 Dashboard 可直接改指
到 Physics 取得場景幾何。
"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.scenario_store.models import BuildingObject, GnbConfig, UeConfig
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


def _ok_post(request):
    try:
        json.loads(request.body or b"{}")
        return True
    except json.JSONDecodeError:
        return True  # readers 不需要 body,容忍空/壞 body


def _gnb_repr(g: "GnbConfig") -> dict:
    return {
        "gnb_uuid": g.gnb_uuid,
        "name": g.name,
        "position": [float(g.pos_x or 0), float(g.pos_y or 0), float(g.pos_z or 0)],
        "frequency_ghz": float((g.freq_mhz or 0) / 1000.0),
        "power_dbm": float(g.power_dbm or 0),
        "bandwidth_mhz": float((g.bw_hz or 0) / 1_000_000.0),
        "active": bool(g.active),
        "cells": g.cells or [],
        "created_at": g.gnb_created_at.isoformat() if g.gnb_created_at else None,
        "updated_at": g.gnb_updated_at.isoformat() if g.gnb_updated_at else None,
    }


def _ue_repr(u: "UeConfig") -> dict:
    r = {
        "name": u.name,
        "position": [float(u.pos_x or 0), float(u.pos_y or 0), float(u.pos_z or 0)],
        "color": [float(u.color_r), float(u.color_g), float(u.color_b)],
        "waypoints": u.waypoints_json,
        "speed_mps": float(u.speed_mps or 1.0),
        "loop": bool(u.loop),
        "target_height_m": u.target_height_m,
    }
    if u.usd_path:
        r["usd_path"] = u.usd_path
    return r


def _bld_repr(b: "BuildingObject") -> dict:
    return {
        "building_uuid": b.building_uuid,
        "name": b.name,
        "scene_id": b.scene_id,
        "position": [b.pos_x, b.pos_y, b.pos_z],
        "size": [b.size_x, b.size_y, b.size_z],
        "color": [b.color_r, b.color_g, b.color_b],
        "usd_path": b.usd_path,
        "preset_type": b.preset_type,
        "target_height_m": b.target_height_m,
        "rotation_xyz_deg": [b.rot_x, b.rot_y, b.rot_z],
        "material": b.material,
        "created_at": b.building_created_at.isoformat(),
        "updated_at": b.building_updated_at.isoformat(),
    }


class GNBReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):  # noqa: ARG004
        return success_response([_gnb_repr(g) for g in GnbConfig.objects.all()])


class UEReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):  # noqa: ARG004
        return success_response([_ue_repr(u) for u in UeConfig.objects.all()])


class BuildingController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):  # noqa: ARG004
        return success_response([_bld_repr(b) for b in BuildingObject.objects.all()])


class SceneLayoutReader:
    """Full map payload(buildings + gnbs + ues + ground)給 trajectory editor。
    gNB 的 freq 轉成 freq_mhz/bw_hz 與 Omniverse SceneLayoutReader 一致。"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):  # noqa: ARG004
        gnbs = []
        for g in GnbConfig.objects.all():
            gnbs.append({
                "name": g.name,
                "prim_path": f"/World/{g.name}",
                "position": [g.pos_x, g.pos_y, g.pos_z],
                "freq_mhz": float(g.freq_mhz or 0),
                "bw_hz": float(g.bw_hz or 0),
                "power_dbm": float(g.power_dbm or 0),
                "active": bool(g.active),
                "color": [g.color_r, g.color_g, g.color_b],
                "cells": g.cells or [],
                "target_height_m": g.target_height_m,
            })
        ues = []
        for u in UeConfig.objects.all():
            entry = {
                "name": u.name,
                "prim_path": f"/World/{u.name}",
                "position": [u.pos_x, u.pos_y, u.pos_z],
                "color": [u.color_r, u.color_g, u.color_b],
                "speed_mps": float(u.speed_mps or 1.0),
            }
            if u.waypoints_json:
                entry["waypoints"] = u.waypoints_json
            if u.target_height_m is not None:
                entry["target_height_m"] = u.target_height_m
            ues.append(entry)
        buildings = []
        for b in BuildingObject.objects.all():
            buildings.append({
                "name": b.name,
                "prim_path": f"/World/{b.name}",
                "position": [b.pos_x, b.pos_y, b.pos_z],
                "size": [b.size_x, b.size_y, b.size_z],
                "color": [b.color_r, b.color_g, b.color_b],
            })
        return success_response({
            "buildings": buildings, "gnbs": gnbs, "ues": ues,
            "ground": {"size": 1000},
        })
