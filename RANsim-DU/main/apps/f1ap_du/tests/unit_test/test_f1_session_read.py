"""F1SessionController.read endpoint — DB 空 / 有 row / 指定 gnb_du_id / 找不到。"""
import json

import pytest
from django.test import Client

from main.apps.f1ap_du.models.f1_session import F1Session
from main.apps.f1ap_du.services.optional.lifecycle import du_bootstrap as boot


@pytest.fixture(autouse=True)
def _reset_boot():
    boot.reset_state()
    yield
    boot.reset_state()


def _post_read(client: Client, body: dict | None = None) -> dict:
    resp = client.post(
        "/api/v0.1/DU/F1AP/F1SessionController/read",
        data=json.dumps(body or {}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    return resp.json()


@pytest.mark.django_db
def test_read_empty_db_returns_init_bootstrap_state():
    body = _post_read(Client())
    assert body["data"]["sessions"] == []
    bs = body["data"]["bootstrap_state"]
    assert bs["state"] == "INIT"
    assert bs["attempts"] == 0
    assert bs["is_setup_done"] is False


@pytest.mark.django_db
def test_read_lists_all_sessions():
    F1Session.objects.create(
        f1_uuid="f1_session-aaa",
        gnb_du_id=1, cu_host="cu", cu_port=8000,
        transaction_id=10, state="ACTIVE",
        last_setup_at=1000, f1_session_updated_at=1000,
    )
    F1Session.objects.create(
        f1_uuid="f1_session-bbb",
        gnb_du_id=2, cu_host="cu2", cu_port=8001,
        transaction_id=20, state="FAILED",
        last_setup_at=None, f1_session_updated_at=2000,
    )
    body = _post_read(Client())
    sessions = body["data"]["sessions"]
    assert len(sessions) == 2
    states = {s["state"] for s in sessions}
    assert states == {"ACTIVE", "FAILED"}


@pytest.mark.django_db
def test_read_by_gnb_du_id_returns_single_session():
    F1Session.objects.create(
        f1_uuid="f1_session-aaa",
        gnb_du_id=42, cu_host="cu", cu_port=8000,
        transaction_id=99, state="ACTIVE",
        last_setup_at=12345, f1_session_updated_at=12345,
    )
    body = _post_read(Client(), {"gnb_du_id": 42})
    s = body["data"]["session"]
    assert s["gnb_du_id"] == 42
    assert s["transaction_id"] == 99
    assert s["state"] == "ACTIVE"


@pytest.mark.django_db
def test_read_by_unknown_gnb_du_id_returns_404():
    resp = Client().post(
        "/api/v0.1/DU/F1AP/F1SessionController/read",
        data=json.dumps({"gnb_du_id": 999}),
        content_type="application/json",
    )
    assert resp.status_code == 404
