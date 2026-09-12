"""LaunchRequest serializers — Write / Read 分離(backend_rule §3-3)。"""
from rest_framework import serializers

from main.apps.run_lifecycle.models.launch_request import LaunchRequest


class LaunchRequestWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaunchRequest
        fields = ['f_scene_run_uuid', 'action', 'mode', 'speed_x', 'status', 'detail']


class LaunchRequestReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaunchRequest
        fields = ['id', 'launch_request_uuid', 'f_scene_run_uuid', 'action', 'mode', 'speed_x', 'status', 'detail', 'launch_request_created_at', 'launch_request_updated_at']
