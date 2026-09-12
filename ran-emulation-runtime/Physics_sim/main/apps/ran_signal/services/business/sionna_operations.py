"""SionnaBusinessService — Physics 業務操作層，包裝 Sionna compute pipeline。

NOTE (restructure/4-system-split):
  - 此 service 已精簡為 Physics-only：
    * 留：sionna_engine, coverage_solver, mitsuba_builder, scene_loader
    * 移除：bbu_telemetry / e2_formatter / mcs_controller / pf_scheduler /
            pm_aggregator / rrc_event_tracker（這些屬於 DU/CU，已搬到 _legacy/）
  - compute_tick / e2 KPI 聚合 / pm 計算 → 全交給未來的 DU 系統做。
  - 此 service 只提供：場景載入、Sionna 物理計算、Coverage map。

鐵則 5-3 要求 business service 提供通用方法吃 model_class；但本服務為 compute-only
無 Model，以「物理場景」為操作對象。方法仍保持 stateless + 參數化。

**Override 機制**：Layer 1 = scene_config.json 預設；Layer 2 = 外部平台 push 覆蓋。
push_scene / reset_to_default 控制 layer 切換。
"""
import copy
import threading
from pathlib import Path
from typing import Any

from main.apps.ran_signal.services.optional.ran_calculation import (
    coverage_solver,
    mitsuba_builder,
    scene_loader,
    sionna_engine,
)
from main.apps.ran_signal.services.common.timestamp_service import TimestampService
from main.utils.env_loader import get_str
from main.utils.logger import get_logger


logger = get_logger(__name__)


# Runtime-push 進來的 Mitsuba XML 落地路徑
RUNTIME_SCENE_XML_PATH = "/tmp/ranp_runtime_scene.xml"


def _release_engine(old: Any) -> None:
    """換場景後釋放舊 engine —— 不做的話 DrJit 的 GPU/host 緩衝不會還。

    2026-08-25:連跑十二題切換十二次場景,physics 漲到 31.8 GiB 被 global
    OOM killer 殺掉(dmesg: Killed process daphne anon-rss 33306552 kB),
    UE 全部失去通道 → RLF → 掉話。在鎖外做,避免 flush 阻塞 compute_paths。
    """
    if old is None:
        return
    try:
        old.close()
    except Exception:  # noqa: BLE001 — 釋放失敗不該讓換場景失敗
        logger.exception("release old SionnaEngine failed")


