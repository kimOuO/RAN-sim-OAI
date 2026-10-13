"""多 gNB(2026-09-27):DU 路由、Initial UL RRC、同 gNB 跨 DU 換手、Xn(Setup / 換手 / 允入)、
過期量測報告、跨 gNB ANR。對外呼叫(DU、鄰居 CU)一律 mock,只驗本 CU 的決策與落地。

拓樸:gNB A(本 CU,e2_index 0)有 DU a1(cell a0)與 DU a2(cell a1);gNB B(e2_index 1)有 cell b0。區塊 3。
"""
from __future__ import annotations

import base64
import json
from unittest.mock import patch

import pytest
from django.test import Client
from ran_sim_protocol.run_topology import build_from_tree

TREE = {"gnbs": [
    {"name": "A", "e2_index": 0, "dus": [
        {"name": "a1", "gnb_du_id": 1, "cells": [{"name": "a0", "pci": 1, "local_cell_id": 0}]},
        {"name": "a2", "gnb_du_id": 2, "cells": [{"name": "a1", "pci": 2, "local_cell_id": 1}]}]},
    {"name": "B", "e2_index": 1, "dus": [
        {"name": "b1", "gnb_du_id": 1, "cells": [{"name": "b0", "pci": 3, "local_cell_id": 0}]}]},
]}
TOPO = build_from_tree(TREE, run_uuid="00000000-0000-0000-0000-00000000t0p0", block=3)
A0, A1, B0 = "e30:a0", "e30:a1", "e31:b0"
DU_OK = {"status": "success", "data": {}}


@pytest.fixture
def gnb_a(monkeypatch, db):
    monkeypatch.setenv("RUN_TOPOLOGY", TOPO.to_json())
    monkeypatch.setenv("GNB_NAME", "A")
    monkeypatch.setenv("GNB_ID_HEX", "0x000e30")
    c = Client()
    for du, cell, nci, pci in ((1, A0, TOPO.cell(A0).nci, 1), (2, A1, TOPO.cell(A1).nci, 2)):
        r = c.post("/api/v0.1/CU/F1AP/F1ApRouter/du_setup", json.dumps({
            "gnb_du_id": du, "du_endpoint": f"http://du-{du}:8000", "du_name": f"A/a{du}",
            "served_cells": [{"cell_id": cell, "pci": pci, "frequency_ghz": 3.5, "bandwidth_mhz": 40.0,
                              "gnb_id": "A", "nr_cellid": nci}]}), content_type="application/json")
        assert r.status_code == 200, r.content
    return c


def _rrc(t: str) -> str:
    return base64.b64encode(json.dumps({"type": t, "payload": {}}).encode()).decode()


def _attach(c, ue="u1", cell=A0, du=1):
    with patch("main.apps.cu_cp.services.business.du_client_operations.DuClientBusinessService._post", return_value=DU_OK):
        for t, init in (("RRCSetupRequest", True), ("RRCSetupComplete", False)):
            r = c.post("/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message", json.dumps(
                {"ue_id": ue, "rrc_msg_b64": _rrc(t), "is_initial": init, "cell_id": cell, "gnb_du_id": du}),
                content_type="application/json")
            assert r.status_code == 200, r.content


def test_du_routing_by_cell_and_ue(gnb_a):
    from main.apps.cu_cp.services.business.du_client_operations import _resolve
    _attach(gnb_a, cell=A1, du=2)
    assert _resolve({"cell_id": A0}) == "http://du-1:8000"
    assert _resolve({"ue_id": "u1"}) == "http://du-2:8000"          # UE 在 a1(DU 2)
    assert _resolve({"target_cell": A1, "ue_id": "u1"}) == "http://du-2:8000"


