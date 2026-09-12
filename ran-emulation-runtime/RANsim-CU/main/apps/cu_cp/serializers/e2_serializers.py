"""E2 KPM read serializer (passthrough — output is dict)."""
from __future__ import annotations

from rest_framework import serializers


class KpmReadEmptyRequestSerializer(serializers.Serializer):
    """Empty request body acceptance (POST keeps semantic; body is ignored)."""

    pass
