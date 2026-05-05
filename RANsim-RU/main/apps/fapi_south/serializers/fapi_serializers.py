"""FAPI Read/Write — 比起 DRF 完整驗證，主要靠 ran_sim_protocol dataclass 還原。

這裡只放輕量 sanity check（sfn/slot 範圍、pdus 必填）。
"""
from rest_framework import serializers


class _PduSerializer(serializers.Serializer):
    ue_id = serializers.CharField()
    prb_start = serializers.IntegerField(min_value=0, max_value=274)
    prb_count = serializers.IntegerField(min_value=1, max_value=275)
    mcs = serializers.IntegerField(min_value=0, max_value=31)
    layers = serializers.IntegerField(min_value=1, max_value=4, required=False, default=1)
    pmi = serializers.IntegerField(min_value=0, max_value=63, required=False, default=0)
    payload_size_bytes = serializers.IntegerField(min_value=0, required=False, default=0)
    harq_pid = serializers.IntegerField(min_value=0, max_value=15, required=False, default=0)


class DlTtiRequestSerializer(serializers.Serializer):
    sfn = serializers.IntegerField(min_value=0, max_value=1023)
    slot = serializers.IntegerField(min_value=0, max_value=159)
    pdus = _PduSerializer(many=True)


class UlTtiRequestSerializer(serializers.Serializer):
    sfn = serializers.IntegerField(min_value=0, max_value=1023)
    slot = serializers.IntegerField(min_value=0, max_value=159)
    pdus = _PduSerializer(many=True)
