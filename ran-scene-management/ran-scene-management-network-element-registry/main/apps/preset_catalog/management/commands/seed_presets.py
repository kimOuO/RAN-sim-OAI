"""seed_presets — 建立預設資源(冪等):
- DU 設定模板「OAI 對齊」:值 = DU 目前對齊 OAI rfsim(band78、106 PRB、TDD DDDDDDDSUU、min_rbSize 5、discard 300 ms、HARQ 4)
- 天線 preset「1×1 iso(OAI rfsim)」
- gNB 模板「OAI 對齊預設」:PLMN 208/95、A3 關(offset 1 / hys 0.5 / TTT 80,CU 預設)、n78 3.5 GHz 40 MHz 23 dBm,綁上面兩個。"""
from django.core.management.base import BaseCommand

from main.apps.preset_catalog.models.antenna_preset import AntennaPreset
from main.apps.preset_catalog.models.du_config_template import DuConfigTemplate
from main.apps.preset_catalog.models.gnb_config_template import GnbConfigTemplate
from main.apps.preset_catalog.services.common.timestamp_service import TimestampService
from main.apps.preset_catalog.services.common.uuid_service import UUIDService


def _get_or_create(model, prefix: str, name: str, defaults: dict):
    obj = model.objects.filter(name=name).first()
    if obj:
        return obj, False
    now = TimestampService.get_current_timestamp()
    obj = model.objects.create(**{f"{prefix}_uuid": UUIDService.generate_uuid(prefix), f"{prefix}_created_at": now, f"{prefix}_updated_at": now, "name": name, **defaults})
    return obj, True


class Command(BaseCommand):
    help = "建立 OAI 對齊的預設 DU 模板 / 天線 preset / gNB 模板(冪等)"

    def handle(self, *args, **opts):
        du, c1 = _get_or_create(DuConfigTemplate, "du_config_template", "OAI 對齊", dict(tdd_pattern="DDDDDDDSUU", numerology=1, n_prb=106, min_prb=5, pf_alpha=0.05, target_bler=0.1, rlc_discard_timer_ms=300, rlc_tx_maxsize_bytes=10_000_000, harq_max_retx=4, qos_gbr_first=True, gbr_max_share=0.3))
        ant, c2 = _get_or_create(AntennaPreset, "antenna_preset", "1×1 iso(OAI rfsim)", dict(source="oai", pattern="iso", rows=1, cols=1, polarization="V", v_spacing=0.5, h_spacing=0.5, polarization_model="tr38901_2", max_gain_dbi=0.0, notes="OAI rfsim 單天線;Physics 目前以此為準"))
        gnb, c3 = _get_or_create(GnbConfigTemplate, "gnb_config_template", "OAI 對齊預設", dict(source="oai", notes="值來自 DU/CU 對齊 OAI rfsim band78 106 PRB 的設定;A3 預設關(CU HO_A3_ENABLED=off)", plmn_mcc="208", plmn_mnc="95", a3_enabled=False, a3_offset_db=1.0, a3_hys_db=0.5, a3_ttt_ms=80, band="n78", center_frequency_ghz=3.5, bandwidth_mhz=40.0, power_dbm=23.0, tilt_deg=0.0, cells_per_gnb=1, azimuth_step_deg=120.0, du_config_template=du, antenna_preset=ant))
        self.stdout.write(f"du_template {'created' if c1 else 'exists'} · antenna {'created' if c2 else 'exists'} · gnb_template {'created' if c3 else 'exists'} ({gnb.gnb_config_template_uuid})")
