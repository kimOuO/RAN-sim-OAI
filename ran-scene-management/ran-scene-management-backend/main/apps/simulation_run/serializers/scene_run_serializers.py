"""SceneRun serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.simulation_run.models.scene_run import SceneRun
from main.apps.field_scene.models.scene import Scene


class SceneRunWriteSerializer(serializers.ModelSerializer):
    f_scene_uuid = serializers.SlugRelatedField(source="scene", slug_field="scene_uuid", queryset=Scene.objects.all())

    class Meta:
        model = SceneRun
        fields = ['mode', 'speed_x', 'sim_dt_ms', 'duration_sec', 'status', 'cache_path', 'e2_node_id', 'gnb_id_hex', 'snapshot_json', 'started_at', 'stopped_at', 'notes', 'f_scene_uuid']


class SceneRunReadSerializer(serializers.ModelSerializer):
    f_scene_uuid = serializers.SlugRelatedField(source="scene", slug_field="scene_uuid", queryset=Scene.objects.all())

    class Meta:
        model = SceneRun
        fields = ['id', 'scene_run_uuid', 'mode', 'speed_x', 'sim_dt_ms', 'duration_sec', 'status', 'cache_path', 'e2_node_id', 'gnb_id_hex', 'snapshot_json', 'started_at', 'stopped_at', 'notes', 'f_scene_uuid', 'scene_run_created_at', 'scene_run_updated_at']
