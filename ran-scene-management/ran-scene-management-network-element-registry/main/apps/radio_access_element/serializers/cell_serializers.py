"""Cell serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.radio_access_element.models.cell import Cell
from main.apps.radio_access_element.models.du import Du


class CellWriteSerializer(serializers.ModelSerializer):
    f_du_uuid = serializers.SlugRelatedField(source="du", slug_field="du_uuid", queryset=Du.objects.all())

    class Meta:
        model = Cell
        fields = ['name', 'center_frequency_ghz', 'pci', 'nr_cellid', 'arfcn', 'band', 'bandwidth_mhz', 'position', 'azimuth_deg', 'tilt_deg', 'power_dbm', 'is_active', 'is_barred', 'f_du_uuid']


class CellReadSerializer(serializers.ModelSerializer):
    f_du_uuid = serializers.SlugRelatedField(source="du", slug_field="du_uuid", queryset=Du.objects.all())

    class Meta:
        model = Cell
        fields = ['id', 'cell_uuid', 'name', 'center_frequency_ghz', 'pci', 'nr_cellid', 'arfcn', 'band', 'bandwidth_mhz', 'position', 'azimuth_deg', 'tilt_deg', 'power_dbm', 'is_active', 'is_barred', 'f_du_uuid', 'cell_created_at', 'cell_updated_at']
