"""Physics HTTP client — POST /api/v0.1/Physics/RanCalc/PathSolver/compute。

Body 用 ran_sim_protocol.physics.PathSolverRequest 做 serialize；
回傳 PathSolverResponse dataclass。
"""
from __future__ import annotations

import requests
from django.conf import settings
from ran_sim_protocol.physics import PathSolverRequest, PathSolverResponse
from ran_sim_protocol.serde import from_dict, to_dict

from main.utils.logger import get_logger


logger = get_logger(__name__)


class PhysicsHttpError(RuntimeError):
    pass


def _base_url() -> str:
    return f"http://{settings.HTTP_PHYSICS_HOST}:{settings.HTTP_PHYSICS_PORT}"


def _default_timeout() -> float:
    """live 模式第一批請求會撞到 Sionna engine 重建(warmup ~30 s、天線變更再 ~30 s);5 s 必逾時。
    2026-09-15:逾時被當成 SINR −100 → DU 1 s 內宣告 RLF → UE 掉到 IDLE 再也回不來。預設放寬到 60 s,env RU_PHYSICS_TIMEOUT_SEC 可調。"""
    import os
    try:
        return float(os.environ.get("RU_PHYSICS_TIMEOUT_SEC", "60") or 60)
    except ValueError:
        return 60.0


def compute_paths(req: PathSolverRequest, *, timeout: float | None = None) -> PathSolverResponse:
    timeout = _default_timeout() if timeout is None else timeout
    url = f"{_base_url()}/api/v0.1/Physics/RanCalc/PathSolver/compute"
    body = to_dict(req)
    try:
        resp = requests.post(url, json=body, timeout=timeout)
    except requests.RequestException as exc:
        raise PhysicsHttpError(f"physics request failed: {exc}") from exc

    if resp.status_code >= 400:
        raise PhysicsHttpError(f"physics returned {resp.status_code}: {resp.text[:200]}")

    payload = resp.json()
    # Physics 端用 utils/response.py 的 success wrapper：{success, message, data}
    data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
    return from_dict(PathSolverResponse, data)


def health() -> dict:
    """GET 風格的 health；對端是 POST /HealthChecker/read（rule §7-2 全 POST）。"""
    url = f"{_base_url()}/api/v0.1/Physics/RanSignal/HealthChecker/read"
    try:
        resp = requests.post(url, json={}, timeout=2.0)
        return {"status_code": resp.status_code, "body": resp.json() if resp.ok else resp.text[:200]}
    except requests.RequestException as exc:
        return {"status_code": -1, "error": str(exc)}
