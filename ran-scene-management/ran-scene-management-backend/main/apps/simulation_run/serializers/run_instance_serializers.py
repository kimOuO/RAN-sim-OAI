"""RunInstance serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.simulation_run.models.run_instance import RunInstance
from main.apps.simulation_run.models.scene_run import SceneRun


class RunInstanceWriteSerializer(serializers.ModelSerializer):
    f_scene_run_uuid = serializers.SlugRelatedField(source="scene_run", slug_field="scene_run_uuid", queryset=SceneRun.objects.all())

    class Meta:
        model = RunInstance
        fields = ['role', 'name', 'gnb_uuid', 'du_uuid', 'e2_node_id', 'container_id', 'host_port', 'status', 'last_heartbeat', 'health_detail', 'f_scene_run_uuid']


class RunInstanceReadSerializer(serializers.ModelSerializer):
    f_scene_run_uuid = serializers.SlugRelatedField(source="scene_run", slug_field="scene_run_uuid", queryset=SceneRun.objects.all())

    class Meta:
        model = RunInstance
        fields = ['id', 'run_instance_uuid', 'role', 'name', 'gnb_uuid', 'du_uuid', 'e2_node_id', 'container_id', 'host_port', 'status', 'last_heartbeat', 'health_detail', 'f_scene_run_uuid', 'run_instance_created_at', 'run_instance_updated_at']
