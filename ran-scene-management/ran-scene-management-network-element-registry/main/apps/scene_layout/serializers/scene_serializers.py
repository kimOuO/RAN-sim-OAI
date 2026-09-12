"""Scene serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.scene_layout.models.scene import Scene
from main.apps.preset_catalog.models.material import Material


class SceneWriteSerializer(serializers.ModelSerializer):
    f_material_uuid = serializers.SlugRelatedField(source="ground_material", slug_field="material_uuid", queryset=Material.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Scene
        fields = ['name', 'description', 'origin_lat', 'origin_lon', 'bounds', 'f_material_uuid']


class SceneReadSerializer(serializers.ModelSerializer):
    f_material_uuid = serializers.SlugRelatedField(source="ground_material", slug_field="material_uuid", queryset=Material.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Scene
        fields = ['id', 'scene_uuid', 'name', 'description', 'origin_lat', 'origin_lon', 'bounds', 'f_material_uuid', 'scene_created_at', 'scene_updated_at']
