"""Material serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.field_scene.models.material import Material


class MaterialWriteSerializer(serializers.ModelSerializer):
    pass

    class Meta:
        model = Material
        fields = ['key', 'itu_id', 'freq_range_ghz', 'notes']


class MaterialReadSerializer(serializers.ModelSerializer):
    pass

    class Meta:
        model = Material
        fields = ['id', 'material_uuid', 'key', 'itu_id', 'freq_range_ghz', 'notes', 'material_created_at', 'material_updated_at']