def test_initial_ul_rrc_sets_cell_du_and_per_gnb_ran_id(gnb_a):
    from main.apps.cu_cp.actors.f1ap_router_actor import _resolve_ue_base
    from main.apps.cu_cp.models.ue_context import UeContext
    _attach(gnb_a, cell=A1, du=2)
    ue = UeContext.objects.get(ue_id="u1")
    assert (ue.serving_cell, ue.gnb_du_id, ue.rrc_state) == (A1, 2, "CONNECTED")
    assert ue.ran_ue_ngap_id != _resolve_ue_base("u1")              # 每個 gNB 自己配
    assert ue.amf_ue_ngap_id == _resolve_ue_base("u1") + 1          # AMF 規則不變


def test_initial_ul_rrc_rejects_foreign_cell(gnb_a):
    r = gnb_a.post("/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message", json.dumps(
        {"ue_id": "u9", "rrc_msg_b64": _rrc("RRCSetupRequest"), "is_initial": True, "cell_id": B0, "gnb_du_id": 1}),
        content_type="application/json")
    assert r.status_code == 404


def test_inter_du_handover_moves_context(gnb_a):
    from main.apps.cu_cp.models.handover_event import HandoverEvent
    from main.apps.cu_cp.models.ue_context import UeContext
    from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
    _attach(gnb_a, cell=A0, du=1)
    calls = []
    with patch("main.apps.cu_cp.services.business.du_client_operations.DuClientBusinessService._post",
               side_effect=lambda path, payload, **kw: calls.append((path.rsplit("/", 1)[-1], kw.get("gnb_du_id"))) or DU_OK):
        ho = execute_f1_handover(ue_id="u1", target_cell=A1, trigger="A3_TTT")
    assert ho and not ho.get("failed")
    assert ("ue_context_setup", 2) in calls and ("ue_context_release", 1) in calls
    assert UeContext.objects.get(ue_id="u1").gnb_du_id == 2
    ev = HandoverEvent.objects.get(ho_uuid=ho["ho_uuid"])
    assert ev.ho_type == "inter-DU" and ev.status == "SUCC" and ev.target_ncgi == TOPO.cell(A1).ncgi


def _peer_b():
    from main.apps.cu_cp.services.business import xn
    xn.store_peer(0xE31, "B", "http://cu-b:8000", [{"cell_id": B0, "nci": TOPO.cell(B0).nci, "pci": 3,
                                                    "arfcn": 633333, "frequency_ghz": 3.5, "bandwidth_mhz": 40.0}])


def test_xn_setup_populates_neighbour_tables(gnb_a):
    from main.apps.cu_cp.actors.anr_control_actor import resolve_cell_ref
    from main.apps.cu_cp.models.cgi_resolution import CgiResolution
    from main.apps.cu_cp.services.business import xn
    from main.apps.cu_cp.services.common.cell_id_map import to_platform_cell_id
    _peer_b()
    assert xn.foreign_cell(B0).gnb_id == 0xE31 and xn.xn_available(0xE31)
    assert CgiResolution.objects.filter(pci=3, arfcn=633333, cgi=B0).exists()     # ReportCGI 解得出鄰 gNB 的 PCI
    assert to_platform_cell_id(TOPO.cell(B0).nci) == B0                           # RC 3-1 目標 NCI
    assert resolve_cell_ref(TOPO.cell(B0).ncgi) == B0                             # ANR 帶 ncgi 字串
    assert xn.std_ids(B0) == {"nci": TOPO.cell(B0).nci, "ncgiStd": TOPO.cell(B0).ncgi}


def _relation(xn_ok: bool):
    from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
    from main.apps.cu_cp.services.common.timestamp_service import TimestampService
    now = TimestampService.now()
    NrCellRelation.objects.create(source_cell_id=A0, target_cgi=B0, target_pci=3, target_arfcn=633333,
                                  xn_x2_established=xn_ok, created_at=now, updated_at=now)


