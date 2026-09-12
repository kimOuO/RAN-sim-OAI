"""整合測試共用 fixture — 在 process 內起 mock CU / RU HTTP server。

mock server 用 stdlib `ThreadingHTTPServer`,沒額外依賴。
每個 test 拿到的 `mock_cu` / `mock_ru` 是 CallRecorder,可以斷言:
  - `recorder.calls` 是收到的所有 POST(每筆含 path 跟 payload dict)
  - `recorder.set_response(status, body)` 改下次回應
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest


@dataclass
class CallRecorder:
    calls: list[dict[str, Any]] = field(default_factory=list)
    response_status: int = 200
    response_body: bytes = b'{"status":"success","data":{"transaction_id":1,"accepted":true}}'

    def reset(self) -> None:
        self.calls.clear()

    def calls_to(self, path: str) -> list[dict[str, Any]]:
        return [c for c in self.calls if c["path"] == path]


def _make_handler(recorder: CallRecorder):
    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 (stdlib name)
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {"_raw": body}
            recorder.calls.append({"path": self.path, "payload": payload})
            self.send_response(recorder.response_status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(recorder.response_body)))
            self.end_headers()
            self.wfile.write(recorder.response_body)

        def log_message(self, *args, **kwargs):  # 靜默 stderr
            return None

    return _Handler


def _start_mock(monkeypatch, host_env: str, port_env: str) -> CallRecorder:
    recorder = CallRecorder()
    handler = _make_handler(recorder)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(host_env, "127.0.0.1")
    monkeypatch.setenv(port_env, str(port))
    # 把 server / thread 掛到 recorder,讓 fixture finalizer 收
    recorder._server = server  # type: ignore[attr-defined]
    recorder._thread = thread  # type: ignore[attr-defined]
    return recorder


def _stop_mock(recorder: CallRecorder) -> None:
    server = getattr(recorder, "_server", None)
    if server:
        server.shutdown()
        server.server_close()


@pytest.fixture
def mock_cu(monkeypatch):
    rec = _start_mock(monkeypatch, "HTTP_CU_HOST", "HTTP_CU_PORT")
    yield rec
    _stop_mock(rec)


@pytest.fixture
def mock_ru(monkeypatch):
    rec = _start_mock(monkeypatch, "HTTP_RU_HOST", "HTTP_RU_PORT")
    yield rec
    _stop_mock(rec)


@pytest.fixture(autouse=True)
def reset_du_singletons():
    """每個 integration test 之間清掉 module-level state — tick / RLC / HARQ / MCS / RA / PM。"""
    from main.apps.f1ap_du.services.optional.lifecycle import du_bootstrap as boot_mod
    from main.apps.f1ap_du.services.optional.lifecycle import du_config_update as cfg_mod
    from main.apps.mac.services.optional.harq import harq_manager as harq_mod
    from main.apps.mac.services.optional.link_adaptation import mcs_controller as mcs_mod
    from main.apps.mac.services.optional.pm_aggregator import pm_aggregator as pm_mod
    from main.apps.mac.services.optional.random_access import ra_manager as ra_mod
    from main.apps.mac.services.optional.scheduler import scheduler_factory as sched_mod
    from main.apps.rlc.services.optional.entities import factory as rlc_factory
    from main.apps.tick.services.optional.runner import tick_runner as tick_mod

    def _clear() -> None:
        tick_mod._singleton = None
        rlc_factory._registry.clear()
        harq_mod._singleton = None
        mcs_mod._singleton = None
        ra_mod._singleton = None
        pm_mod._singleton = None
        sched_mod._singleton = None
        boot_mod.reset_state()
        cfg_mod.reset_tx_counter()

    _clear()
    yield
    _clear()
