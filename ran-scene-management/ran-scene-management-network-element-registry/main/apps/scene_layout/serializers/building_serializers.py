"""Building serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.scene_layout.models.building import Building
from main.apps.preset_catalog.models.material import Material
from main.apps.scene_layout.models.scene import Scene


class BuildingWriteSerializer(serializers.ModelSerializer):
    f_scene_uuid = serializers.SlugRelatedField(source="scene", slug_field="scene_uuid", queryset=Scene.objects.all())
    f_material_uuid = serializers.SlugRelatedField(source="default_material", slug_field="material_uuid", queryset=Material.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Building
        fields = ['name', 'source', 'geometry_ref', 'position', 'rotation', 'scale', 'size', 'materials_npz', 'f_scene_uuid', 'f_material_uuid']


class BuildingReadSerializer(serializers.ModelSerializer):
    f_scene_uuid = serializers.SlugRelatedField(source="scene", slug_field="scene_uuid", queryset=Scene.objects.all())
    f_material_uuid = serializers.SlugRelatedField(source="default_material", slug_field="material_uuid", queryset=Material.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Building
        fields = ['id', 'building_uuid', 'name', 'source', 'geometry_ref', 'position', 'rotation', 'scale', 'size', 'materials_npz', 'f_scene_uuid', 'f_material_uuid', 'building_created_at', 'building_updated_at']