class SionnaBusinessService:
    """Stateful singleton service. Caches loaded scene + engine + counters across requests."""

    _loaded_config: dict[str, Any] | None = None
    _engine: Any = None
    _scene_id: str | None = None
    _loaded_at_ms: int | None = None
    # 序列化進入 Sionna scene mutation（compute_paths / compute_coverage / engine rebuild）
    # 防多 thread 同時改 scene.receivers 造成 drjit reshape mismatch。
    _engine_lock: threading.Lock = threading.Lock()
    # NOTE (restructure/4-system-split): 移除 _pm_aggregator / _rrc_tracker /
    # _pf_scheduler / _mcs_controller — 這些 trackers 屬於 DU 系統的 tick orchestrator。
    _last_tick_ms: int | None = None

    # Override state
    _source: str = "default"                 # "default" or "runtime_push"
    _previous_scene_id: str | None = None
    _ttl_expires_at_ms: int | None = None
    _current_mitsuba_path: str | None = None
    _current_geometry_source_type: str | None = None

    # ── query ────────────────────────────────────────────────────

    @classmethod
    def is_scene_loaded(cls, scene_id: str) -> bool:
        return cls._scene_id == scene_id

    @classmethod
    def get_loaded_config(cls) -> dict[str, Any] | None:
        if cls._loaded_config is None:
            return None
        return {
            "scene_id": cls._scene_id or "",
            "loaded_at_ms": cls._loaded_at_ms or 0,
            "gnb_count": len(cls._loaded_config.get("gnbs", [])),
            "ue_count": len(cls._loaded_config.get("ues", [])),
            "gnbs": cls._loaded_config.get("gnbs", []),
            "ues": cls._loaded_config.get("ues", []),
            "source": cls._source,
            "ttl_expires_at_ms": cls._ttl_expires_at_ms,
            "previous_scene_id": cls._previous_scene_id,
        }

    @classmethod
    def health_status(cls) -> dict[str, Any]:
        engine = cls._engine
        return {
            "ready": engine is not None,
            "scene_id": cls._scene_id,
            "loaded_at_ms": cls._loaded_at_ms,
            "source": cls._source,
            "gpu": sionna_engine.probe_gpu(),
        }

    # ── mutate: 預設載入 ─────────────────────────────────────────

    @classmethod
    def reload_scene_config(cls) -> dict[str, Any]:
        """Layer 1 — 從 scene_config.json 載入預設。"""
        scene_config_path = get_str("SCENE_CONFIG_PATH", "/mnt/srcin/scene_config.json")
        mitsuba_scene_path = get_str("MITSUBA_SCENE_PATH", "/app/scenes/umi_3sector.xml")
        scene_id = get_str("SCENE_ID", "umi_3sector_v1")

        cfg = scene_loader.load(scene_config_path)
        logger.info(
            "scene_config loaded (default): gnbs=%d ues=%d buildings=%d",
            len(cfg.get("gnbs", [])),
            len(cfg.get("ues", [])),
            len(cfg.get("buildings", [])),
        )

        antenna_cfg = cfg.get("scene_antenna_config", {})
        # 建 engine 過程含 Sionna scene load + warmup（~4s），在 lock 外做避免阻塞 compute_paths
        engine = sionna_engine.SionnaEngine(
            mitsuba_scene_path=mitsuba_scene_path,
            gnbs=cfg["gnbs"],
            gnb_antenna_pattern=antenna_cfg.get("gnb_antenna_pattern", "tr38901"),
            gnb_polarization=antenna_cfg.get("gnb_polarization", "V"),
            ue_antenna_pattern=antenna_cfg.get("ue_antenna_pattern", "dipole"),
            ue_polarization=antenna_cfg.get("ue_polarization", "V"),
            gnb_array_rows=antenna_cfg.get("gnb_array_rows", 1),
            gnb_array_cols=antenna_cfg.get("gnb_array_cols", 1),
            ue_array_rows=antenna_cfg.get("ue_array_rows", 1),
            ue_array_cols=antenna_cfg.get("ue_array_cols", 1),
        )

        # 短暫鎖 swap engine（毫秒級）
        with cls._engine_lock:
            _old = cls._engine
            cls._loaded_config = cfg
            cls._engine = engine
            cls._scene_id = scene_id
            cls._loaded_at_ms = TimestampService.now_ms()
            cls._source = "default"
            cls._previous_scene_id = None
            cls._ttl_expires_at_ms = None
            cls._current_mitsuba_path = mitsuba_scene_path
            cls._current_geometry_source_type = None
            cls._last_tick_ms = None
        _release_engine(_old)
        return cls.get_loaded_config()  # type: ignore[return-value]

    # ── mutate: 外部 push override ───────────────────────────────

    @classmethod
    def apply_override(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """Layer 2 — 套用外部平台 push 的 override（部分或全部覆蓋）。

        payload 需通過 PushSceneRequestSerializer 驗證。
        """
        rebuild_start_ms = TimestampService.now_ms()

        new_scene_id = payload["scene_id"]
        override_mode = payload.get("override_mode", "full")
        geometry_source = payload.get("geometry_source")
        new_gnbs = payload.get("gnbs")
        new_ues = payload.get("ues")
        ttl_seconds = payload.get("ttl_seconds")

        prev_scene_id = cls._scene_id

        # 確保有預設 loaded（拿來 merge）
        if cls._loaded_config is None:
            cls.reload_scene_config()

        # ── Step 1: 處理 geometry_source（若有）──────────────────
        mitsuba_path = cls._current_mitsuba_path or get_str(
            "MITSUBA_SCENE_PATH", "/app/scenes/umi_3sector.xml"
        )
        geometry_type_out: str | None = None

        if override_mode in ("full", "geometry_only") and geometry_source:
            geometry_type_out = geometry_source["type"]
            mitsuba_path = cls._materialize_geometry(geometry_source)
            logger.info("runtime geometry source=%s → %s", geometry_type_out, mitsuba_path)

        # ── Step 2: merge gnbs / ues ────────────────────────────
        merged_cfg = copy.deepcopy(cls._loaded_config or {})
        if override_mode in ("full", "ran_only") and new_gnbs:
            merged_cfg["gnbs"] = [dict(g) for g in new_gnbs]
        if new_ues:
            merged_cfg["ues"] = [dict(u) for u in new_ues]

        # Auto-assign pci/cell_id for any gnbs missing them（優先從 cells[0]["pci"]）
        import hashlib
        for idx, gnb in enumerate(merged_cfg.get("gnbs", [])):
            cells = gnb.get("cells") or []
            if "pci" not in gnb:
                if cells:
                    gnb["pci"] = int(cells[0]["pci"])
                else:
                    h = int(hashlib.sha256(gnb["name"].encode()).hexdigest(), 16)
                    gnb["pci"] = h % 1008
            if "cell_id" not in gnb:
                gnb["cell_id"] = f"cell_{gnb['pci']}"

        # ── Step 3: 重建 Sionna engine ───────────────────────────
        gnb_list = merged_cfg.get("gnbs", [])
        logger.info(
            "rebuilding Sionna engine for push: scene_id=%s mode=%s gnbs=%d",
            new_scene_id, override_mode, len(gnb_list),
        )
        if not gnb_list:
            logger.warning(
                "No gNBs provided; SionnaEngine will use default frequency 3.5 GHz. "
                "Consider creating gNBs in Omniver-RAN first via BuildingController/write or API."
            )
        antenna_cfg = payload.get("scene_antenna_config", {})
        # 建 engine 在 lock 外（耗時 ~4s 不阻塞 compute_paths）
        engine = sionna_engine.SionnaEngine(
            mitsuba_scene_path=mitsuba_path,
            gnbs=gnb_list,
            gnb_antenna_pattern=antenna_cfg.get("gnb_antenna_pattern", "tr38901"),
            gnb_polarization=antenna_cfg.get("gnb_polarization", "V"),
            ue_antenna_pattern=antenna_cfg.get("ue_antenna_pattern", "dipole"),
            ue_polarization=antenna_cfg.get("ue_polarization", "V"),
            gnb_array_rows=antenna_cfg.get("gnb_array_rows", 1),
            gnb_array_cols=antenna_cfg.get("gnb_array_cols", 1),
            ue_array_rows=antenna_cfg.get("ue_array_rows", 1),
            ue_array_cols=antenna_cfg.get("ue_array_cols", 1),
        )

        # ── Step 4: 提交 state（短暫鎖 swap engine） ─────────────
        with cls._engine_lock:
            _old = cls._engine
            cls._loaded_config = merged_cfg
            cls._engine = engine
            cls._scene_id = new_scene_id
            cls._loaded_at_ms = TimestampService.now_ms()
            cls._source = "runtime_push"
            cls._previous_scene_id = prev_scene_id
            cls._current_mitsuba_path = mitsuba_path
            cls._current_geometry_source_type = geometry_type_out

            if ttl_seconds is not None and ttl_seconds > 0:
                cls._ttl_expires_at_ms = cls._loaded_at_ms + int(ttl_seconds * 1000)
            else:
                cls._ttl_expires_at_ms = None

            cls._last_tick_ms = None

        sionna_rebuild_ms = TimestampService.now_ms() - rebuild_start_ms

        _release_engine(_old)
        cls._persist_override(payload)          # OOM/重建自癒的料源
        cls._override_restore_attempted = True  # 本進程已有現行 override,不再回載舊檔
        try:                                    # TF 不還 OS,每次 rebuild RSS 棘輪 — 監測供 OOM 歸因
            rss_mb = int(open("/proc/self/status").read().split("VmRSS:")[1].split()[0]) // 1024
            logger.info("engine rebuilt: RSS=%dMB(mem_limit 前的棘輪水位)", rss_mb)
            if rss_mb > 10240:
                logger.warning("RSS %dMB 逼近 mem_limit —— OOM 前兆,建議擇機重啟 physics(場景會自動回載)", rss_mb)
        except Exception:
            pass
        return {
            "scene_id": cls._scene_id,
            "previous_scene_id": prev_scene_id,
            "loaded_at_ms": cls._loaded_at_ms,
            "override_mode": override_mode,
            "source": cls._source,
            "ttl_expires_at_ms": cls._ttl_expires_at_ms,
            "sionna_rebuild_ms": sionna_rebuild_ms,
            "gnb_count": len(merged_cfg.get("gnbs", [])),
            "ue_count": len(merged_cfg.get("ues", [])),
            "geometry_source_type": geometry_type_out,
        }

    # ── 2026-08-26 OOM 自癒:override 落地與回載 ──────────────────
    # Layer 2 場景只存在記憶體,容器 OOM/重建後回到預設場景,整套模擬讀到
    # 錯誤通道直到人工重啟場景(Q5 當天實炸)。修:apply_override 成功即把
    # payload 落地 /app/tmp/last_override.json;首次 compute 的 lazy init
    # 自動回載;reset_to_default 視為明確放棄 override,刪檔。
    _OVERRIDE_STATE_PATH = "/app/tmp/last_override.json"
    _override_restore_attempted = False

    @classmethod
    def _persist_override(cls, payload: dict[str, Any]) -> None:
        try:
            import json as _json
            import os as _os
            _os.makedirs(_os.path.dirname(cls._OVERRIDE_STATE_PATH), exist_ok=True)
            with open(cls._OVERRIDE_STATE_PATH, "w") as f:
                _json.dump(payload, f)
        except Exception as exc:
            logger.warning("persist override failed(不擋套用): %s", exc)

    @classmethod
    def _drop_persisted_override(cls) -> None:
        try:
            import os as _os
            _os.remove(cls._OVERRIDE_STATE_PATH)
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.warning("drop persisted override failed: %s", exc)

    @classmethod
    def ensure_loaded(cls) -> None:
        """lazy init:預設場景 + (若有)回載重啟前的 Layer 2 override。"""
        if cls._engine is None:
            cls.reload_scene_config()
        if not cls._override_restore_attempted:
            cls._override_restore_attempted = True
            try:
                import json as _json
                with open(cls._OVERRIDE_STATE_PATH) as f:
                    payload = _json.load(f)
            except FileNotFoundError:
                return
            except Exception as exc:
                logger.warning("read persisted override failed: %s", exc)
                return
            try:
                logger.info("重啟自癒:回載 Layer 2 override scene_id=%s", payload.get("scene_id"))
                cls.apply_override(payload)
            except Exception:
                logger.exception("回載 override 失敗 —— 維持預設場景(需人工重推)")

    @classmethod
    def reset_to_default(cls) -> dict[str, Any]:
        """退回 Layer 1（scene_config.json 預設）。"""
        logger.info("reset_to_default (was scene_id=%s source=%s)", cls._scene_id, cls._source)
        cls._drop_persisted_override()          # 明確重置=放棄 override,重啟不再回載
        return cls.reload_scene_config()

    # ── 內部：geometry 落地 ──────────────────────────────────────

    @classmethod
    def _materialize_geometry(cls, geometry_source: dict[str, Any]) -> str:
        """把 geometry_source 轉成容器內可讀的 Mitsuba XML 路徑。

        兩種來源：
          - buildings_json  ：收到建築 box 列表後，後端自己用 mitsuba_builder 轉 XML 落地。
          - mitsuba_xml_path：已產好的 Mitsuba XML（例：OSM 地圖的真實 mesh），直接使用。
        """
        src_type = geometry_source["type"]
        if src_type == "mitsuba_xml_path":
            path = (geometry_source.get("path") or "").strip()
            if not path:
                raise RuntimeError("mitsuba_xml_path 需要 path")
            if not Path(path).is_file():
                raise RuntimeError(f"Mitsuba XML 不存在（容器內路徑）：{path}")
            logger.info("runtime scene from existing Mitsuba XML → %s", path)
            return path
        if src_type == "buildings_json":
            buildings = geometry_source["buildings"]
            ground = geometry_source.get("ground")
            mitsuba_builder.build_and_write(
                buildings=buildings,
                out_path=RUNTIME_SCENE_XML_PATH,
                ground=ground,
            )
            logger.info(
                "runtime scene built from %d buildings → %s",
                len(buildings), RUNTIME_SCENE_XML_PATH,
            )
            return RUNTIME_SCENE_XML_PATH
        raise RuntimeError(f"Unsupported geometry_source type: {src_type}")

    # ── coverage map ─────────────────────────────────────────────

    @classmethod
    def compute_coverage(
        cls,
        *,
        grid: dict[str, Any],
        include_sinr: bool = True,
        max_depth: int = 3,
        null_threshold_dbm: float = -120.0,
        diffraction: bool = False,
        diffuse_reflection: bool = False,
    ) -> dict[str, Any]:
        """產 per-gNB 2D RSRP 網格（對齊外部平台 spec）。"""
        cls.ensure_loaded()

        assert cls._engine is not None
        assert cls._loaded_config is not None

        # Debug: print scene geometry
        buildings = cls._loaded_config.get("buildings", [])
        logger.info(f"[Coverage] Buildings in scene: {len(buildings)}")
        for b in buildings:
            logger.info(f"  Building '{b.get('name')}': pos={b.get('position')} size={b.get('size')}")

        # 序列化 Sionna scene mutation：compute_paths / compute_coverage / rebuild 互鎖
        with cls._engine_lock:
            result = coverage_solver.compute_coverage_map(
                scene=cls._engine._scene,
                gnbs=cls._loaded_config["gnbs"],
                cell_entries=cls._engine._cell_entries,
                x_range=tuple(grid["x_range"]),
                z_range=tuple(grid["z_range"]),
                x_step=float(grid["x_step"]),
                z_step=float(grid["z_step"]),
                sample_height_m=float(grid.get("sample_height_m", 1.5)),
                max_depth=max_depth,
                null_threshold_dbm=null_threshold_dbm,
                include_sinr=include_sinr,
                diffraction=diffraction,
                diffuse_reflection=diffuse_reflection,
            )
        return result

    # ── compute (Physics-only) ───────────────────────────────────────
    # NOTE (restructure/4-system-split):
    #   原 compute_tick() 含 e2_formatter / pf_scheduler / mcs_controller /
    #   pm_aggregator / rrc_tracker / bbu_telemetry — 那些屬於 DU/CU。
    #   原始備份保留在 _legacy/mixed/sionna_operations.py（git history）。
    #   Physics 只提供 raw Sionna ray tracing 結果，不做 KPI 聚合。

    @classmethod
    def compute_paths(
        cls,
        *,
        ue_positions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """純 Sionna ray tracing；回傳 channel matrix + path gain。
        DU 拿這個結果自己跑 e2_formatter / scheduler / KPI。"""
        cls.ensure_loaded()
        assert cls._engine is not None
        # 序列化 Sionna scene mutation。多 thread 同時改 scene.receivers 會 race 噴 drjit reshape error。
        with cls._engine_lock:
            return cls._engine.compute_paths(ue_positions=ue_positions)
