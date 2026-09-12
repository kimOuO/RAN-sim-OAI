"""RunKnob serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.simulation_run.models.run_knob import RunKnob
from main.apps.simulation_run.models.scene_run import SceneRun


class RunKnobWriteSerializer(serializers.ModelSerializer):
    f_scene_run_uuid = serializers.SlugRelatedField(source="scene_run", slug_field="scene_run_uuid", queryset=SceneRun.objects.all())

    class Meta:
        model = RunKnob
        fields = ['key', 'value', 'f_scene_run_uuid']


class RunKnobReadSerializer(serializers.ModelSerializer):
    f_scene_run_uuid = serializers.SlugRelatedField(source="scene_run", slug_field="scene_run_uuid", queryset=SceneRun.objects.all())

    class Meta:
        model = RunKnob
        fields = ['id', 'run_knob_uuid', 'key', 'value', 'f_scene_run_uuid', 'run_knob_created_at', 'run_knob_updated_at']
