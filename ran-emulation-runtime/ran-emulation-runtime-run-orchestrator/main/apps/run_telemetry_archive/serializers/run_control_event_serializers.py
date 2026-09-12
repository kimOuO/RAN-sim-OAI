"""RunControlEvent serializers — Write / Read 分離(backend_rule §3-3)。"""
from rest_framework import serializers

from main.apps.run_telemetry_archive.models.run_control_event import RunControlEvent


class RunControlEventWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RunControlEvent
        fields = ['f_scene_run_uuid', 'at_sim_ms', 'source', 'action_type', 'target', 'outcome', 'landing_latency_ms', 'detail']


class RunControlEventReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = RunControlEvent
        fields = ['id', 'run_control_event_uuid', 'f_scene_run_uuid', 'at_sim_ms', 'source', 'action_type', 'target', 'outcome', 'landing_latency_ms', 'detail', 'run_control_event_created_at', 'run_control_event_updated_at']
