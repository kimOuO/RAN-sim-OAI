"""DU bootstrap 對 mock CU 的整合測試 — accepted / rejected / unreachable 三條路徑。"""
from __future__ import annotations

import pytest

from main.apps.f1ap_du.models.f1_session import F1Session
from main.apps.f1ap_du.services.optional.lifecycle import du_bootstrap as boot
from main.utils.env_loader import get_int


def _set_response(recorder, accepted: bool, tid: int = 1, wrapped: bool = True) -> None:
    if wrapped:
        body = (
            f'{{"status":"success","message":"OK",'
            f'"data":{{"accepted":{"true" if accepted else "false"},"transaction_id":{tid}}}}}'
        )
    else:
        body = f'{{"accepted":{"true" if accepted else "false"},"transaction_id":{tid}}}'
    recorder.response_body = body.encode()


@pytest.mark.django_db
def test_accepted_response_drives_state_to_active(mock_cu):
    _set_response(mock_cu, accepted=True, tid=123)

    outcome = boot.attempt_setup(timeout=2.0)

    assert outcome == "ACTIVE"
    s = boot.get_state()
    assert s.state == "ACTIVE"
    assert s.transaction_id == 123
    assert s.attempts == 1
    assert boot.is_setup_done() is True

    # F1Session row 應寫入,state=ACTIVE,last_setup_at 不為 null
    rows = list(F1Session.objects.all())
    assert len(rows) == 1
    row = rows[0]
    assert row.state == "ACTIVE"
    assert row.transaction_id == 123
    assert row.gnb_du_id == get_int("SIM_GNB_DU_ID", 1)
    assert row.last_setup_at is not None


@pytest.mark.django_db
def test_rejected_response_drives_state_to_failed_no_retry(mock_cu):
    _set_response(mock_cu, accepted=False, tid=42)

    outcome = boot.attempt_setup(timeout=2.0)

    assert outcome == "FAILED"
    s = boot.get_state()
    assert s.state == "FAILED"
    assert s.transaction_id == 42
    assert boot.is_setup_done() is False  # 沒 active

    # _bootstrap_loop 在 FAILED 時也應停止 — 跑一次 loop 應只會新增 0 個 attempt
    # (attempt_setup 已增 1,_bootstrap_loop 內部也呼叫一次後 return,共 2 attempts)
    boot._bootstrap_loop(max_retries=5, interval_s=0.01)
    s2 = boot.get_state()
    assert s2.attempts == 2  # 第一次手動 + loop 內第一次,然後 FAILED 即停
    assert s2.state == "FAILED"

    rows = list(F1Session.objects.all())
    assert any(r.state == "FAILED" for r in rows)


@pytest.mark.django_db
def test_unreachable_cu_keeps_state_setup_sent_and_retries(monkeypatch):
    """指向不存在的 port → resp 為 None → state SETUP_SENT,_bootstrap_loop 應 retry 滿 max_retries。"""
    monkeypatch.setenv("HTTP_CU_HOST", "127.0.0.1")
    monkeypatch.setenv("HTTP_CU_PORT", "1")  # nothing listens

    boot._bootstrap_loop(max_retries=3, interval_s=0.01)

    s = boot.get_state()
    assert s.state == "SETUP_SENT"
    assert s.attempts == 3
    assert boot.is_setup_done() is False


@pytest.mark.django_db
def test_bare_response_format_also_works(mock_cu):
    """CU 若直接 serialize F1SetupResponse dataclass 不包 wrapper,也要能解析。"""
    _set_response(mock_cu, accepted=True, tid=77, wrapped=False)
    outcome = boot.attempt_setup(timeout=2.0)
    assert outcome == "ACTIVE"
    assert boot.get_state().transaction_id == 77


@pytest.mark.django_db
def test_post_du_setup_url_path_is_correct(mock_cu):
    _set_response(mock_cu, accepted=True, tid=1)
    boot.attempt_setup(timeout=2.0)
    assert mock_cu.calls[0]["path"] == "/api/v0.1/CU/F1AP/F1ApRouter/du_setup"
    body = mock_cu.calls[0]["payload"]
    assert "gnb_du_id" in body
    assert "served_cells" in body


@pytest.mark.django_db
def test_f1_session_read_endpoint_reflects_bootstrap_outcome(mock_cu):
    """整合:跑完 attempt_setup 後從 read endpoint 撈出 ACTIVE row + bootstrap_state。"""
    import json
    from django.test import Client

    _set_response(mock_cu, accepted=True, tid=555)
    outcome = boot.attempt_setup(timeout=2.0)
    assert outcome == "ACTIVE"

    resp = Client().post(
        "/api/v0.1/DU/F1AP/F1SessionController/read",
        data=json.dumps({}),
        content_type="application/json",
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["data"]["bootstrap_state"]["state"] == "ACTIVE"
    assert body["data"]["bootstrap_state"]["transaction_id"] == 555
    assert body["data"]["bootstrap_state"]["is_setup_done"] is True
    sessions = body["data"]["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["state"] == "ACTIVE"
    assert sessions[0]["transaction_id"] == 555
