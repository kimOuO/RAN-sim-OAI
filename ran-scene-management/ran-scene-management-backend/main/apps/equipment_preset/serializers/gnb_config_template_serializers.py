"""GnbConfigTemplate serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.equipment_preset.models.antenna_preset import AntennaPreset
from main.apps.equipment_preset.models.du_config_template import DuConfigTemplate
from main.apps.equipment_preset.models.gnb_config_template import GnbConfigTemplate

_F = ['name', 'source', 'notes', 'plmn_mcc', 'plmn_mnc', 'a3_enabled', 'a3_offset_db', 'a3_hys_db', 'a3_ttt_ms', 'band', 'center_frequency_ghz', 'bandwidth_mhz', 'power_dbm', 'tilt_deg', 'cells_per_gnb', 'azimuth_step_deg', 'f_du_config_template_uuid', 'f_antenna_preset_uuid']


class GnbConfigTemplateWriteSerializer(serializers.ModelSerializer):
    f_du_config_template_uuid = serializers.SlugRelatedField(source="du_config_template", slug_field="du_config_template_uuid", queryset=DuConfigTemplate.objects.all(), required=False, allow_null=True)
    f_antenna_preset_uuid = serializers.SlugRelatedField(source="antenna_preset", slug_field="antenna_preset_uuid", queryset=AntennaPreset.objects.all(), required=False, allow_null=True)

    class Meta:
        model = GnbConfigTemplate
        fields = _F


class GnbConfigTemplateReadSerializer(serializers.ModelSerializer):
    f_du_config_template_uuid = serializers.SlugRelatedField(source="du_config_template", slug_field="du_config_template_uuid", read_only=True)
    f_antenna_preset_uuid = serializers.SlugRelatedField(source="antenna_preset", slug_field="antenna_preset_uuid", read_only=True)

    class Meta:
        model = GnbConfigTemplate
        fields = ['id', 'gnb_config_template_uuid', *_F, 'gnb_config_template_created_at', 'gnb_config_template_updated_at']
