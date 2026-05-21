"""路由綁定 — 鐵則 2-2：直接綁 Actor.function。

URL 格式（鐵則 7-1）：/api/{version}/{System}/{Module}/{Component}/{Element}
本 app 的 version (v0.1) 由 main/urls.py 負責 prefix。

鐵則 7-2：全 POST。

NOTE (restructure/4-system-split):
  - 此 Django project 已轉型成 Physics 專案（即將改名 Physics_sim）
  - 移除的路由：ComputeRunner、SimLoop、Proxy（全部移到 _legacy/，對應 DU/CU 系統）
  - 保留的路由：ConfigManager、CoverageRunner、HealthChecker、SceneGateway 屬於 Physics 範圍
  - 之後會再加：PathSolver/compute (Phase 4 整合層補上)
"""
from django.urls import path

from main.apps.ran_signal.actors.config_actor import ConfigActor
from main.apps.ran_signal.actors.coverage_actor import CoverageActor
from main.apps.ran_signal.actors.health_actor import HealthActor
from main.apps.ran_signal.actors.path_solver_actor import PathSolverActor
from main.apps.ran_signal.actors.precompute_actor import PrecomputeActor
from main.apps.ran_signal.actors.scene_gateway_actor import SceneGatewayActor


urlpatterns = [
    # /api/v0.1/Physics/RanCalc/PathSolver/compute  ← RU 呼叫的 ray tracing 入口
    path(
        "Physics/RanCalc/PathSolver/compute",
        PathSolverActor.compute,
        name="path_solver_compute",
    ),

    # /api/v0.1/Physics/Precompute/{run,status} (Phase B B.6)
    path("Physics/Precompute/run", PrecomputeActor.run, name="precompute_run"),
    path("Physics/Precompute/status", PrecomputeActor.status, name="precompute_status"),

    # /api/v0.1/Physics/RanSignal/ConfigManager/read
    path(
        "Physics/RanSignal/ConfigManager/read",
        ConfigActor.read,
        name="config_manager_read",
    ),
    # /api/v0.1/Physics/RanSignal/ConfigManager/reload
    path(
        "Physics/RanSignal/ConfigManager/reload",
        ConfigActor.reload,
        name="config_manager_reload",
    ),
    # /api/v0.1/Physics/RanSignal/ConfigManager/push_scene
    path(
        "Physics/RanSignal/ConfigManager/push_scene",
        ConfigActor.push_scene,
        name="config_manager_push_scene",
    ),
    # /api/v0.1/Physics/RanSignal/ConfigManager/reset_to_default
    path(
        "Physics/RanSignal/ConfigManager/reset_to_default",
        ConfigActor.reset_to_default,
        name="config_manager_reset_to_default",
    ),

    # /api/v0.1/Physics/RanSignal/CoverageRunner/compute
    path(
        "Physics/RanSignal/CoverageRunner/compute",
        CoverageActor.compute,
        name="coverage_runner_compute",
    ),

    # /api/v0.1/Physics/RanSignal/HealthChecker/read
    path(
        "Physics/RanSignal/HealthChecker/read",
        HealthActor.read,
        name="health_checker_read",
    ),

    # /api/v0.1/Physics/Scene/SceneGateway/init
    path(
        "Physics/Scene/SceneGateway/init",
        SceneGatewayActor.init,
        name="scene_gateway_init",
    ),
]
