"""E1AP serializers for CU-UP."""
from __future__ import annotations

from rest_framework import serializers


class _DrbConfigSerializer(serializers.Serializer):
    drb_id = serializers.IntegerField(min_value=1, max_value=32)
    qos_5qi = serializers.IntegerField(min_value=1, max_value=254)
    rlc_mode = serializers.CharField(default="AM")


class BearerContextSetupWriteSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    drbs = _DrbConfigSerializer(many=True)


class DrbReadSerializer(serializers.Serializer):
    ue_id = serializers.CharField()
    drb_id = serializers.IntegerField()
    qos_5qi = serializers.IntegerField()
    rlc_mode = serializers.CharField()
    gtp_teid_ul = serializers.IntegerField()
    gtp_teid_dl = serializers.IntegerField()
    dl_packets = serializers.IntegerField()
    ul_packets = serializers.IntegerField()
