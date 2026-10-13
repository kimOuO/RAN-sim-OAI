"""E2 身分規則的回歸測試(multi_gnb_plan.md D2、D3)。常數與 RIC 端實際看到的值對齊。"""
import pytest

from ran_sim_protocol import e2_identity as e


def test_plmn_and_gnb_bits_match_ric_observed_values():
    assert e.plmn_bcd_hex("208", "95") == "02F859"                       # RIC 閘道 register 的 plmn
    assert e.gnb_id_bits(0x000E04) == "0000000000111000000100"            # 2026-09-24 閘道回傳的 nbIdBits


def test_block_slot_gnb_meid_tag():
    ident = e.node_identity(3, 1, "nbr")
    assert ident["slot"] == 0x31
    assert ident["gnb_id_hex"] == "0x000e31"
    assert ident["meid"] == "gnb_208_095_000e31"
    assert ident["cell_tag"] == "e31"


@pytest.mark.parametrize("block,idx", [(0, 0), (16, 0), (1, 16), (1, -1)])
def test_out_of_range_rejected(block, idx):
    with pytest.raises(ValueError):
        e.slot_for(block, idx)


def test_block_range_never_leaves_e_prefix():
    for b in range(e.BLOCK_MIN, e.BLOCK_MAX + 1):
        for i in range(e.BLOCK_SIZE):
            assert e.cell_tag(e.gnb_id_for(b, i)).startswith("e")


def test_nci_embeds_gnb_and_roundtrips():
    gid = e.gnb_id_for(3, 1)
    v = e.nci(gid, 5)
    assert e.gnb_id_of_nci(v) == gid
    assert e.local_cell_of_nci(v) == 5
    assert v == (0x000E31 << 14) | 5


def test_ncgi_fixed_format():
    v = e.nci(0x000E31, 0)
    s = e.ncgi(v)
    assert s == "208095-" + f"{v:09x}"
    assert len(s.split("-")[1]) == 9 and s.split("-")[1] == s.split("-")[1].lower()
    assert e.parse_ncgi(s) == ("208095", v)
    assert e.parse_ncgi("bad") is None


def test_local_cell_range():
    with pytest.raises(ValueError):
        e.nci(0x000E31, 1 << 14)
