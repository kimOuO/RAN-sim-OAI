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


class _RlcInjectSduItemSerializer(serializers.Serializer):
    """AL: batch inject 單筆 sub-SDU 描述."""
    sdu_bytes = serializers.IntegerField(min_value=1)
    # ts_offset_us = 此 packet 在 UE tick window 內的相對時間 (0 = window 開頭)
    ts_offset_us = serializers.IntegerField(min_value=0)


class RlcInjectSduBatchSerializer(serializers.Serializer):
    """AL: 一次 POST 帶 N 個 sub-SDU + 每包獨立 enqueue_ts.

    UE traffic_gen 100ms tick 累計的 bytes 拆成 N 個 1500B packet, 攤平在 tick window 內,
    每包帶獨立 ts_offset_us, DU 還原成 wall-clock enqueue_ts_ms 寫進 RLC entity.
    對齊真實 OAI per-packet inject 行為.
    """
    ue_id = serializers.CharField(max_length=64)
    bearer_type = serializers.ChoiceField(choices=["SRB", "DRB"])
    bearer_id = serializers.IntegerField(min_value=0, max_value=32)
    # UE tick window 長度 (ms). DU 用它把 ts_offset_us 映射回相對「現在」的 wall-clock.
    # AL: max 拉到 60s — UE 端已 clamp 1s, 這裡留餘裕避免邊界 race 失敗.
    window_ms = serializers.IntegerField(min_value=1, max_value=60_000, default=100)
    items = _RlcInjectSduItemSerializer(many=True)
