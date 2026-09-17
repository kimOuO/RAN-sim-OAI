"""RunKpmSample serializers — Write / Read 分離(backend_rule §3-3)。"""
from rest_framework import serializers

from main.apps.run_telemetry_archive.models.run_kpm_sample import RunKpmSample


class RunKpmSampleWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RunKpmSample
        fields = ['f_scene_run_uuid', 'window_index', 'sim_time_ms', 'wall_time_ms', 'per_cell', 'per_ue', 'warnings', 'scene_t_sec']


class RunKpmSampleReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = RunKpmSample
        fields = ['id', 'run_kpm_sample_uuid', 'f_scene_run_uuid', 'window_index', 'sim_time_ms', 'wall_time_ms', 'per_cell', 'per_ue', 'warnings', 'scene_t_sec', 'run_kpm_sample_created_at', 'run_kpm_sample_updated_at']
