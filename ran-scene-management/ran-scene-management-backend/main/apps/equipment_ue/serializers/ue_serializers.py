"""Ue serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.equipment_ue.models.ue import Ue
from main.apps.equipment_preset.models.antenna_preset import AntennaPreset
from main.apps.field_scene.models.scene import Scene


class UeWriteSerializer(serializers.ModelSerializer):
    f_scene_uuid = serializers.SlugRelatedField(source="scene", slug_field="scene_uuid", queryset=Scene.objects.all())
    f_antenna_preset_uuid = serializers.SlugRelatedField(source="antenna_preset", slug_field="antenna_preset_uuid", queryset=AntennaPreset.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Ue
        fields = ['name', 'loop', 'speed_mps', 'presence_restricted', 'antenna_height_m', 'qos_5qi', 'color', 'f_scene_uuid', 'f_antenna_preset_uuid']


class UeReadSerializer(serializers.ModelSerializer):
    f_scene_uuid = serializers.SlugRelatedField(source="scene", slug_field="scene_uuid", queryset=Scene.objects.all())
    f_antenna_preset_uuid = serializers.SlugRelatedField(source="antenna_preset", slug_field="antenna_preset_uuid", queryset=AntennaPreset.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Ue
        fields = ['id', 'ue_uuid', 'name', 'loop', 'speed_mps', 'presence_restricted', 'antenna_height_m', 'qos_5qi', 'color', 'f_scene_uuid', 'f_antenna_preset_uuid', 'ue_created_at', 'ue_updated_at']
