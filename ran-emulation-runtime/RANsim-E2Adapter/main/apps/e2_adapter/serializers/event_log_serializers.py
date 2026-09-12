"""E2 event log read response serializer."""
from __future__ import annotations

from rest_framework import serializers


class EventLogReadSerializer(serializers.Serializer):
    """Read response — Dashboard /logs page 拉 E2 plane 事件 timeline。"""

    entries = serializers.ListField(child=serializers.DictField())
    count = serializers.IntegerField()
    last_seq = serializers.IntegerField()