def test_xn_handover_success(gnb_a):
    from main.apps.cu_cp.models.handover_event import HandoverEvent
    from main.apps.cu_cp.models.ue_context import UeContext
    from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
    _attach(gnb_a)
    _peer_b(); _relation(True)
    sent = []
    with patch("main.apps.cu_cp.services.business.xn._post", side_effect=lambda url, path, body, timeout=None: sent.append(path) or {"ran_ue_ngap_id": 7}), \
         patch("main.apps.cu_cp.services.business.du_client_operations.DuClientBusinessService._post", return_value=DU_OK):
        ho = execute_f1_handover(ue_id="u1", target_cell=B0, trigger="A3_TTT")
    assert ho["ho_type"] == "Xn" and not ho.get("failed")
    assert sent == ["handover_request", "sn_status_transfer"]
    assert UeContext.objects.get(ue_id="u1").rrc_state == "RELEASE"
    ev = HandoverEvent.objects.get(ho_uuid=ho["ho_uuid"])
    assert ev.status == "SUCC" and ev.amf_ue_ngap_id and ev.source_ncgi == TOPO.cell(A0).ncgi


def test_xn_not_established_fails_like_before(gnb_a):
    from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
    _attach(gnb_a)
    _peer_b(); _relation(False)
    with patch("main.apps.cu_cp.services.business.xn._post") as post:
        ho = execute_f1_handover(ue_id="u1", target_cell=B0, trigger="A3_TTT")
    assert ho["failed"] and ho["failure_cause"] == "TXnRELOCprepExpiry"
    post.assert_not_called()


def test_xn_handover_request_admits_ue(gnb_a):
    from main.apps.cu_cp.models.ue_context import UeContext
    with patch("main.apps.cu_cp.services.business.du_client_operations.DuClientBusinessService._post", return_value=DU_OK) as du:
        r = gnb_a.post("/api/v0.1/CU/Xn/XnRouter/handover_request", json.dumps({
            "ue_id": "x1", "amf_ue_ngap_id": 555, "source_gnb_id": 0xE31, "source_cell": B0, "target_cell": A1,
            "ue_context": {"traffic_profile": {"pattern": "cbr", "bearer_id": 1}}, "ho_uuid": "h1"}),
            content_type="application/json")
    assert r.status_code == 200, r.content
    ue = UeContext.objects.get(ue_id="x1")
    assert (ue.rrc_state, ue.serving_cell, ue.gnb_du_id, ue.amf_ue_ngap_id) == ("CONNECTED", A1, 2, 555)
    assert du.call_args.kwargs.get("gnb_du_id") == 2


def test_xn_handover_request_rejects_inactive_cell(gnb_a):
    from main.apps.cu_cp.models.cell_config import CellConfig
    CellConfig.objects.filter(cell_id=A1).update(is_active=False)
    r = gnb_a.post("/api/v0.1/CU/Xn/XnRouter/handover_request", json.dumps({
        "ue_id": "x2", "target_cell": A1, "source_cell": B0}), content_type="application/json")
    assert r.status_code == 409


def test_stale_measurement_report_is_ignored(gnb_a):
    from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
    from main.apps.cu_cp.models.ue_context import UeContext
    _attach(gnb_a)
    UeContext.objects.filter(ue_id="u1").update(rrc_state="RELEASE", serving_cell=B0)
    r = gnb_a.post("/api/v0.1/CU/F1AP/F1ApRouter/measurement_report", json.dumps({
        "ue_id": "u1", "rsrp_dbm": -80, "sinr_db": 10, "throughput_dl_mbps": 1.0,
        "neighbor_cells": [{"cell_id": A0, "rsrp_dbm": -70, "rsrq_db": -10}]}), content_type="application/json")
    assert r.status_code == 200 and r.json()["data"]["processed"] is False
    assert not NrCellRelation.objects.filter(source_cell_id=B0).exists()


