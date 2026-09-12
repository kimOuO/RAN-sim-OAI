"""SceneGatewayActor — 前端初始化場景 → RAN-sim + Omniverse。"""
import time
import uuid

import requests
from rest_framework.decorators import api_view

from main.apps.ran_signal.serializers.config_serializers import (
    SceneGatewayInitSerializer,
    SceneGatewayInitResponseSerializer,
)
# NOTE (restructure/4-system-split): SimLoopService moved to _legacy/du_candidates/.
# Tick orchestration is DU's responsibility now. SceneGateway only handles physics scene init.
from main.apps.ran_signal.services.business.sionna_operations import SionnaBusinessService
from main.apps.ran_signal.services.optional.ran_calculation.scene_frequency import (
    SceneFrequencyMismatch,
)
from main.utils.env_loader import get_str
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


logger = get_logger(__name__)
OMNIVERSE_BACKEND_URL = get_str("OMNIVERSE_BACKEND_URL", "http://localhost:8001")
# 場景幾何來源(gNB/UE/建築 readers):預設沿用 Omniverse;設 SCENARIO_STORE_URL
# (如 Physics 自己 http://localhost:8000)即可脫離 Omniverse。端點形狀相同。
# SimSession/SceneIngestor 仍走 Omniverse(選配遙測,掛掉時 graceful skip)。
SCENARIO_STORE_URL = get_str("SCENARIO_STORE_URL", "") or OMNIVERSE_BACKEND_URL


