"""測 ComputeRequestSerializer validation；不跑真 Sionna。"""
from main.apps.ran_signal.serializers.compute_serializers import ComputeRequestSerializer


def _valid_payload():
    return {
        "timestamp_ms": 1713420000500,
        "scene_id": "umi_3sector_v1",
        "ue_positions": [
            {"id": "UE_1", "position": [0, 1.5, 0], "velocity": [1, 0, 0]},
        ],
    }


def test_valid_payload():
    ser = ComputeRequestSerializer(data=_valid_payload())
    assert ser.is_valid(), ser.errors


def test_missing_scene_id():
    payload = _valid_payload()
    del payload["scene_id"]
    ser = ComputeRequestSerializer(data=payload)
    assert not ser.is_valid()
    assert "scene_id" in ser.errors


def test_wrong_position_length():
    payload = _valid_payload()
    payload["ue_positions"][0]["position"] = [0, 0]
    ser = ComputeRequestSerializer(data=payload)
    assert not ser.is_valid()
