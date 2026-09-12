"""UeTraffic serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.user_equipment.models.ue_traffic import UeTraffic
from main.apps.user_equipment.models.ue import Ue


class UeTrafficWriteSerializer(serializers.ModelSerializer):
    f_ue_uuid = serializers.SlugRelatedField(source="ue", slug_field="ue_uuid", queryset=Ue.objects.all())

    class Meta:
        model = UeTraffic
        fields = ['pattern', 'rate_mbps', 'schedule', 'bearer_id', 'f_ue_uuid']


class UeTrafficReadSerializer(serializers.ModelSerializer):
    f_ue_uuid = serializers.SlugRelatedField(source="ue", slug_field="ue_uuid", queryset=Ue.objects.all())

    class Meta:
        model = UeTraffic
        fields = ['id', 'ue_traffic_uuid', 'pattern', 'rate_mbps', 'schedule', 'bearer_id', 'f_ue_uuid', 'ue_traffic_created_at', 'ue_traffic_updated_at']