def test_anr_add_cross_gnb_target_by_ncgi(gnb_a):
    from main.apps.cu_cp.actors.anr_control_actor import apply_son_trigger
    from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
    _peer_b()
    with patch("main.apps.cu_cp.actors.anr_control_actor._schedule_xn_setup"):
        out = apply_son_trigger({"requestType": "ADD", "sourceCellId": A0, "target": {"cgi": TOPO.cell(B0).ncgi}})
    assert out["result"] == "ADDED" and out["targetCgi"] == B0
    rel = NrCellRelation.objects.get(source_cell_id=A0, target_cgi=B0)
    assert (rel.target_pci, rel.target_arfcn) == (3, 633333)


def test_handover_group_matches_cross_gnb_neighbour(gnb_a):
    """RC 3-1 群組換手:鄰區是別的 gNB 的 cell(只在 Xn 外部鄰區表)也要匹配得到 UE,並走 Xn 換過去。"""
    from main.apps.cu_cp.actors.e2_control_actor import _handle_handover_group
    from main.apps.cu_cp.models.measurement_log import MeasurementLog
    from main.apps.cu_cp.services.common.timestamp_service import TimestampService
    _attach(gnb_a)
    _peer_b(); _relation(True)
    MeasurementLog.objects.create(meas_uuid="m1", ue_id="u1", recorded_at=TimestampService.now(),
                                  neighbor_cells_json=[{"cell_id": B0, "rsrp_dbm": -90}])
    msg = {"ue_group_id": 1, "serving_cell_ncgi": A0, "target_pci": 3,
           "target_cgi_msg": {"nr_cell_id": TOPO.cell(B0).nci}}
    with patch("main.apps.cu_cp.services.business.xn._post", return_value={"ran_ue_ngap_id": 7}), \
         patch("main.apps.cu_cp.services.business.du_client_operations.DuClientBusinessService._post", return_value=DU_OK):
        out = json.loads(_handle_handover_group(msg, {}).content)["data"]["control_outcome"]
        assert (out["matchedUeCount"], out["executedCount"], out["result"]) == (1, 1, "EXECUTED")
        # ARFCN 條件也要用鄰 gNB 的頻率比對:帶錯的頻率 → 匹配 0
        _attach(gnb_a, ue="u2")
        MeasurementLog.objects.create(meas_uuid="m2", ue_id="u2", recorded_at=TimestampService.now(),
                                      neighbor_cells_json=[{"cell_id": B0, "rsrp_dbm": -90}])
        out = json.loads(_handle_handover_group({**msg, "target_arfcn": 600000}, {}).content)["data"]["control_outcome"]
        assert out["matchedUeCount"] == 0


def test_rc_handover_to_foreign_cell_reports_its_nci(gnb_a):
    from main.apps.cu_cp.actors.e2_control_actor import _handle_handover
    _attach(gnb_a)
    _peer_b(); _relation(True)
    with patch("main.apps.cu_cp.services.business.xn._post", return_value={"ran_ue_ngap_id": 7}), \
         patch("main.apps.cu_cp.services.business.du_client_operations.DuClientBusinessService._post", return_value=DU_OK):
        r = _handle_handover("u1", {"target_cgi": {"nr_cell_id": TOPO.cell(B0).nci}}, {})
    d = json.loads(r.content)["data"]
    assert d["target_cell"] == B0 and d["target_nr_cell_id"] == TOPO.cell(B0).nci


def test_energy_saving_offload_falls_back_to_xn_neighbour(gnb_a):
    """本 gNB 沒有其他可用 cell 時,節能趕人改趕到 Xn 鄰 gNB 的 cell;本地有可用 cell 時行為不變。"""
    from main.apps.cu_cp.actors import e2_control_actor as e2c
    _peer_b(); _relation(True)
    assert e2c._pick_offload_target(A0) == A1
    with patch.dict(e2c._CELL_ES_STATE, {A1: "isEnergySaving"}):
        assert e2c._pick_offload_target(A0) == B0
        from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
        NrCellRelation.objects.filter(source_cell_id=A0, target_cgi=B0).update(xn_blocklist=True)
        assert e2c._pick_offload_target(A0) is None


