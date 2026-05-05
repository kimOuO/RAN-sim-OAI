"""SimLoop Service — 管理持續的 RAN 模擬 loop，每 500ms 推進一步。

架構：
  1. setup(ues) — 接收 UE 軌跡（waypoints + 速度），儲存狀態
  2. start() — 啟動線程，每 500ms 執行 _tick()
  3. _tick() — 計算 UE 位置 → compute → 推給 Omniverse
  4. stop() — 停止 loop，通知 Omniverse session ended

設計原則：
  - Singleton，維持 loop 狀態在內存
  - 線性插值：在 waypoint 之間按速度推進
  - 線程驅動：使用 Thread，不阻塞 HTTP handler
  - 無狀態 HTTP：每個 tick 保存信號數據供前端查詢
"""
import asyncio
import json
import math
import time
import threading
import uuid
from typing import Any, Optional

import requests

try:
    import websockets
except ImportError:
    websockets = None

from main.apps.ran_signal.services.business.sionna_operations import SionnaBusinessService
from main.apps.ran_signal.services.common.timestamp_service import TimestampService
from main.utils.env_loader import get_int, get_str
from main.utils.logger import get_logger

log = get_logger(__name__)

OMNIVERSE_BACKEND_URL = get_str("OMNIVERSE_BACKEND_URL", "http://localhost:8001")
_default_omni_ws = OMNIVERSE_BACKEND_URL.replace("http://", "ws://").replace("https://", "wss://") + "/api/v0.1/RAN/Ingest/ws/"
OMNIVERSE_WS_URL = get_str("OMNIVERSE_WS_URL", _default_omni_ws)
SIM_LOOP_TICK_MS = get_int("SIM_LOOP_TICK_MS", 500)


