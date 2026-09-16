"""AntennaPreset serializers — Write / Read 分離(backend_rule §3-3)。FK 對外一律 f_<parent>_uuid。"""
from rest_framework import serializers

from main.apps.equipment_preset.models.antenna_preset import AntennaPreset


class AntennaPresetWriteSerializer(serializers.ModelSerializer):
    pass

    class Meta:
        model = AntennaPreset
        fields = ['name', 'source', 'pattern', 'rows', 'cols', 'polarization', 'v_spacing', 'h_spacing', 'polarization_model', 'max_gain_dbi', 'panels_mg', 'panels_ng', 'panel_v_spacing', 'panel_h_spacing', 'trx_v_group', 'trx_count', 'electrical_tilt_deg', 'csi_ports', 'port_n1', 'port_n2', 'ru_category', 'bf_method', 'gob_az_beams', 'gob_el_beams', 'notes']


class AntennaPresetReadSerializer(serializers.ModelSerializer):
    pass

    class Meta:
        model = AntennaPreset
        fields = ['id', 'antenna_preset_uuid', 'name', 'source', 'pattern', 'rows', 'cols', 'polarization', 'v_spacing', 'h_spacing', 'polarization_model', 'max_gain_dbi', 'panels_mg', 'panels_ng', 'panel_v_spacing', 'panel_h_spacing', 'trx_v_group', 'trx_count', 'electrical_tilt_deg', 'csi_ports', 'port_n1', 'port_n2', 'ru_category', 'bf_method', 'gob_az_beams', 'gob_el_beams', 'notes', 'antenna_preset_created_at', 'antenna_preset_updated_at']
