"""把 E2 識別的已知值釘死(多 gNB 改版,計畫 D2 / D3,RIC 已確認)。

外部 Agent 依 I-1 / I-2 宣告的 meid + NCI 部署 xApp;宣告值與執行期一旦不同,xApp 就打不中 cell,
而且要跑起來才看得出來 —— 所以用常數鎖住。規則的唯一來源是 ran_sim_protocol.run_topology。
"""
from main.apps.agent_api.services.optional.e2_identity import cells_by_name, field_e2_identities

TREE = {"gnbs": [
    {"name": "src", "e2_index": 0, "dus": [{"name": "d", "cells": [{"name": "src", "pci": 0, "local_cell_id": 0}]}]},
    {"name": "nbr", "e2_index": 1, "dus": [{"name": "d", "cells": [{"name": "nbr", "pci": 1, "local_cell_id": 0}]}]},
    {"name": "mid", "e2_index": 2, "dus": [{"name": "d", "cells": [{"name": "mid", "pci": 2, "local_cell_id": 0}]}]},
]}


def test_block3_identities():
    ids = field_e2_identities(TREE, 3)
    assert [n["node_id"] for n in ids] == ["src", "nbr", "mid"]
    nbr = ids[1]
    assert nbr["gnb_id"] == "0x000e31" and nbr["meid"] == "gnb_208_095_000e31"
    assert nbr["cell_tag"] == "e31" and nbr["plmn"]["bcd"] == "02F859"
    assert nbr["gnb_id_bits"] == "0000000000111000110001"
    c = nbr["cells"][0]
    assert c["cell_id"] == "e31:nbr" and c["ran_name"] == "gnb_208_095_000e31"
    assert c["nr_cell_identity"] == 0xE31 << 14 and c["ncgi"] == "208095-0038c4000"   # 0xE31 << 14


def test_cells_by_name():
    by = cells_by_name(field_e2_identities(TREE, 1))
    assert by["mid"]["cell_id"] == "e12:mid" and by["mid"]["node_id"] == "mid"


def test_block_out_of_range():
    # 不用 pytest.raises —— orchestrator 映像沒裝 pytest,這些測試也可以直接呼叫執行
    for bad in (0, 16):
        try:
            field_e2_identities(TREE, bad)
        except ValueError:
            continue
        raise AssertionError(f"block={bad} 應該要被擋下")