def test_cell_level_rc_rejects_foreign_cell(gnb_a):
    """2-6 / 2-8 的 ranP[4] NCI 指到鄰 gNB 的 cell:解得出來但不屬於本 E2 node → 409,不送 DU。"""
    from main.apps.cu_cp.actors.e2_control_actor import _handle_slice_prb_quota
    _peer_b()
    with patch("main.apps.cu_cp.services.business.du_client_operations.DuClientBusinessService._post", return_value=DU_OK) as du:
        r = _handle_slice_prb_quota({}, {"target_cgi": {"nr_cell_id": TOPO.cell(B0).nci}, "max_prb": 50}, {})
        assert r.status_code == 409
        r = gnb_a.post("/api/v0.1/CU/E2/Control/request", json.dumps({
            "control_header": {"control_style": 2, "control_action_id": 8},
            "control_message": {"target_cgi": {"nr_cell_id": TOPO.cell(B0).nci}, "max_layers": 2}}),
            content_type="application/json")
        assert r.status_code == 409, r.content
        du.assert_not_called()
        r = _handle_slice_prb_quota({}, {"target_cgi": {"nr_cell_id": TOPO.cell(A0).nci}, "max_prb": 50}, {})
        assert r.status_code == 200


def test_full_kpm_cell_id_is_cell_name_with_std_ids(gnb_a):
    """ran_func 5 的 cell_id 維持 cell 名稱(與 ran_func 6 一致),NCI 另放 nci / ncgiStd(RIC run 5 回報)。"""
    from main.apps.cu_cp.models.cell_config import CellConfig
    from main.apps.cu_cp.services.optional.e2.full_kpm_reporter import _cell_hex_id, _std_ids
    cfg = CellConfig.objects.get(cell_id=A0)
    cfg.served_plmn = "20895"
    assert _cell_hex_id(cfg) == A0
    assert _std_ids(cfg) == {"nci": TOPO.cell(A0).nci, "ncgiStd": TOPO.cell(A0).ncgi}
    cfg.nr_cellid = None                       # 舊場景沒有明確 NCI:不附(輸出與改版前相同)
    assert _cell_hex_id(cfg) == A0 and _std_ids(cfg) == {}


def test_report_cgi_resolves_local_and_foreign_by_name(gnb_a):
    """ReportCGI:本 gNB 與 Xn 鄰 gNB 的 PCI 都解得出來,回 cell 名稱(不是 15 位 hex),NCI 另附。"""
    from main.apps.cu_cp.services.business.anr_kpm import cgi_resolve
    _peer_b()
    loc = cgi_resolve(1)
    assert loc["results"] == {A0: 3} and loc["nrCellIdentity"] == TOPO.cell(A0).nci
    far = cgi_resolve(3, 633333)
    assert far["unique"] and far["results"] == {B0: 3} and far["nrCellIdentity"] == TOPO.cell(B0).nci
    assert cgi_resolve(3, 600000)["results"] == {"FAIL": 3}


def test_to_be_energy_saving_blocks_admission_and_retries(gnb_a):
    """toBeEnergySaving 期間 cell 不收新 UE(換手 / 鄰 gNB 轉入);清不空時交給背景重試,不是停在原地。"""
    from main.apps.cu_cp.actors import e2_control_actor as e2c
    from main.apps.cu_cp.services.business.ue_admission import AdmissionRejected, check_target_cell
    from main.apps.cu_cp.services.common.fixture_state import admission_blocked
    _attach(gnb_a)                                   # u1 在 A0
    with patch.dict(e2c._CELL_ES_STATE, {A1: "toBeEnergySaving"}):
        assert admission_blocked(A1, False) and not admission_blocked(A0, False)
        try:
            check_target_cell(A1)
            raise AssertionError("toBeEnergySaving 的 cell 不該允入")
        except AdmissionRejected as e:
            assert e.cause == "CellNotAvailable"
    # A0 進節能:u1 換手失敗(DU 不回成功)→ 留在 A0 → 啟動背景重試
    with patch.dict(e2c._CELL_ES_STATE, {}), \
         patch.object(e2c, "_es_start_retry") as retry, \
         patch("main.apps.cu_cp.services.business.du_client_operations.DuClientBusinessService._post",
               return_value={"success": False}):
        out = e2c._cell_energy_saving(A0, "disable", {})
        assert out["energySavingState"] == "toBeEnergySaving" and out["remaining"] == 1
        retry.assert_called_once()
        out = e2c._cell_energy_saving(A0, "enable", {})
        assert e2c.get_cell_es_state(A0) == "isNotEnergySaving"


