"""Dashboard-facing serializers."""
from __future__ import annotations

from rest_framework import serializers


class HandoverWriteSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    target_cell = serializers.CharField(max_length=64)


class GetStateWriteSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)


class SessionListReadSerializer(serializers.Serializer):
    ue_id = serializers.CharField()
    rrc_state = serializers.CharField()
    serving_cell = serializers.CharField()
    last_measurement_at = serializers.DateTimeField(allow_null=True)


class UeStateReadSerializer(serializers.Serializer):
    ue_id = serializers.CharField()
    rrc_state = serializers.CharField()
    serving_cell = serializers.CharField()
    rrc_ue_id = serializers.IntegerField()
    amf_ue_ngap_id = serializers.IntegerField()
    ran_ue_ngap_id = serializers.IntegerField()
    gnb_du_id = serializers.IntegerField(allow_null=True)
    last_measurement_at = serializers.DateTimeField(allow_null=True)
