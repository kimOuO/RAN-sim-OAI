"""全場鎖步時鐘:平行驅動多個 DU、合併 DL TTI 一次算、量測依 UE 分回原 DU、下一拍帶回。"""
from unittest.mock import patch

from ran_sim_protocol.fapi import CqiIndication

from main.apps.phy_low.services.optional.lockstep_clock import LockstepClock, merge_dl_tti

A, B = "http://du-a:8000", "http://du-b:8000"


def _tti(ue, cell, dl_load):
    return {"sfn": 3, "slot": 4, "scene_sim_ms": 0, "cell_dl_load": {cell: dl_load}, "cell_ul_load": {cell: 0.1},
            "pdus": [{"ue_id": ue, "prb_start": 0, "prb_count": 5, "mcs": 9, "payload_size_bytes": 100,
                      "harq_pid": 0, "layers": 1, "pmi": 0, "cell_id": cell}]}


def test_merge_concatenates_pdus_and_unions_loads():
    m = merge_dl_tti([_tti("u1", "c1", 0.4), None, _tti("u2", "c2", 0.9)], scene_sim_ms=700)
    assert [p["ue_id"] for p in m["pdus"]] == ["u1", "u2"]
    assert m["cell_dl_load"] == {"c1": 0.4, "c2": 0.9} and m["scene_sim_ms"] == 700
    assert merge_dl_tti([None, {}], 0) is None


def test_step_drives_all_dus_and_routes_measurements_back():
    clk = LockstepClock(du_urls=[A, B])
    clk.reset(sim_dt_ms=100, speed_x=2.0)
    sent = []

    def fake_post(url, body):
        sent.append((url, body))
        return {"dl_tti": _tti("u1", "c1", 0.4) if url == A else _tti("u2", "c2", 0.9)}

    ran = []

    def fake_run(req):
        ran.append(req)
        return [CqiIndication(ue_id=p.ue_id, sinr_db=10.0, cqi=9) for p in req.pdus]

    with patch.object(clk, "_post_step", side_effect=fake_post), \
         patch("main.apps.fapi_south.services.optional.dl_tti_pipeline.run", side_effect=fake_run):
        out = clk.step_once()
        assert out == {"tick": 1, "dus_ok": 2, "pdus": 2, "cqi": 2}
        assert len(ran) == 1 and len(ran[0].pdus) == 2           # 全場一次算
        assert ran[0].cell_dl_load == {"c1": 0.4, "c2": 0.9}
        clk.align_scene()
        clk.step_once()

    tick2 = {u: b for u, b in sent[2:]}
    # 第二拍:全場負載帶給每個 DU;量測只回給 UE 所屬的 DU
    assert tick2[A]["cell_dl_load"] == {"c1": 0.4, "c2": 0.9}
    assert [i["ue_id"] for i in tick2[A]["indications"]] == ["u1"]
    assert [i["ue_id"] for i in tick2[B]["indications"]] == ["u2"]
    assert tick2[A]["tick"] == 2 and tick2[A]["scene_tick"] == 1 and tick2[A]["speed_x"] == 2.0


def test_failed_du_does_not_block_others():
    clk = LockstepClock(du_urls=[A, B])

    def fake_post(url, body):
        if url == B:
            raise TimeoutError("slow")
        return {"dl_tti": _tti("u1", "c1", 0.2)}

    with patch.object(clk, "_post_step", side_effect=fake_post), \
         patch("main.apps.fapi_south.services.optional.dl_tti_pipeline.run",
               side_effect=lambda req: [CqiIndication(ue_id="u1", sinr_db=1.0, cqi=3)]):
        out = clk.step_once()
    assert out["dus_ok"] == 1 and clk.step_errors == 1 and "du-b" in clk.last_error
    assert list(clk.pending) == [A]
