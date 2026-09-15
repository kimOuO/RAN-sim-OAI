"""Scene serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.field_scene.models.scene import Scene
from main.apps.equipment_preset.models.antenna_preset import AntennaPreset
from main.apps.field_scene.models.material import Material


class SceneWriteSerializer(serializers.ModelSerializer):
    f_material_uuid = serializers.SlugRelatedField(source="ground_material", slug_field="material_uuid", queryset=Material.objects.all(), required=False, allow_null=True)
    f_gnb_antenna_preset_uuid = serializers.SlugRelatedField(source="gnb_antenna_preset", slug_field="antenna_preset_uuid", queryset=AntennaPreset.objects.all(), required=False, allow_null=True)
    f_ue_antenna_preset_uuid = serializers.SlugRelatedField(source="ue_antenna_preset", slug_field="antenna_preset_uuid", queryset=AntennaPreset.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Scene
        fields = ['name', 'legacy_scenario_id', 'geometry_scene_id', 'geometry_source', 'description', 'origin_lat', 'origin_lon', 'bounds', 'f_material_uuid', 'f_gnb_antenna_preset_uuid', 'f_ue_antenna_preset_uuid']


class SceneReadSerializer(serializers.ModelSerializer):
    f_material_uuid = serializers.SlugRelatedField(source="ground_material", slug_field="material_uuid", queryset=Material.objects.all(), required=False, allow_null=True)
    f_gnb_antenna_preset_uuid = serializers.SlugRelatedField(source="gnb_antenna_preset", slug_field="antenna_preset_uuid", read_only=True)
    f_ue_antenna_preset_uuid = serializers.SlugRelatedField(source="ue_antenna_preset", slug_field="antenna_preset_uuid", read_only=True)

    class Meta:
        model = Scene
        fields = ['id', 'scene_uuid', 'name', 'legacy_scenario_id', 'geometry_scene_id', 'geometry_source', 'description', 'origin_lat', 'origin_lon', 'bounds', 'f_material_uuid', 'f_gnb_antenna_preset_uuid', 'f_ue_antenna_preset_uuid', 'scene_created_at', 'scene_updated_at']
