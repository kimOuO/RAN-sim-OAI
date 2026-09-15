"""NeighborSeed serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.equipment_ran.models.neighbor_seed import NeighborSeed
from main.apps.equipment_ran.models.cell import Cell


class NeighborSeedWriteSerializer(serializers.ModelSerializer):
    f_source_cell_uuid = serializers.SlugRelatedField(source="source_cell", slug_field="cell_uuid", queryset=Cell.objects.all())
    f_target_cell_uuid = serializers.SlugRelatedField(source="target_cell", slug_field="cell_uuid", queryset=Cell.objects.all())

    class Meta:
        model = NeighborSeed
        fields = ['ho_blocklist', 'no_remove', 'xn_blocklist', 'f_source_cell_uuid', 'f_target_cell_uuid']


class NeighborSeedReadSerializer(serializers.ModelSerializer):
    f_source_cell_uuid = serializers.SlugRelatedField(source="source_cell", slug_field="cell_uuid", queryset=Cell.objects.all())
    f_target_cell_uuid = serializers.SlugRelatedField(source="target_cell", slug_field="cell_uuid", queryset=Cell.objects.all())

    class Meta:
        model = NeighborSeed
        fields = ['id', 'neighbor_seed_uuid', 'ho_blocklist', 'no_remove', 'xn_blocklist', 'f_source_cell_uuid', 'f_target_cell_uuid', 'neighbor_seed_created_at', 'neighbor_seed_updated_at']