class SceneGatewayActor:
    """初始化場景：接收前端場景 → RAN-sim + Omniverse。"""

    @staticmethod
    @api_view(["POST"])
    def init(request):
        """初始化場景。

        流程：
          1. 驗證請求
          2. 在 RAN-sim 中建置場景（Sionna + geometry）
          3. 在 Omniverse 中建立 SimSession → 拿回 session_uuid
          4. 儲存 session_uuid 到 SimLoopService
          5. 返回 session_uuid 給前端

        Args:
            request.data: {
                scene_id: str,
                geometry_source: {type, buildings, ground},
                gnbs: [{name, pci, cell_id, position, frequency_ghz, power_dbm, bandwidth_mhz}],
                ues: [{name, role, qos_5qi}]
            }

        Returns:
            {scene_id, session_uuid, gnb_count, ue_count, building_count, sionna_rebuild_ms}
        """
        # 1. 驗證
        req_ser = SceneGatewayInitSerializer(data=request.data)
        if not req_ser.is_valid():
            return error_response(
                "Invalid scene configuration",
                errors=req_ser.errors,
                http_status=400,
            )

        validated = req_ser.validated_data
        scene_id = validated["scene_id"]
        logger.info("SceneGatewayActor.init scene_id=%s", scene_id)

        # 1.5 DB-only mode fallback：若未提供 geometry_source / gnbs，從 Omniver-RAN DB 讀取
        if not validated.get("geometry_source"):
            try:
                logger.info("DB-mode: fetching buildings from Omniver-RAN")
                resp = requests.post(
                    f"{SCENARIO_STORE_URL}/api/v0.1/RAN/Scene/BuildingController/read",
                    json={},
                    timeout=5,
                )
                if resp.status_code == 200:
                    buildings_data = resp.json().get("data", [])
                    validated["geometry_source"] = {
                        "type": "buildings_json",
                        "buildings": [
                            {
                                "name": b.get("name", f"building_{i}"),
                                "position": b.get("position", [0, 0, 0]),
                                "size": b.get("size", [10, 10, 10]),
                                "color": b.get("color", [0.75, 0.75, 0.75]),
                                "rotation_xyz_deg": b.get("rotation_xyz_deg", [-90, 0, 0]),
                                "target_height_m": b.get("target_height_m"),
                                "material": b.get("material", "concrete"),
                                "usd_path": b.get("usd_path", ""),
                                "preset_type": b.get("preset_type", ""),
                            }
                            for i, b in enumerate(buildings_data)
                        ],
                    }
                    logger.info("Loaded %d buildings from DB", len(buildings_data))
                else:
                    logger.warning("Building read failed: status=%d, using empty", resp.status_code)
                    validated["geometry_source"] = {"type": "buildings_json", "buildings": []}
            except requests.RequestException as e:
                logger.warning("Failed to fetch buildings from DB: %s", e)
                validated["geometry_source"] = {"type": "buildings_json", "buildings": []}

        if not validated.get("gnbs"):
            try:
                logger.info("DB-mode: fetching gNBs from Omniver-RAN")
                resp = requests.post(
                    f"{SCENARIO_STORE_URL}/api/v0.1/RAN/GNB/GNBReader/read",
                    json={},
                    timeout=5,
                )
                if resp.status_code == 200:
                    gnbs_data = resp.json().get("data", [])
                    # Convert position from {"x":..,"y":..,"z":..} to [x, y, z] for Sionna
                    for g in gnbs_data:
                        pos = g.get("position", {})
                        if isinstance(pos, dict):
                            g["position"] = [pos.get("x", 0), pos.get("y", 0), pos.get("z", 0)]
                    validated["gnbs"] = gnbs_data
                    logger.info("Loaded %d gNBs from DB", len(gnbs_data))
                else:
                    logger.warning("gNB read failed: status=%d, using empty", resp.status_code)
                    validated["gnbs"] = []
            except requests.RequestException as e:
                logger.warning("Failed to fetch gNBs from DB: %s", e)
                validated["gnbs"] = []

        if not validated.get("ues"):
            try:
                logger.info("DB-mode: fetching UEs from Omniver-RAN")
                resp = requests.post(
                    f"{SCENARIO_STORE_URL}/api/v0.1/RAN/UE/UEReader/read",
                    json={},
                    timeout=5,
                )
                if resp.status_code == 200:
                    ues_data = resp.json().get("data", [])
                    validated["ues"] = ues_data
                    logger.info("Loaded %d UEs from DB", len(ues_data))
                else:
                    logger.warning("UE read failed: status=%d, using empty", resp.status_code)
                    validated["ues"] = []
            except requests.RequestException as e:
                logger.warning("Failed to fetch UEs from DB: %s", e)
                validated["ues"] = []

        # 2. 在 RAN-sim 中建置場景
        try:
            started_ms = time.time() * 1000
            push_payload = {
                "scene_id": scene_id,
                "override_mode": "full",
                "geometry_source": validated.get("geometry_source"),
                "gnbs": validated.get("gnbs"),
                "ues": validated.get("ues"),
            }
            if validated.get("scene_antenna_config"):
                push_payload["scene_antenna_config"] = validated["scene_antenna_config"]
            sionna_result = SionnaBusinessService.apply_override(push_payload)
            sionna_rebuild_ms = int(time.time() * 1000 - started_ms)
            logger.info(
                "Sionna scene loaded: scene_id=%s rebuild_ms=%d gnbs=%d ues=%d",
                scene_id,
                sionna_rebuild_ms,
                sionna_result.get("gnb_count", 0),
                sionna_result.get("ue_count", 0),
            )
        except SceneFrequencyMismatch as e:
            logger.warning("Sionna init rejected: %s", e)
            return error_response(str(e), http_status=400)
        except Exception as e:
            logger.exception("Failed to load scene in Sionna")
            return error_response(f"Sionna scene load failed: {e}", http_status=500)

        # 3. 在 Omniverse 中建立 SimSession（可選，失敗不影響主要功能）
        session_uuid = str(uuid.uuid4())
        omniverse_connected = False
        try:
            resp = requests.post(
                f"{OMNIVERSE_BACKEND_URL}/api/v0.1/RAN/SimSession/SimSessionController/create",
                json={
                    "session_uuid": session_uuid,
                    "scene_id": scene_id,
                    "scene_snapshot": {
                        "buildings": validated.get("geometry_source", {}).get("buildings", []),
                        "gnbs": validated.get("gnbs", []),
                        "ues": validated.get("ues", []),
                    },
                },
                timeout=10,
            )
            if resp.status_code in (200, 201):
                logger.info("Omniverse SimSession created: session_uuid=%s", session_uuid)
                omniverse_connected = True
            else:
                logger.warning(
                    "Omniverse SimSession create failed: status=%d body=%s",
                    resp.status_code,
                    resp.text,
                )
        except requests.RequestException as e:
            logger.warning("Failed to contact Omniverse (non-blocking): %s", e)

        # 4. 初始化 Omniverse 3D 場景（SceneIngestor）
        try:
            scene_ingest_payload = {
                "session_uuid": session_uuid,
                "scene_id": scene_id,
                "buildings": validated.get("geometry_source", {}).get("buildings", []),
                "ground": validated.get("geometry_source", {}).get("ground"),
            }
            resp = requests.post(
                f"{OMNIVERSE_BACKEND_URL}/api/v0.1/RAN/Ingest/SceneIngestor/create",
                json=scene_ingest_payload,
                timeout=10,
            )
            if resp.status_code not in (200, 201):
                logger.warning("SceneIngestor create failed: status=%d", resp.status_code)
            else:
                logger.info("SceneIngestor ingested: session_uuid=%s", session_uuid)
        except requests.RequestException as e:
            logger.warning("SceneIngestor failed (non-blocking): %s", e)

        # 5. (restructure/4-system-split) SimLoop init removed — tick driver moved to DU.
        #    Physics_sim only handles scene initialization. DU will own SimLoop start/stop.
        logger.info("Scene initialized; tick driver is now in DU (call DU's TickController)")

        # 6. 組裝回應
        response_data = {
            "scene_id": scene_id,
            "session_uuid": session_uuid,
            "gnb_count": sionna_result.get("gnb_count", 0),
            "ue_count": sionna_result.get("ue_count", 0),
            "building_count": len(validated.get("geometry_source", {}).get("buildings", [])),
            "sionna_rebuild_ms": sionna_rebuild_ms,
        }

        resp_ser = SceneGatewayInitResponseSerializer(response_data)
        return success_response(
            resp_ser.data,
            message="Scene initialized",
            http_status=201,
        )
