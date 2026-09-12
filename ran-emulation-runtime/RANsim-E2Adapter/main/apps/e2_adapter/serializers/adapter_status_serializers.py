"""Adapter status read response serializer."""
from __future__ import annotations

from rest_framework import serializers


class _SctpLinkSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    target_host = serializers.CharField()
    target_port = serializers.IntegerField()
    connected = serializers.BooleanField()
    last_connect_at_ms = serializers.IntegerField()
    last_disconnect_at_ms = serializers.IntegerField()
    last_error = serializers.CharField(allow_blank=True)
    pdu_sent_count = serializers.IntegerField()
    pdu_recv_count = serializers.IntegerField()


class _E2SetupSerializer(serializers.Serializer):
    completed = serializers.BooleanField()
    accepted_ran_function_ids = serializers.ListField(child=serializers.IntegerField())
    rejected_ran_function_ids = serializers.ListField(child=serializers.IntegerField())


class _SchemasSerializer(serializers.Serializer):
    loaded = serializers.BooleanField()
    file_list = serializers.ListField(child=serializers.CharField())
    error = serializers.CharField(allow_blank=True)


class _SimBridgeSerializer(serializers.Serializer):
    cu_url = serializers.CharField()
    last_e2_node_id_at_ms = serializers.IntegerField()
    last_error = serializers.CharField(allow_blank=True)


class _CodecSelftestSerializer(serializers.Serializer):
    """離線可驗證的 PDU encode/decode 健康度。"""
    e2_setup_request_ok = serializers.BooleanField()
    e2_setup_request_size = serializers.IntegerField()
    kpm_indication_ok = serializers.BooleanField()
    kpm_indication_size = serializers.IntegerField()
    subscription_decode_ok = serializers.BooleanField()
    subscription_decoded_metrics = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    last_error = serializers.CharField(allow_blank=True)


class AdapterStatusReadSerializer(serializers.Serializer):
    """全域狀態 snapshot — Dashboard 顯示用 / ops debug 用。"""

    sctp_link = _SctpLinkSerializer()
    e2_setup = _E2SetupSerializer()
    schemas = _SchemasSerializer()
    sim_bridge = _SimBridgeSerializer()
    codec_selftest = _CodecSelftestSerializer()
