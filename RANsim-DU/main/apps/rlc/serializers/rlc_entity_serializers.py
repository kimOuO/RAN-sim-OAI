from rest_framework import serializers


class RlcEntityWriteSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    bearer_type = serializers.ChoiceField(choices=["SRB", "DRB"])
    bearer_id = serializers.IntegerField(min_value=0, max_value=32)
    mode = serializers.ChoiceField(choices=["AM", "UM", "TM"])
    sn_field_length = serializers.IntegerField(default=12)


class RlcEntityReadSerializer(serializers.Serializer):
    rlc_uuid = serializers.CharField()
    ue_id = serializers.CharField()
    bearer_type = serializers.CharField()
    bearer_id = serializers.IntegerField()
    mode = serializers.CharField()
    sn_field_length = serializers.IntegerField()
    tx_buffer_bytes = serializers.IntegerField()
    rx_buffer_bytes = serializers.IntegerField()
    retx_count = serializers.IntegerField()
    status_pdu_pending = serializers.BooleanField()
    rlc_created_at = serializers.IntegerField()
    rlc_updated_at = serializers.IntegerField()


class RlcInjectSduSerializer(serializers.Serializer):
    """測試/F1-U 模擬:推一段 SDU 進對應 entity。"""
    ue_id = serializers.CharField(max_length=64)
    bearer_type = serializers.ChoiceField(choices=["SRB", "DRB"])
    bearer_id = serializers.IntegerField(min_value=0, max_value=32)
    sdu_bytes = serializers.IntegerField(min_value=1)
