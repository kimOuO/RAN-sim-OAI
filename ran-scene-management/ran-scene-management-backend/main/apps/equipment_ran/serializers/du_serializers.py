"""Du serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.equipment_ran.models.du import Du
from main.apps.equipment_preset.models.du_config_template import DuConfigTemplate
from main.apps.equipment_ran.models.gnb import Gnb


class DuWriteSerializer(serializers.ModelSerializer):
    f_gnb_uuid = serializers.SlugRelatedField(source="gnb", slug_field="gnb_uuid", queryset=Gnb.objects.all())
    f_du_config_template_uuid = serializers.SlugRelatedField(source="config_template", slug_field="du_config_template_uuid", queryset=DuConfigTemplate.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Du
        fields = ['name', 'gnb_du_id', 'config_override', 'f_gnb_uuid', 'f_du_config_template_uuid']


class DuReadSerializer(serializers.ModelSerializer):
    f_gnb_uuid = serializers.SlugRelatedField(source="gnb", slug_field="gnb_uuid", queryset=Gnb.objects.all())
    f_du_config_template_uuid = serializers.SlugRelatedField(source="config_template", slug_field="du_config_template_uuid", queryset=DuConfigTemplate.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Du
        fields = ['id', 'du_uuid', 'name', 'gnb_du_id', 'config_override', 'f_gnb_uuid', 'f_du_config_template_uuid', 'du_created_at', 'du_updated_at']
