"""RunHandoverEvent serializers — Write / Read 分離(backend_rule §3-3)。"""
from rest_framework import serializers

from main.apps.run_telemetry_archive.models.run_handover_event import RunHandoverEvent


class RunHandoverEventWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RunHandoverEvent
        fields = ['run_seq', 'ric_run', 'f_scene_run_uuid', 'at_sim_ms', 'ue_id', 'source_cell', 'target_cell', 'outcome', 'detail']


class RunHandoverEventReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = RunHandoverEvent
        fields = ['id', 'run_handover_event_uuid', 'run_seq', 'ric_run', 'f_scene_run_uuid', 'at_sim_ms', 'ue_id', 'source_cell', 'target_cell', 'outcome', 'detail', 'node_id', 'meid', 'run_handover_event_created_at', 'run_handover_event_updated_at']
