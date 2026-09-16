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
    # 三層天線(2026-09-16;舊呼叫端不帶 → 用預設值,行為等同「一片元件 = 一個 TXRU = 一個埠」)
    panels_mg = serializers.IntegerField(required=False, default=1, min_value=1, max_value=8)
    panels_ng = serializers.IntegerField(required=False, default=1, min_value=1, max_value=8)
    panel_v_spacing = serializers.FloatField(required=False, default=0.0, min_value=0.0, max_value=20.0)
    panel_h_spacing = serializers.FloatField(required=False, default=0.0, min_value=0.0, max_value=20.0)
    trx_v_group = serializers.IntegerField(required=False, default=1, min_value=1, max_value=16)
    trx_count = serializers.IntegerField(required=False, default=0, min_value=0, max_value=1024)
    electrical_tilt_deg = serializers.FloatField(required=False, default=0.0, min_value=-30.0, max_value=30.0)
    csi_ports = serializers.IntegerField(required=False, default=0, min_value=0, max_value=32)
    port_n1 = serializers.IntegerField(required=False, default=0, min_value=0, max_value=16)
    port_n2 = serializers.IntegerField(required=False, default=0, min_value=0, max_value=16)
    ru_category = serializers.ChoiceField(required=False, default='A', choices=['A', 'B'])
    bf_method = serializers.CharField(required=False, allow_blank=True, default='', max_length=16)
    gob_az_beams = serializers.IntegerField(required=False, default=0, min_value=0, max_value=256)
    gob_el_beams = serializers.IntegerField(required=False, default=0, min_value=0, max_value=64)

    ue_rows = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=16)
    ue_cols = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=16)
    ue_pattern = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=32)
    ue_polarization = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=16)


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
            "panels_mg",
            "panels_ng",
            "panel_v_spacing",
            "panel_h_spacing",
            "trx_v_group",
            "trx_count",
            "electrical_tilt_deg",
            "csi_ports",
            "port_n1",
            "port_n2",
            "ru_category",
            "bf_method",
            "gob_az_beams",
            "gob_el_beams",
            "antenna_config_updated_at",
        ]
