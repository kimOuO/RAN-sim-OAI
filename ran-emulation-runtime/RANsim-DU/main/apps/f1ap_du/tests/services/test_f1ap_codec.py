from ran_sim_protocol.common import CellConfig, DrbConfig
from ran_sim_protocol.f1ap import F1Setup, GnbDuMeasurementReport, UeContextSetup

from main.apps.f1ap_du.services.optional.message_codec.f1ap_codec import (
    decode_ue_context_setup,
    encode_f1_setup,
    encode_measurement_report,
)


def test_encode_f1_setup_roundtrip():
    msg = F1Setup(gnb_du_id=42, served_cells=[
        CellConfig(cell_id="c1", pci=1, frequency_ghz=3.5, bandwidth_mhz=100.0),
    ])
    d = encode_f1_setup(msg)
    assert d["gnb_du_id"] == 42
    assert d["served_cells"][0]["cell_id"] == "c1"


def test_decode_ue_context_setup():
    payload = {
        "ue_id": "ue-1",
        "drbs": [{"drb_id": 1, "qos_5qi": 9, "rlc_mode": "AM"}],
        "rrc_message_b64": "",
    }
    obj = decode_ue_context_setup(payload)
    assert obj.ue_id == "ue-1"
    assert obj.drbs[0].drb_id == 1
    assert isinstance(obj.drbs[0], DrbConfig)


def test_encode_measurement_report():
    msg = GnbDuMeasurementReport(
        ue_id="ue-1", rsrp_dbm=-80.0, sinr_db=15.0,
        throughput_dl_mbps=120.0, throughput_ul_mbps=30.0,
        mcs_dl=18, rb_width_dl=100, mimo_rank=2,
    )
    d = encode_measurement_report(msg)
    assert d["ue_id"] == "ue-1"
    assert d["mcs_dl"] == 18
