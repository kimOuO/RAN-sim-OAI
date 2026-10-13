"""run_topology:由場景樹組拓樸、查詢、序列化往返。"""
import pytest

from ran_sim_protocol import e2_identity as ident
from ran_sim_protocol.run_topology import RunTopology, build_from_tree

RUN = "00000000-0000-0000-0000-0000abcd1234"


def _tree():
    return {"gnbs": [
        {"name": "nbr", "e2_index": 1, "plmn_mcc": "208", "plmn_mnc": "95",
         "dus": [{"name": "du", "du_uuid": "d1", "gnb_du_id": 1, "cells": [{"name": "nbr", "pci": 2, "local_cell_id": 0}]}]},
        {"name": "src", "e2_index": 0,
         "dus": [{"name": "a", "gnb_du_id": 1, "cells": [{"name": "s0", "pci": 1, "local_cell_id": 0}]},
                 {"name": "b", "gnb_du_id": 1, "cells": [{"name": "s1", "pci": 3, "local_cell_id": 1}]}]},
    ]}


def test_build_orders_by_e2_index_and_computes_identity():
    t = build_from_tree(_tree(), run_uuid=RUN, block=3)
    assert [g.name for g in t.gnbs] == ["src", "nbr"]
    src = t.gnb("src")
    assert src.gnb_id == 0xE30 and src.meid == "gnb_208_095_000e30" and src.cell_tag == "e30"
    assert src.cu_host == "cu-abcd1234-0" and t.gnb("nbr").cu_host == "cu-abcd1234-1"
    assert src.e2_port == 8400 + 48
    # DU 全場序號連續;gNB 內 gnb_du_id 重複時改依序
    assert [(d.name, d.index, d.gnb_du_id, d.host) for d in t.dus()] == [
        ("src/a", 0, 1, "du-abcd1234-0"), ("src/b", 1, 2, "du-abcd1234-1"), ("nbr/du", 2, 1, "du-abcd1234-2")]
    c = t.cell("e30:s1")
    assert c.nci == ident.nci(0xE30, 1) and c.ncgi == "208095-" + format(c.nci, "09x")
    assert t.du_of_cell("e30:s1").host == "du-abcd1234-1"
    assert t.gnb_of_cell("e31:nbr").name == "nbr"
    assert t.gnb_of_nci(t.cell("e31:nbr").nci).name == "nbr"
    assert t.cell_by_nci(c.nci).cell_id == "e30:s1"
    assert t.ru_url == "http://ru-abcd1234:8000" and t.amf_url == "http://amf-abcd1234:8000"


def test_roundtrip_json():
    t = build_from_tree(_tree(), run_uuid=RUN, block=3)
    t2 = RunTopology.from_json(t.to_json())
    assert t2.to_dict() == t.to_dict()
    assert t2.cell("e30:s0").du == "src/a"


def test_duplicate_local_cell_id_rejected():
    tree = _tree()
    tree["gnbs"][1]["dus"][1]["cells"][0]["local_cell_id"] = 0
    with pytest.raises(ValueError):
        build_from_tree(tree, run_uuid=RUN, block=3)


def test_missing_local_cell_id_filled_in_order():
    tree = _tree()
    for du in tree["gnbs"][1]["dus"]:
        for c in du["cells"]:
            c.pop("local_cell_id")
    t = build_from_tree(tree, run_uuid=RUN, block=3)
    assert [c.local_cell_id for c in t.gnb("src").dus[0].cells + t.gnb("src").dus[1].cells] == [0, 1]


def test_from_env(monkeypatch):
    t = build_from_tree(_tree(), run_uuid=RUN, block=2)
    monkeypatch.setenv("RUN_TOPOLOGY", t.to_json())
    monkeypatch.setenv("GNB_NAME", "nbr")
    monkeypatch.setenv("DU_NAME", "src/b")
    e = RunTopology.from_env()
    assert e.self_gnb().gnb_id == 0xE21 and e.self_du().gnb_du_id == 2
    monkeypatch.delenv("RUN_TOPOLOGY")
    assert RunTopology.from_env() is None
