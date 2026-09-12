"""Gnb serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.radio_access_element.models.gnb import Gnb
from main.apps.scene_layout.models.scene import Scene


class GnbWriteSerializer(serializers.ModelSerializer):
    f_scene_uuid = serializers.SlugRelatedField(source="scene", slug_field="scene_uuid", queryset=Scene.objects.all())

    class Meta:
        model = Gnb
        fields = ['name', 'is_active', 'color', 'gnb_id', 'plmn_mcc', 'plmn_mnc', 'position', 'a3_enabled', 'a3_offset_db', 'a3_hys_db', 'a3_ttt_ms', 'f_scene_uuid']


class GnbReadSerializer(serializers.ModelSerializer):
    f_scene_uuid = serializers.SlugRelatedField(source="scene", slug_field="scene_uuid", queryset=Scene.objects.all())

    class Meta:
        model = Gnb
        fields = ['id', 'gnb_uuid', 'name', 'is_active', 'color', 'gnb_id', 'plmn_mcc', 'plmn_mnc', 'position', 'a3_enabled', 'a3_offset_db', 'a3_hys_db', 'a3_ttt_ms', 'f_scene_uuid', 'gnb_created_at', 'gnb_updated_at']