def test_setup_request_after_release_reattaches(gnb_a):
    """舊 context 停在 RELEASE(剛經 Xn 換走)時 UE 重新接入:要能重建連線,不是 500。"""
    from main.apps.cu_cp.models.ue_context import UeContext
    _attach(gnb_a)
    UeContext.objects.filter(ue_id="u1").update(rrc_state="RELEASE", serving_cell="")
    _attach(gnb_a)
    assert UeContext.objects.get(ue_id="u1").rrc_state == "CONNECTED"


def test_initial_access_rejected_while_cell_enters_energy_saving(gnb_a):
    """toBeEnergySaving 的 cell 拒收 UE 的第一次接入(409 = RRC Reject),也不建 UE context。"""
    from main.apps.cu_cp.actors import e2_control_actor as e2c
    from main.apps.cu_cp.models.ue_context import UeContext
    with patch.dict(e2c._CELL_ES_STATE, {A0: "toBeEnergySaving"}), \
         patch("main.apps.cu_cp.services.business.du_client_operations.DuClientBusinessService._post", return_value=DU_OK):
        r = gnb_a.post("/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message", json.dumps(
            {"ue_id": "z1", "rrc_msg_b64": _rrc("RRCSetupRequest"), "is_initial": True, "cell_id": A0, "gnb_du_id": 1}),
            content_type="application/json")
        assert r.status_code == 409
        assert not UeContext.objects.filter(ue_id="z1").exists()
        _attach(gnb_a, ue="z1", cell=A1, du=2)          # 另一顆 cell 照常接入
    assert UeContext.objects.get(ue_id="z1").serving_cell == A1


def test_rc_handover_failure_returns_409_with_outcome(gnb_a):
    """RC 3-1 換手沒成 → 409 + control_outcome{result: HANDOVER_FAILED, failureCause}(adapter 轉 RICcontrolFailure)。"""
    from main.apps.cu_cp.actors.e2_control_actor import _handle_handover
    _attach(gnb_a)
    _peer_b(); _relation(False)                      # Xn 關係未建立 → TXnRELOCprepExpiry
    r = _handle_handover("u1", {"target_cgi": {"nr_cell_id": TOPO.cell(B0).nci}}, {})
    assert r.status_code == 409
    co = json.loads(r.content)["errors"]["control_outcome"]
    assert co["result"] == "HANDOVER_FAILED" and co["failureCause"] == "TXnRELOCprepExpiry"


def test_full_kpm_reads_dump_pm_from_every_du(gnb_a):
    """I2(2026-10-10):一個 CU 兩個 DU 時,第二個 DU 的 cell 也要拿到自己 DU 的 du_* 計數(以前只讀第一個 DU → 0)。"""
    from unittest.mock import MagicMock
    from main.apps.cu_cp.services.optional.e2.full_kpm_reporter import FullKpmReporter
    dumps = {
        "http://du-1:8000": {"tick_count": 100, "prb_per_cell": 106, "gnbs": {A0: {"prb_used_dl": 11}}},
        "http://du-2:8000": {"tick_count": 200, "prb_per_cell": 106, "gnbs": {A1: {"prb_used_dl": 22}}},
    }

    def fake_post(url, **_):
        r = MagicMock()
        r.json.return_value = {"data": dumps[url.split("/api/")[0]]}
        return r
    with patch("main.apps.cu_cp.services.optional.e2.full_kpm_reporter.requests.post", side_effect=fake_post):
        out = FullKpmReporter.collect()
    recs = {r["cell_id"]: r for g in out["pm"].values() for r in g}
    assert recs[A0]["du_RRU.PrbTotDl"] == "11"
    assert recs[A1]["du_RRU.PrbTotDl"] == "22"


