"""DU cell → cached npz tx 名對應(2026-10-14:tx 名是 <gNB>#<PCI>,第二個 gNB 起 PCI ≠ 序號)。"""
from unittest.mock import patch

import pytest

from main.apps.fapi_north.services.optional import channel_cache_du as ccd


class _Cache:
    cell_names = ["g0#0", "g0#1", "g0#2", "g1#3", "g1#4", "g1#5"]


@pytest.fixture(autouse=True)
def _reset_pci_cache():
    ccd._PCI_MAP_CACHE.update(ts=0.0, map={})
    yield
    ccd._PCI_MAP_CACHE.update(ts=0.0, map={})


@pytest.mark.django_db
def test_second_gnb_maps_by_pci_not_local_index():
    from main.apps.mac.models.cell_state import CellState
    for i, pci in enumerate((3, 4, 5)):
        CellState.objects.create(cell_uuid=f"cell-t{i}", cell_id=f"e51:g1_c{i}", pci=pci, total_prb=106, cell_created_at=0, cell_updated_at=0)
    with patch.object(ccd, "get_du_cache", return_value=_Cache()):
        assert [ccd.cell_id_to_tx(f"e51:g1_c{i}") for i in range(3)] == ["g1#3", "g1#4", "g1#5"]


@pytest.mark.django_db
def test_first_gnb_and_unknown_pci_keep_old_rule():
    with patch.object(ccd, "get_du_cache", return_value=_Cache()):
        assert ccd.cell_id_to_tx("e50:g0_c1") == "g0#1"     # 查不到 PCI → 退回序號規則
        assert ccd.cell_id_to_tx("g0#2") == "g0#2"


class _MduCache:
    cell_names = ["mid#2", "nbr#1", "src#0", "src#3"]   # S3:gNB 'src' 有 src(PCI 0)與 spare(PCI 3)兩個 DU


@pytest.mark.django_db
def test_cell_named_differently_from_gnb_maps_by_pci():
    """2026-10-14:spare 是 gNB 'src' 第二個 DU 的 cell,tx 名 'src#3'。以前回 'spare' → SINR −30 dB → 2 秒 RLF。"""
    from main.apps.mac.models.cell_state import CellState
    CellState.objects.create(cell_uuid="cell-s0", cell_id="e50:spare", pci=3, total_prb=106, cell_created_at=0, cell_updated_at=0)
    CellState.objects.create(cell_uuid="cell-s1", cell_id="e50:src", pci=0, total_prb=106, cell_created_at=0, cell_updated_at=0)
    with patch.object(ccd, "get_du_cache", return_value=_MduCache()):
        assert ccd.cell_id_to_tx("e50:spare") == "src#3"
        assert ccd.cell_id_to_tx("e50:src") == "src#0"


@pytest.mark.django_db
def test_duplicate_pci_falls_back_to_name_rule():
    from main.apps.mac.models.cell_state import CellState
    CellState.objects.create(cell_uuid="cell-d0", cell_id="west_c7", pci=7, total_prb=106, cell_created_at=0, cell_updated_at=0)

    class _Dup:
        cell_names = ["west#7", "mid#0", "east#7"]
    with patch.object(ccd, "get_du_cache", return_value=_Dup()):
        assert ccd.cell_id_to_tx("west_c7") == "west#7"