class SimLoopService:
    """管理模擬 loop 的單例服務。"""

    # Loop 狀態
    _loop_thread: Optional[threading.Thread] = None
    _is_running: bool = False

    # Session 識別
    _session_uuid: Optional[str] = None
    _scene_id: Optional[str] = None

    # UE 軌跡狀態
    # ue_state[name] = {
    #   "waypoints": [[x,y,z], ...],
    #   "speed_mps": float,
    #   "loop": bool,
    #   "current_wp_index": int,           # 當前目標 waypoint 的索引
    #   "progress_in_segment": float,      # [0, 1) 在當前線段內的進度
    #   "current_position": [x, y, z],
    #   "total_distance": float,           # 整個軌跡的總長度（公尺）
    #   "elapsed_distance": float,         # 目前走過的總距離
    # }
    _ue_states: dict[str, dict[str, Any]] = {}

    # Counters
    _tick_count: int = 0
    _started_at_ms: Optional[int] = None
    _last_tick_timestamp_ms: int = 0

    # WebSocket connection to Omniver-RAN ingest endpoint
    _ws_connection: Optional[Any] = None

    # 最新信號數據（供前端查詢）
    # ── API ─────────────────────────────────────────────────────

    @classmethod
    def setup(cls, session_uuid: str, scene_id: str, ues: list[dict[str, Any]]) -> dict[str, Any]:
        """設定 UE 軌跡（不啟動 loop）。

        Args:
            session_uuid: Omniverse session ID
            scene_id: 場景 ID
            ues: [{name, waypoints, speed_mps, loop}]

        Returns:
            {ues_configured, total_duration_ms}
        """
        log.info("SimLoopService.setup session=%s scene=%s ues=%d", session_uuid, scene_id, len(ues))

        cls._session_uuid = session_uuid
        cls._scene_id = scene_id
        cls._ue_states = {}

        for ue_cfg in ues:
            name = ue_cfg["name"]
            waypoints = ue_cfg.get("waypoints", [])
            speed_mps = ue_cfg.get("speed_mps", 1.0)
            loop = ue_cfg.get("loop", True)

            # 驗證
            if len(waypoints) < 2:
                log.warning("UE %s waypoints < 2, skipping", name)
                continue

            # 計算總距離
            total_distance = cls._calculate_total_distance(waypoints)
            total_duration_ms = int((total_distance / speed_mps) * 1000) if speed_mps > 0 else 0

            cls._ue_states[name] = {
                "waypoints": waypoints,
                "speed_mps": speed_mps,
                "loop": loop,
                "current_wp_index": 1,  # 從第 1 個 waypoint 開始（目標）
                "progress_in_segment": 0.0,
                "current_position": list(waypoints[0]),
                "total_distance": total_distance,
                "elapsed_distance": 0.0,
            }

            log.info(
                "UE %s configured: waypoints=%d speed=%.1f m/s total_distance=%.1f m duration=%.1f s",
                name, len(waypoints), speed_mps, total_distance, total_duration_ms / 1000.0,
            )

        cls._tick_count = 0
        cls._started_at_ms = None
        cls._last_tick_timestamp_ms = 0

        return {
            "ues_configured": len(cls._ue_states),
            "total_duration_ms": max(
                ((cls._ue_states[name]["total_distance"] / cls._ue_states[name]["speed_mps"] * 1000)
                if cls._ue_states[name]["speed_mps"] > 0
                else 0
                for name in cls._ue_states),
                default=0
            ),
        }

    @classmethod
    def start(cls) -> dict[str, Any]:
        """啟動模擬線程，開始模擬。"""
        log.info("SimLoopService.start session=%s", cls._session_uuid)

        if cls._is_running:
            log.warning("SimLoop already running")
            return {"status": "already_started"}

        if not cls._ue_states:
            log.error("No UE configured, cannot start")
            return {"status": "error", "message": "No UE configured"}

        # 若未設定 session_uuid，則生成新的
        if not cls._session_uuid:
            cls._session_uuid = str(uuid.uuid4())
            cls._scene_id = "default"  # 或可從環境變數讀取

            # 取得當前場景快照
            try:
                scene_resp = requests.post(
                    f"{OMNIVERSE_BACKEND_URL}/api/v0.1/RAN/Scene/SceneLayoutReader/read",
                    json={},
                    timeout=5
                )
                scene_config = scene_resp.json().get("data", {})
                log.info("Retrieved scene snapshot: %d buildings, %d gnbs",
                        len(scene_config.get("buildings", [])),
                        len(scene_config.get("gnbs", [])))
            except Exception as e:
                log.warning("Failed to get scene snapshot: %s", e)
                scene_config = {}

            # 建立 SimSession
            try:
                create_resp = requests.post(
                    f"{OMNIVERSE_BACKEND_URL}/api/v0.1/RAN/SimSession/SimSessionController/create",
                    json={
                        "session_uuid": cls._session_uuid,
                        "scene_id": cls._scene_id,
                        "scene_snapshot": scene_config
                    },
                    timeout=5
                )
                log.info("Created SimSession %s: status=%d", cls._session_uuid, create_resp.status_code)
            except Exception as e:
                log.error("Failed to create SimSession: %s", e)
                return {"status": "error", "message": f"Failed to create session: {e}"}

        cls._is_running = True
        cls._tick_count = 0
        cls._started_at_ms = TimestampService.now_ms()
        cls._last_tick_timestamp_ms = cls._started_at_ms

        # 啟動後臺線程運行 SimLoop
        cls._loop_thread = threading.Thread(target=cls._run_loop_sync, daemon=True)
        cls._loop_thread.start()
        log.info("SimLoop thread started")

        return {"status": "started", "session_uuid": cls._session_uuid, "tick_count": 0}

    @classmethod
    def stop(cls) -> dict[str, Any]:
        """停止 loop 並通知 Omniverse session ended。"""
        log.info("SimLoopService.stop session=%s tick_count=%d", cls._session_uuid, cls._tick_count)

        cls._is_running = False

        if cls._loop_thread is not None:
            cls._loop_thread.join(timeout=2)
            cls._loop_thread = None

        # 通知 Omniverse session ended
        if cls._session_uuid:
            try:
                resp = requests.post(
                    f"{OMNIVERSE_BACKEND_URL}/api/v0.1/RAN/SimSession/SimSessionController/end",
                    json={"session_uuid": cls._session_uuid},
                    timeout=5,
                )
                log.info("Notified Omniverse session end: status=%d", resp.status_code)
            except Exception as e:
                log.error("Failed to notify Omniverse: %s", e)

        result = {
            "status": "stopped",
            "session_uuid": cls._session_uuid,
            "tick_count": cls._tick_count,
            "elapsed_ms": TimestampService.now_ms() - (cls._started_at_ms or 0) if cls._started_at_ms else 0,
        }

        # 重置 session 狀態，下次 start() 時才能建立新 session
        cls._session_uuid = None
        cls._scene_id = None

        return result

    @classmethod
    def status(cls) -> dict[str, Any]:
        """查詢當前狀態。"""
        return {
            "is_running": cls._is_running,
            "session_uuid": cls._session_uuid,
            "scene_id": cls._scene_id,
            "ue_count": len(cls._ue_states),
            "tick_count": cls._tick_count,
            "started_at_ms": cls._started_at_ms,
            "elapsed_ms": TimestampService.now_ms() - cls._started_at_ms if cls._started_at_ms else 0,
        }

    @classmethod
    def get_ue_positions(cls) -> dict[str, list[float]]:
        """取得所有 UE 的當前位置。

        Returns:
            {ue_name: [x, y, z], ...}
        """
        positions = {}
        for ue_name, ue_state in cls._ue_states.items():
            positions[ue_name] = ue_state.get("current_position", [0, 0, 0])
        return positions

    # ── Internal ─────────────────────────────────────────────────

    @classmethod
    def _run_loop_sync(cls) -> None:
        """內部同步 loop：每 500ms 執行一次 _tick()（線程版）。"""
        log.info("SimLoop._run_loop_sync started")

        try:
            while cls._is_running:
                try:
                    # 同步執行 tick（計算 UE 位置、compute、保存信號數據）
                    cls._tick_sync()
                except Exception as e:
                    log.exception("Error in _tick_sync: %s", e)
                    # 繼續運行，不中斷 loop

                # 下一個 tick 的延遲
                time.sleep(SIM_LOOP_TICK_MS / 1000.0)
        finally:
            log.info("SimLoop._run_loop_sync ended")

    @classmethod
    async def _run_loop(cls) -> None:
        """內部 asyncio loop：每 500ms 執行一次 _tick()。"""
        log.info("SimLoop._run_loop started")

        try:
            while cls._is_running:
                try:
                    await cls._tick()
                except Exception as e:
                    log.exception("Error in _tick: %s", e)
                    # 繼續運行，不中斷 loop

                # 下一個 tick 的延遲
                await asyncio.sleep(SIM_LOOP_TICK_MS / 1000.0)
        except asyncio.CancelledError:
            log.info("SimLoop._run_loop cancelled")
        finally:
            log.info("SimLoop._run_loop ended")

    @classmethod
    def _tick_sync(cls) -> None:
        """每 tick 執行：推進 UE → compute → 保存信號數據（同步版）。"""
        cls._tick_count += 1
        now_ms = TimestampService.now_ms()

        # 1. 推進各 UE 位置
        for ue_name in cls._ue_states:
            cls._advance_ue(ue_name, SIM_LOOP_TICK_MS)

        # 2. 準備 compute 請求
        ue_positions = []
        for ue_name, state in cls._ue_states.items():
            ue_positions.append({
                "id": ue_name,
                "position": state["current_position"],
                "velocity": [0, 0, 0],
            })

        # 3. 調用 RAN-sim compute
        try:
            compute_result = SionnaBusinessService.compute_tick(
                timestamp_ms=now_ms,
                scene_id=cls._scene_id,
                ue_positions=ue_positions,
            )
        except Exception as e:
            log.error("Compute failed: %s", e)
            return

        # 保存最新信號數據供前端查詢
        ue_status = compute_result.get("ue_status", [])

        # 4. 推給 Omniverse via WebSocket（可選）
        try:
            cls._send_to_omniverse_ws_sync(now_ms, ue_status)
            cls._broadcast_to_ws(now_ms, ue_status)
        except Exception as e:
            log.warning("Omniverse push failed (non-blocking): %s", e)

    @classmethod
    async def _tick(cls) -> None:
        """每 tick 執行：推進 UE → compute → 推給 Omniverse。"""
        cls._tick_count += 1
        now_ms = TimestampService.now_ms()

        # 1. 推進各 UE 位置
        for ue_name in cls._ue_states:
            cls._advance_ue(ue_name, SIM_LOOP_TICK_MS)

        # 2. 準備 compute 請求
        ue_positions = []
        for ue_name, state in cls._ue_states.items():
            ue_positions.append({
                "id": ue_name,
                "position": state["current_position"],
                "velocity": [0, 0, 0],  # 簡化：沒有速度向量，只有位置
            })

        # 3. 調用 RAN-sim compute
        try:
            compute_result = SionnaBusinessService.compute_tick(
                timestamp_ms=now_ms,
                scene_id=cls._scene_id,
                ue_positions=ue_positions,
            )
        except Exception as e:
            log.error("Compute failed: %s", e)
            return

        # 保存最新信號數據供前端查詢
        ue_status = compute_result.get("ue_status", [])
        # 4. 推給 Omniverse via WebSocket（包含位置 + 信號數據）
        try:
            await cls._post_to_omniverse_ingest(now_ms, ue_status)

            log.debug(
                "Tick %d: compute_ms=%.1f ue_count=%d",
                cls._tick_count,
                compute_result.get("data", {}).get("compute_ms", 0),
                len(ue_positions),
            )
        except Exception as e:
            log.error("Failed to push to Omniverse: %s", e)

    @classmethod
    def _advance_ue(cls, ue_name: str, delta_ms: int) -> None:
        """推進單個 UE 沿軌跡。"""
        state = cls._ue_states[ue_name]

        if state["speed_mps"] == 0:
            return  # 靜止不動

        # 計算本 tick 移動距離
        delta_distance = (state["speed_mps"] * delta_ms) / 1000.0

        # 累積距離
        state["elapsed_distance"] += delta_distance

        # 計算新位置
        cls._compute_position_at_distance(state)

    @classmethod
    def _compute_position_at_distance(cls, state: dict[str, Any]) -> None:
        """根據走過的距離，計算當前位置（線性插值）。"""
        waypoints = state["waypoints"]
        total_distance = state["total_distance"]
        elapsed = state["elapsed_distance"]

        # 若軌跡長度為 0（所有 waypoint 相同），保持在起點
        if total_distance == 0:
            state["current_position"] = list(waypoints[0])
            state["current_wp_index"] = 0
            state["progress_in_segment"] = 0.0
            return

        # 處理 loop
        if state["loop"]:
            elapsed = elapsed % total_distance
        else:
            elapsed = min(elapsed, total_distance)

        # 找到當前線段
        distance_so_far = 0.0
        for i in range(len(waypoints) - 1):
            p0 = waypoints[i]
            p1 = waypoints[i + 1]
            segment_dist = cls._distance_3d(p0, p1)

            if distance_so_far + segment_dist >= elapsed:
                # 在這個線段內
                progress_in_segment = (elapsed - distance_so_far) / segment_dist if segment_dist > 0 else 0
                state["current_position"] = cls._interpolate(p0, p1, progress_in_segment)
                state["current_wp_index"] = i + 1
                state["progress_in_segment"] = progress_in_segment
                return

            distance_so_far += segment_dist

        # 如果到這裡，表示已到軌跡終點
        state["current_position"] = list(waypoints[-1])
        state["current_wp_index"] = len(waypoints) - 1
        state["progress_in_segment"] = 1.0

    @classmethod
    def _interpolate(cls, p0: list[float], p1: list[float], t: float) -> list[float]:
        """線性插值：p = p0 + t * (p1 - p0)，其中 t ∈ [0, 1]。"""
        return [p0[i] + t * (p1[i] - p0[i]) for i in range(3)]

    @classmethod
    def _distance_3d(cls, p0: list[float], p1: list[float]) -> float:
        """歐幾里得距離。"""
        return math.sqrt(sum((p1[i] - p0[i]) ** 2 for i in range(3)))

    @classmethod
    def _calculate_total_distance(cls, waypoints: list[list[float]]) -> float:
        """計算整個軌跡的總距離。"""
        total = 0.0
        for i in range(len(waypoints) - 1):
            total += cls._distance_3d(waypoints[i], waypoints[i + 1])
        return total

    # ── Omniverse HTTP ──────────────────────────────────────────

    @classmethod
    def _post_to_omniverse_move_sync(cls, ue_name: str, position: list[float]) -> None:
        """POST UE 位置到 Omniverse（同步版）。"""
        url = f"{OMNIVERSE_BACKEND_URL}/api/v0.1/RAN/UE/UEController/move"
        payload = {
            "name": ue_name,
            "x": position[0],
            "y": position[1],
            "z": position[2],
        }

        try:
            requests.post(url, json=payload, timeout=1)
        except Exception:
            pass  # Omniverse 不可用時忽略

    @classmethod
    async def _post_to_omniverse_move(cls, ue_name: str, position: list[float]) -> None:
        """POST UE 位置到 Omniverse."""
        # 注意：Kit 是內部 HTTP :8080，但 Omniverse 後端會處理，所以我們 POST 到 Omniverse
        # 實際上，Omniverse 後端會再轉發給 Kit
        # 這裡簡化：直接 POST 給 Omniverse 的 UEController/move

        url = f"{OMNIVERSE_BACKEND_URL}/api/v0.1/RAN/UE/UEController/move"
        payload = {
            "name": ue_name,
            "x": position[0],
            "y": position[1],
            "z": position[2],
        }

        try:
            # 非同步 POST
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: requests.post(url, json=payload, timeout=2))
        except Exception as e:
            log.warning("Failed to move UE %s: %s", ue_name, e)

    @classmethod
    def _send_to_omniverse_ws_sync(cls, timestamp_ms: int, ue_status: list[dict[str, Any]]) -> None:
        """Send signal 資料透過 WebSocket 到 Omniver-RAN ingest（同步版）。"""
        if not ue_status:
            log.debug("No ue_status to ingest via WS")
            return

        if websockets is None:
            log.warning("websockets package not installed, falling back to HTTP POST")
            cls._post_to_omniverse_ingest_sync(timestamp_ms, ue_status)
            return

        signals = []
        for ue in ue_status:
            ue_id = ue.get("ue_id")
            signal = {
                "ue_name": ue_id,
                "serving_gnb": ue.get("serving_gnb"),
                "serving_pci": ue.get("serving_pci"),
                "serving_cell_id": ue.get("serving_cell_id"),
                "rsrp_dbm": ue.get("rsrp_dbm"),
                "sinr_db": ue.get("sinr_db"),
                "rsrp_map": ue.get("all_rsrp", {}),
            }
            if ue_id in cls._ue_states:
                position = cls._ue_states[ue_id].get("current_position", [0, 0, 0])
                signal["position"] = position
            signals.append(signal)

        payload = {
            "ts": TimestampService.format_iso8601(timestamp_ms),
            "signals": signals,
        }
        if cls._session_uuid:
            payload["session_uuid"] = cls._session_uuid

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(cls._send_via_ws(payload))
            loop.close()
        except Exception as e:
            log.warning("Failed to ingest signals via WS: %s", e)

    @classmethod
    async def _send_via_ws(cls, payload: dict[str, Any]) -> None:
        """每次開新連線發送一個 payload（sync loop 每 tick 建立新 event loop，無法跨 loop 持久連線）。"""
        async with websockets.connect(OMNIVERSE_WS_URL) as ws:
            await ws.send(json.dumps(payload))
            log.debug("Sent via WS: %d signals", len(payload.get("signals", [])))

    @classmethod
    def _post_to_omniverse_ingest_sync(cls, timestamp_ms: int, ue_status: list[dict[str, Any]]) -> None:
        """POST 信號數據到 Omniverse ingest（同步版，向後相容）。"""
        if not ue_status:
            log.debug("No ue_status to ingest")
            return

        url = f"{OMNIVERSE_BACKEND_URL}/api/v0.1/RAN/Ingest/SignalIngestor/create"

        signals = []
        for ue in ue_status:
            ue_id = ue.get("ue_id")
            signal = {
                "ue_name": ue_id,
                "serving_gnb": ue.get("serving_gnb"),
                "serving_pci": ue.get("serving_pci"),
                "serving_cell_id": ue.get("serving_cell_id"),
                "rsrp_dbm": ue.get("rsrp_dbm"),
                "sinr_db": ue.get("sinr_db"),
                "rsrp_map": ue.get("all_rsrp", {}),
            }
            if ue_id in cls._ue_states:
                position = cls._ue_states[ue_id].get("current_position", [0, 0, 0])
                signal["position"] = position
            signals.append(signal)

        payload = {
            "ts": TimestampService.format_iso8601(timestamp_ms),
            "signals": signals,
        }
        if cls._session_uuid:
            payload["session_uuid"] = cls._session_uuid

        try:
            resp = requests.post(url, json=payload, timeout=2)
            log.debug("SignalIngestor response: %s", resp.status_code)
        except Exception as e:
            log.warning("Failed to ingest signals: %s", e)

    @classmethod
    async def _post_to_omniverse_ingest(cls, timestamp_ms: int, ue_status: list[dict[str, Any]]) -> None:
        """Send 信號數據透過 WebSocket 到 Omniver-RAN ingest。"""
        if not ue_status:
            return

        if websockets is None:
            log.warning("websockets package not installed, falling back to HTTP POST")
            await cls._post_to_omniverse_ingest_http(timestamp_ms, ue_status)
            return

        signals = []
        for ue in ue_status:
            ue_id = ue.get("ue_id")
            signal = {
                "ue_name": ue_id,
                "serving_gnb": ue.get("serving_gnb"),
                "serving_pci": ue.get("serving_pci"),
                "serving_cell_id": ue.get("serving_cell_id"),
                "rsrp_dbm": ue.get("rsrp_dbm"),
                "sinr_db": ue.get("sinr_db"),
                "rsrp_map": ue.get("all_rsrp", {}),
            }
            if ue_id in cls._ue_states:
                position = cls._ue_states[ue_id].get("current_position", [0, 0, 0])
                signal["position"] = position
            signals.append(signal)

        payload = {
            "ts": TimestampService.format_iso8601(timestamp_ms),
            "signals": signals,
        }
        if cls._session_uuid:
            payload["session_uuid"] = cls._session_uuid

        try:
            await cls._send_via_ws(payload)
        except Exception as e:
            log.warning("Failed to ingest signals via WS: %s", e)

    @classmethod
    async def _post_to_omniverse_ingest_http(cls, timestamp_ms: int, ue_status: list[dict[str, Any]]) -> None:
        """POST 信號數據到 Omniverse ingest（HTTP fallback）。"""
        if not ue_status:
            return

        url = f"{OMNIVERSE_BACKEND_URL}/api/v0.1/RAN/Ingest/SignalIngestor/create"

        signals = []
        for ue in ue_status:
            ue_id = ue.get("ue_id")
            signal = {
                "ue_name": ue_id,
                "serving_gnb": ue.get("serving_gnb"),
                "serving_pci": ue.get("serving_pci"),
                "serving_cell_id": ue.get("serving_cell_id"),
                "rsrp_dbm": ue.get("rsrp_dbm"),
                "sinr_db": ue.get("sinr_db"),
                "rsrp_map": ue.get("all_rsrp", {}),
            }
            if ue_id in cls._ue_states:
                position = cls._ue_states[ue_id].get("current_position", [0, 0, 0])
                signal["position"] = position
            signals.append(signal)

        payload = {
            "ts": TimestampService.format_iso8601(timestamp_ms),
            "signals": signals,
        }
        if cls._session_uuid:
            payload["session_uuid"] = cls._session_uuid

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: requests.post(url, json=payload, timeout=5))
        except Exception as e:
            log.warning("Failed to ingest signals via HTTP: %s", e)

    @classmethod
    def _broadcast_to_ws(cls, timestamp_ms: int, ue_status: list[dict[str, Any]]) -> None:
        """廣播信號給所有 WebSocket 連接的前端客戶端。"""
        if not ue_status:
            return
        import json
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        payload = {
            "type": "ue_update",
            "tick": cls._tick_count,
            "ues": [
                {
                    "ue_name": ue.get("ue_id"),
                    "position": ue.get("position"),
                    "rsrp_dbm": ue.get("rsrp_dbm"),
                    "sinr_db": ue.get("sinr_db"),
                    "serving_cell": ue.get("serving_cell_id"),
                    "serving_gnb": ue.get("serving_gnb"),
                    "serving_pci": ue.get("serving_pci"),
                    "serving_cell_id": ue.get("serving_cell_id"),
                    "throughput_dl_mbps": ue.get("throughput_dl_mbps"),
                    "mimo_rank": ue.get("mimo_rank"),
                    "mimo_streams_sinr_db": ue.get("mimo_streams_sinr_db"),
                    "mimo_streams_mcs": ue.get("mimo_streams_mcs"),
                }
                for ue in ue_status
            ],
        }
        try:
            async_to_sync(channel_layer.group_send)(
                "sim_live",
                {"type": "sim_update", "text": json.dumps(payload)},
            )
            log.info("WS broadcast sent to sim_live: %d ues", len(ue_status))
        except Exception as e:
            log.warning("WS broadcast failed: %s", e)