def test_full_kpm_conn_mean_is_per_report_period(gnb_a):
    """2026-10-13:RRC.ConnMean / ConnMax 是本 report 週期的值,不跨週期累計(TS 28.552)。"""
    from unittest.mock import MagicMock
    from main.apps.cu_cp.services.optional.e2.full_kpm_reporter import FullKpmReporter
    from main.apps.cu_cp.models.cell_cum_counter import CellCumCounter
    # 模擬先前累計留下的高水位與平均樣本:新算法不應再受它影響
    from django.utils import timezone
    CellCumCounter.objects.update_or_create(cell_id=A0, defaults={"conn_max": 9, "conn_sum": 90, "conn_n": 10, "updated_at": timezone.now()})
    r = MagicMock(); r.json.return_value = {"data": {}}
    with patch("main.apps.cu_cp.services.optional.e2.full_kpm_reporter.requests.post", return_value=r):
        out = FullKpmReporter.collect()
    rec = {x["cell_id"]: x for g in out["pm"].values() for x in g}[A0]
    assert rec["cu_RRC.ConnMax"] == "0" and rec["cu_RRC.ConnMean"] == "0"


def test_rc_handover_to_own_cell_returns_409_already_at_target(gnb_a):
    """C8(2026-10-13):目標就是 UE 目前的 cell → 409 + failureCause=UeAlreadyAtTarget(以前 400、無 IE 32)。"""
    from main.apps.cu_cp.actors.e2_control_actor import _handle_handover
    _attach(gnb_a)
    r = _handle_handover("u1", {"target_cell": A0}, {})
    assert r.status_code == 409
    co = json.loads(r.content)["errors"]["control_outcome"]
    assert co["result"] == "HANDOVER_FAILED" and co["failureCause"] == "UeAlreadyAtTarget"
    assert co["sourceCell"] == A0 and co["targetCell"] == A0


def test_rc_handover_to_unknown_cell_returns_409_target_not_found(gnb_a):
    """C11(2026-10-13):目標 cell 不在本 CU、也不是 Xn 鄰居 → 409 + failureCause=TargetCellNotFound。"""
    from main.apps.cu_cp.actors.e2_control_actor import _handle_handover
    _attach(gnb_a)
    r = _handle_handover("u1", {"target_cell": "e99:phantom"}, {})
    assert r.status_code == 409
    co = json.loads(r.content)["errors"]["control_outcome"]
    assert co["failureCause"] == "TargetCellNotFound"


def test_handover_failure_carries_ho_type(gnb_a, monkeypatch):
    """C16(2026-10-13):換手失敗的 IE 32 也要帶 hoType(以前為 null)。a0(DU1)→ a1(DU2)強制失敗 → inter-DU。"""
    from main.apps.cu_cp.actors.e2_control_actor import _handle_handover
    _attach(gnb_a)
    monkeypatch.setenv("HO_FORCE_FAIL_TARGET", A1)
    with patch("main.apps.cu_cp.services.business.du_client_operations.DuClientBusinessService._post", return_value=DU_OK):
        r = _handle_handover("u1", {"target_cell": A1}, {})
    assert r.status_code == 409
    co = json.loads(r.content)["errors"]["control_outcome"]
    assert co["failureCause"] == "RandomAccessProblem" and co["hoType"] == "inter-DU"
