"""Compute API 的 Read / Write 序列化器 — 鐵則 3-3 必須區分 Write / Read。"""
from rest_framework import serializers


# ─── Write（外部平台 → 模擬RAN）───────────────────────────────────

class Vec3Field(serializers.ListField):
    """[x, y, z] 三元座標，單位公尺。"""

    def __init__(self, **kwargs):
        kwargs.setdefault("child", serializers.FloatField())
        kwargs.setdefault("min_length", 3)
        kwargs.setdefault("max_length", 3)
        super().__init__(**kwargs)


class UEPositionWriteSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=128)
    position = Vec3Field()
    velocity = Vec3Field(required=False, default=[0.0, 0.0, 0.0])
    role = serializers.IntegerField(required=False, default=1)
    qos_5qi = serializers.IntegerField(required=False, default=9)


class ComputeRequestSerializer(serializers.Serializer):
    timestamp_ms = serializers.IntegerField(min_value=0)
    scene_id = serializers.CharField(max_length=128)
    ue_positions = UEPositionWriteSerializer(many=True)

    def validate_ue_positions(self, value):
        from main.utils.env_loader import get_int
        max_n = get_int("SIM_MAX_UES_PER_TICK", default=50)
        if len(value) > max_n:
            raise serializers.ValidationError(
                f"ue_positions[] has {len(value)} items; limit is {max_n}"
            )
        return value


# ─── Read（模擬RAN → 外部平台）───────────────────────────────────

class NeighborCellReadSerializer(serializers.Serializer):
    """{"<cell_id>": {"rsrp": ..., "rsrq": ...}} 一個 dict；DRF 直接吐 dict。"""


class UEKpiReadSerializer(serializers.Serializer):
    role = serializers.IntegerField()
    ue_id = serializers.CharField()
    interfered = serializers.IntegerField()
    rsrp = serializers.IntegerField()
    rsrq = serializers.IntegerField()
    sinr = serializers.IntegerField()
    neighbors = serializers.ListField(child=serializers.DictField())
    dl_throughput = serializers.IntegerField()
    ul_throughput = serializers.IntegerField()
    rb_start = serializers.IntegerField()
    rb_width = serializers.IntegerField()


class CellReadSerializer(serializers.Serializer):
    cell_id = serializers.CharField()
    ran_name = serializers.CharField()
    pci = serializers.IntegerField()
    ues = UEKpiReadSerializer(many=True)


class E2EntryReadSerializer(serializers.Serializer):
    gnb_id = serializers.CharField()
    timestamp = serializers.IntegerField()
    cells = CellReadSerializer(many=True)


class UeStatusReadSerializer(serializers.Serializer):
    ue_id = serializers.CharField()
    position = Vec3Field()
    serving_gnb = serializers.CharField()
    serving_pci = serializers.IntegerField()
    rsrp_dbm = serializers.FloatField()
    sinr_db = serializers.FloatField()
    all_rsrp = serializers.DictField(child=serializers.FloatField())
    throughput_dl_mbps = serializers.IntegerField()
    throughput_ul_mbps = serializers.IntegerField(required=False)
    quality = serializers.CharField()
    qos_5qi = serializers.IntegerField(required=False, default=9)
    role = serializers.IntegerField(required=False, default=1)
    mcs_dl = serializers.IntegerField(required=False)
    rb_width_dl = serializers.IntegerField(required=False)
    mimo_rank = serializers.IntegerField(required=False, default=1)
    mimo_streams_sinr_db = serializers.ListField(child=serializers.FloatField(), required=False, default=list)
    mimo_streams_mcs = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


class ComputeResponseSerializer(serializers.Serializer):
    timestamp_ms = serializers.IntegerField()
    compute_ms = serializers.IntegerField()
    tick_ms = serializers.IntegerField(required=False)
    e2 = E2EntryReadSerializer(many=True)
    ue_status = UeStatusReadSerializer(many=True)
    # pm 區塊欄位眾多且 dynamic key（gnb-<pci>），直接用 DictField 不做子欄位驗證
    pm = serializers.DictField(required=False, default=dict)
    # bbu_status 同理，key 是 gnb-<pci> 或 "timestamp"
    bbu_status = serializers.DictField(required=False, default=dict)
    warnings = serializers.ListField(child=serializers.CharField())
