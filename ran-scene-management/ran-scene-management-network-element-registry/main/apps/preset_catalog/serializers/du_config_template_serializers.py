"""DuConfigTemplate serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.preset_catalog.models.du_config_template import DuConfigTemplate


class DuConfigTemplateWriteSerializer(serializers.ModelSerializer):
    pass

    class Meta:
        model = DuConfigTemplate
        fields = ['name', 'tdd_pattern', 'numerology', 'n_prb', 'min_prb', 'pf_alpha', 'target_bler', 'rlc_discard_timer_ms', 'rlc_tx_maxsize_bytes', 'harq_max_retx', 'qos_gbr_first', 'gbr_max_share']


class DuConfigTemplateReadSerializer(serializers.ModelSerializer):
    pass

    class Meta:
        model = DuConfigTemplate
        fields = ['id', 'du_config_template_uuid', 'name', 'tdd_pattern', 'numerology', 'n_prb', 'min_prb', 'pf_alpha', 'target_bler', 'rlc_discard_timer_ms', 'rlc_tx_maxsize_bytes', 'harq_max_retx', 'qos_gbr_first', 'gbr_max_share', 'du_config_template_created_at', 'du_config_template_updated_at']
