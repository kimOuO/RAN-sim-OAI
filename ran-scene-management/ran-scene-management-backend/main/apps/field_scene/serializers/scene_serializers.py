"""Scene serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
import re

from rest_framework import serializers

from main.apps.field_scene.models.scene import Scene
from main.apps.equipment_preset.models.antenna_preset import AntennaPreset
from main.apps.field_scene.models.material import Material


class SceneWriteSerializer(serializers.ModelSerializer):
    f_material_uuid = serializers.SlugRelatedField(source="ground_material", slug_field="material_uuid", queryset=Material.objects.all(), required=False, allow_null=True)
    f_gnb_antenna_preset_uuid = serializers.SlugRelatedField(source="gnb_antenna_preset", slug_field="antenna_preset_uuid", queryset=AntennaPreset.objects.all(), required=False, allow_null=True)
    f_ue_antenna_preset_uuid = serializers.SlugRelatedField(source="ue_antenna_preset", slug_field="antenna_preset_uuid", queryset=AntennaPreset.objects.all(), required=False, allow_null=True)

    # 2026-09-20:legacy_scenario_id 會直接當通道快取檔名(<id>.npz / <id>.paths)並傳給
    # precompute 的 shell,所以字元集要鎖死;兩個場景撞同一個 id 會互相蓋掉快取,也要擋。
    def validate_legacy_scenario_id(self, value: str) -> str:
        v = (value or "").strip()
        if not v:
            return ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", v):
            raise serializers.ValidationError("只能用英數字、底線與連字號(這個值會變成快取檔名)")
        qs = Scene.objects.filter(legacy_scenario_id=v)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        other = qs.first()
        if other is not None:
            raise serializers.ValidationError(f"已被場景「{other.name}」使用,兩者會共用同一份通道快取")
        return v

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
