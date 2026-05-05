"""DU setup endpoint integration."""
from __future__ import annotations

import json

import pytest
from django.test import Client


@pytest.mark.django_db
def test_du_setup_persists_and_responds():
    client = Client()
    body = {
        "gnb_du_id": 42,
        "served_cells": [
            {"cell_id": "c1", "pci": 1, "frequency_ghz": 3.5,
             "bandwidth_mhz": 100.0, "served_plmn": "00101"},
            {"cell_id": "c2", "pci": 2, "frequency_ghz": 3.5,
             "bandwidth_mhz": 100.0, "served_plmn": "00101"},
        ],
    }
    resp = client.post(
        "/api/v0.1/CU/F1AP/F1ApRouter/du_setup",
        data=json.dumps(body), content_type="application/json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True

    from main.apps.cu_cp.models.cell_config import CellConfig
    from main.apps.cu_cp.models.du_registry import DuRegistry
    assert DuRegistry.objects.filter(gnb_du_id=42).exists()
    assert CellConfig.objects.filter(served_by_du_id=42).count() == 2
