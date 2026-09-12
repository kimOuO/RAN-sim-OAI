"""AntennaConfig Read/Write — backend_rule §3-3。

合法值對齊 ran_sim_protocol.common.AntennaArrayConfig。
"""
from rest_framework import serializers

from main.apps.antenna.models.antenna_config import (
    AntennaConfig,
    PATTERN_CHOICES,
    POLARIZATION_CHOICES,
)


_POLARIZATION_VALUES = [v for v, _ in POLARIZATION_CHOICES]
_PATTERN_VALUES = [v for v, _ in PATTERN_CHOICES]


class AntennaConfigWriteSerializer(serializers.Serializer):
    rows = serializers.IntegerField(min_value=1, max_value=64)
    cols = serializers.IntegerField(min_value=1, max_value=64)
    polarization = serializers.ChoiceField(choices=_POLARIZATION_VALUES)
    pattern = serializers.ChoiceField(choices=_PATTERN_VALUES)
    vertical_spacing = serializers.FloatField(required=False, default=0.5, min_value=0.1, max_value=4.0)
    horizontal_spacing = serializers.FloatField(required=False, default=0.5, min_value=0.1, max_value=4.0)


class AntennaConfigReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AntennaConfig
        fields = [
            "antenna_config_uuid",
            "rows",
            "cols",
            "polarization",
            "pattern",
            "vertical_spacing",
            "horizontal_spacing",
            "antenna_config_updated_at",
        ]
