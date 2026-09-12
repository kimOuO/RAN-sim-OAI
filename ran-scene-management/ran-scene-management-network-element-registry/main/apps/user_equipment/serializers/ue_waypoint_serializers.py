"""UeWaypoint serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.user_equipment.models.ue_waypoint import UeWaypoint
from main.apps.user_equipment.models.ue import Ue


class UeWaypointWriteSerializer(serializers.ModelSerializer):
    f_ue_uuid = serializers.SlugRelatedField(source="ue", slug_field="ue_uuid", queryset=Ue.objects.all())

    class Meta:
        model = UeWaypoint
        fields = ['ord', 't_sec', 'x', 'y', 'z', 'f_ue_uuid']


class UeWaypointReadSerializer(serializers.ModelSerializer):
    f_ue_uuid = serializers.SlugRelatedField(source="ue", slug_field="ue_uuid", queryset=Ue.objects.all())

    class Meta:
        model = UeWaypoint
        fields = ['id', 'ue_waypoint_uuid', 'ord', 't_sec', 'x', 'y', 'z', 'f_ue_uuid', 'ue_waypoint_created_at', 'ue_waypoint_updated_at']
