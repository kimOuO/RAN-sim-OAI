"""Ru serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.radio_access_element.models.ru import Ru
from main.apps.preset_catalog.models.antenna_preset import AntennaPreset
from main.apps.radio_access_element.models.cell import Cell


class RuWriteSerializer(serializers.ModelSerializer):
    f_cell_uuid = serializers.SlugRelatedField(source="cell", slug_field="cell_uuid", queryset=Cell.objects.all())
    f_antenna_preset_uuid = serializers.SlugRelatedField(source="antenna_preset", slug_field="antenna_preset_uuid", queryset=AntennaPreset.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Ru
        fields = ['name', 'antenna_override', 'noise_figure_db', 'f_cell_uuid', 'f_antenna_preset_uuid']


class RuReadSerializer(serializers.ModelSerializer):
    f_cell_uuid = serializers.SlugRelatedField(source="cell", slug_field="cell_uuid", queryset=Cell.objects.all())
    f_antenna_preset_uuid = serializers.SlugRelatedField(source="antenna_preset", slug_field="antenna_preset_uuid", queryset=AntennaPreset.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Ru
        fields = ['id', 'ru_uuid', 'name', 'antenna_override', 'noise_figure_db', 'f_cell_uuid', 'f_antenna_preset_uuid', 'ru_created_at', 'ru_updated_at']
