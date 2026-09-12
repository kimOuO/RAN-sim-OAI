"""KPM snapshot read response serializer."""
from __future__ import annotations

from rest_framework import serializers


class KpmSnapshotReadSerializer(serializers.Serializer):
    """Latest UE × metric snapshot."""
    ues = serializers.ListField(child=serializers.DictField())
    last_update_ms = serializers.IntegerField()
    total_indications = serializers.IntegerField()


class KpmRecentReadSerializer(serializers.Serializer):
    entries = serializers.ListField(child=serializers.DictField())
    count = serializers.IntegerField()


class KpmHistoryReadSerializer(serializers.Serializer):
    ue_id = serializers.CharField()
    metric = serializers.CharField()
    points = serializers.ListField(child=serializers.DictField())
