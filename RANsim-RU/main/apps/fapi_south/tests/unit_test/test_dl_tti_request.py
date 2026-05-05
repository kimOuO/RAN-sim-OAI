"""dl_tti_request actor：mock physics + du_callback，確認 actor 對每個 PDU 各送一次 CQI。"""
import json
from unittest.mock import patch

import numpy as np
import pytest
from django.utils import timezone
from ran_sim_protocol.physics import PathSolverResponse
from rest_framework.test import APIClient

from main.apps.antenna.models.antenna_config import AntennaConfig
from main.apps.antenna.models.cell import Cell
from main.apps.antenna.models.ue_position import UePosition


def _seed():
    now = timezone.now()
    AntennaConfig.objects.create(
        antenna_config_uuid="antenna_t1",
        rows=2, cols=1, polarization="V", pattern="tr38901",
        antenna_config_created_at=now, antenna_config_updated_at=now,
    )
    Cell.objects.create(
        cell_uuid="cell_t1", name="gnb1", pci=1, azimuth_deg=0,
        position_x=0, position_y=10, position_z=0,
        cell_created_at=now, cell_updated_at=now,
    )
    UePosition.objects.create(
        ue_position_uuid="ue_t1", ue_id="ue-1",
        position_x=10, position_y=0, position_z=1.5,
        ue_position_created_at=now, ue_position_updated_at=now,
    )


@pytest.mark.django_db
def test_dl_tti_request_emits_one_cqi_per_pdu():
    _seed()
    client = APIClient()

    fake_resp = PathSolverResponse(
        channel_matrix={"ue-1": {"gnb1": [[[1.0, 0.0]], [[0.0, 0.5]]]}},  # (2,1) complex
        path_gain={"ue-1": {"gnb1": 0.25}},
        serving_cells={"ue-1": "gnb1"},
    )

    payload = {
        "sfn": 10, "slot": 5,
        "pdus": [
            {"ue_id": "ue-1", "prb_start": 0, "prb_count": 4, "mcs": 10,
             "layers": 1, "pmi": 0, "harq_pid": 0, "payload_size_bytes": 100},
        ],
    }

    with patch(
        "main.apps.fapi_south.services.optional.dl_tti_pipeline.physics_http.compute_paths",
        return_value=fake_resp,
    ), patch(
        "main.apps.fapi_south.services.optional.du_callback.send_cqi_indication",
    ) as mock_du:
        resp = client.post(
            "/api/v0.1/RU/FAPI/FapiRouter/dl_tti_request",
            data=json.dumps(payload),
            content_type="application/json",
        )

    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["data"]["accepted_pdus"] == 1
    assert mock_du.call_count == 1
    cqi = mock_du.call_args[0][0]
    assert cqi.ue_id == "ue-1"
    assert cqi.cqi >= 0
