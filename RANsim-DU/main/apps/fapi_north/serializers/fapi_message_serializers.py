from rest_framework import serializers


class _NeighborMeasSerializer(serializers.Serializer):
    """A3 measurement event 用的 neighbor cell 量測 — RU 從 Sionna path_gain 算出。"""
    cell_id = serializers.CharField(max_length=64)
    rsrp_dbm = serializers.FloatField()
    rsrq_db = serializers.FloatField(default=0.0)


class CqiIndicationSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    sinr_db = serializers.FloatField()
    cqi = serializers.IntegerField(min_value=0, max_value=15)
    rank = serializers.IntegerField(min_value=1, max_value=4, default=1)
    pmi = serializers.IntegerField(default=0)
    # RU 從 Sionna path_gain 算的真 RSRP (RU 0.x 版本沒帶，預設 -200 表「未填」)
    rsrp_dbm = serializers.FloatField(default=-200.0)
    serving_cell = serializers.CharField(default="", allow_blank=True)
    # Neighbor cells — RU 從 Sionna 算所有非 serving gNB 的 RSRP
    # 對應 A3 evaluator 比對 RSRP(serving) vs RSRP(neighbor)
    neighbors = _NeighborMeasSerializer(many=True, default=list)


class CrcIndicationSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    harq_pid = serializers.IntegerField(min_value=0, max_value=15)
    success = serializers.BooleanField()
