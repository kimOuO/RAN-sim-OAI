"""UeActiveWindow serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.equipment_ue.models.ue_active_window import UeActiveWindow
from main.apps.equipment_ue.models.ue import Ue


class UeActiveWindowWriteSerializer(serializers.ModelSerializer):
    f_ue_uuid = serializers.SlugRelatedField(source="ue", slug_field="ue_uuid", queryset=Ue.objects.all())

    class Meta:
        model = UeActiveWindow
        fields = ['t0_sec', 't1_sec', 'f_ue_uuid']


class UeActiveWindowReadSerializer(serializers.ModelSerializer):
    f_ue_uuid = serializers.SlugRelatedField(source="ue", slug_field="ue_uuid", queryset=Ue.objects.all())

    class Meta:
        model = UeActiveWindow
        fields = ['id', 'ue_active_window_uuid', 't0_sec', 't1_sec', 'f_ue_uuid', 'ue_active_window_created_at', 'ue_active_window_updated_at']
