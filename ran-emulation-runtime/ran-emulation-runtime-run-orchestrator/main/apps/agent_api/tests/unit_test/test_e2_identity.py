"""把 NCI 的已知值釘死。

這條規則同時存在於 e2adapter(_hash_nr_cell_id)、CU(compute_nr_cell_id)與本 app。
三者一旦漂移,xApp 依 I-2 宣告的 NCI 下 control 就會打不中 cell,而且只會在跑起來
以後才看得出來 —— 所以用常數鎖住。0xb2a9cd944 取自 e2adapter 自己的測試常數
(test_rc_beam_control.NCI_E01_NBR)。
"""
from main.apps.agent_api.services.optional.e2_identity import field_e2_identity, nr_cell_identity


def test_nci_matches_e2adapter_constant():
    assert nr_cell_identity("e01:nbr") == 0xB2A9CD944


def test_field_identity_slot1():
    d = field_e2_identity(1, ["src", "nbr", "mid"])
    assert d["gnb_id"] == "0x000e01"
    assert d["e2_node_id"] == "gnb_208_095_000e01"
    assert d["cell_tag"] == "e01"
    by = {c["name"]: c for c in d["cells"]}
    assert by["src"]["cell_id"] == "e01:src"
    assert by["nbr"]["nr_cell_identity_hex"] == "0xb2a9cd944"
    assert by["mid"]["ncgi"] == "208095-2824f98f7"


def test_slot_out_of_range():
    # 不用 pytest.raises —— orchestrator 映像沒裝 pytest,這些測試也可以直接呼叫執行
    for bad in (0, 512):
        try:
            field_e2_identity(bad, ["src"])
        except ValueError:
            continue
        raise AssertionError(f"slot={bad} 應該要被擋下")
