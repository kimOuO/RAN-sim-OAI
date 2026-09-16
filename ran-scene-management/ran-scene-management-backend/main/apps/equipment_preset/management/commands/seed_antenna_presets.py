"""seed_antenna_presets — 建立內建天線 preset(冪等)。

三層模型見 new_plan/ru_antenna_mimo_plan.md §3.1b:
    元件層 (Mg,Ng,M,N,P)  ──virtualization──▶  TRX 層  ──埠映射──▶  埠層 (N1,N2)
    TR 38.901 §7.3            TR 38.901 式 (7.3-1)          TS 38.214 §5.2.2.2.1

rows/cols = 單面板元件排列 (M, N);trx_v_group = 每個 TXRU 垂直帶幾片同極化元件。
元件圖樣一律 TR 38.901 Table 7.3-1(65°/65° HPBW、SLA_V = A_max = 30 dB、G_E,max = 8 dBi)。
"""
from django.core.management.base import BaseCommand

from main.apps.equipment_preset.models.antenna_preset import AntennaPreset
from main.apps.equipment_preset.services.common.timestamp_service import TimestampService
from main.apps.equipment_preset.services.common.uuid_service import UUIDService

# (name, source, pattern, rows, cols, pol, v_sp, h_sp, gain, mg, ng, trx_vg, trx, etilt, ports, n1, n2, cat, bf, gob_az, gob_el, notes)
PRESETS: list[tuple] = [
    ("1×1 iso(OAI rfsim)", "oai", "iso", 1, 1, "V", 0.5, 0.5, 0.0, 1, 1, 1, 1, 0.0, 1, 1, 1, "A", "", 0, 0,
     "OAI rfsim 對齊:單元件單埠。"),
    ("38.901 大尺度校準(10×1 單極化)", "3gpp", "tr38901", 10, 1, "V", 0.5, 0.5, 8.0, 1, 1, 10, 1, 0.0, 1, 1, 1, "A", "", 0, 0,
     "TR 38.901 §7.8.1 Table 7.8-1:Mg=Ng=1、(M,N,P)=(10,1,1)、dV=0.5λ。10 片元件虛擬化成 1 埠,校準基準。"),
    ("38.901 完整校準 Config 1(雙面板 4×4 雙極化)", "3gpp", "tr38901", 4, 4, "cross", 0.5, 0.5, 8.0, 1, 2, 4, 2, 0.0, 2, 1, 1, "A", "", 0, 0,
     "TR 38.901 §7.8.2 Config 1:(M,N,P)=(4,4,2)、Mg=1、Ng=2、dH=dV=0.5λ、面板間距 2.5λ;每面板每極化 16 元件映射到 1 埠。"),
    ("2T2R 小站", "3gpp", "tr38901", 1, 1, "cross", 0.5, 0.5, 8.0, 1, 1, 1, 2, 0.0, 2, 1, 1, "A", "", 0, 0,
     "TS 38.104 BS type 1-C 典型:單元件雙極化 = 2 埠。"),
    ("4T4R", "3gpp", "tr38901", 2, 1, "cross", 0.5, 0.5, 8.0, 1, 1, 1, 4, 0.0, 4, 2, 1, "A", "", 0, 0,
     "TS 38.214 Table 5.2.2.2.1-2:4 埠 (N1,N2)=(2,1)。2026-09-15 已實測 rank 2。"),
    ("8T8R", "3gpp", "tr38901", 2, 2, "cross", 0.5, 0.5, 8.0, 1, 1, 1, 8, 0.0, 8, 2, 2, "A", "", 0, 0,
     "TS 38.214:8 埠 (N1,N2)=(2,2)。Cat A 典型上限。"),
    ("16T16R", "3gpp", "tr38901", 4, 2, "cross", 0.8, 0.5, 8.0, 1, 1, 1, 16, 0.0, 16, 4, 2, "B", "predefined", 8, 2,
     "TS 38.214:16 埠 (N1,N2)=(4,2);進入 O-RAN Cat B。"),
    ("32T32R mMIMO", "3gpp", "tr38901", 8, 8, "cross", 0.8, 0.5, 8.0, 1, 1, 4, 32, 6.0, 32, 8, 2, "B", "predefined", 16, 4,
     "128 元件(8×8 雙極化),每 TXRU 垂直帶 4 片 → 32 TRX;32 埠 (N1,N2)=(8,2)。中頻 mMIMO。"),
    ("64T64R mMIMO", "3gpp", "tr38901", 12, 8, "cross", 0.8, 0.5, 8.0, 1, 1, 3, 64, 6.0, 32, 8, 2, "B", "predefined", 16, 4,
     "192 元件(12×8 雙極化),每 TXRU 垂直帶 3 片 → 64 TRX;再虛擬化成 32 埠 (8,2)。O-RAN WG1 §4.21 節能例的 64→32 通道即此型。"),
    ("UE 1 埠 iso", "3gpp", "iso", 1, 1, "V", 0.5, 0.5, 0.0, 1, 1, 1, 1, 0.0, 1, 1, 1, "A", "", 0, 0, "UE 單埠。"),
    ("UE 2 埠 cross iso", "3gpp", "iso", 1, 1, "cross", 0.5, 0.5, 0.0, 1, 1, 1, 2, 0.0, 2, 1, 1, "A", "", 0, 0,
     "UE 單元件雙極化 = 2 埠(TS 38.211 SRS 1/2/4 埠)。"),
    ("UE 4 埠 cross iso", "3gpp", "iso", 1, 2, "cross", 0.5, 0.5, 0.0, 1, 1, 1, 4, 0.0, 4, 2, 1, "A", "", 0, 0, "UE 1×2 雙極化 = 4 埠。"),
]

_FIELDS = ("source", "pattern", "rows", "cols", "polarization", "v_spacing", "h_spacing", "max_gain_dbi",
           "panels_mg", "panels_ng", "trx_v_group", "trx_count", "electrical_tilt_deg", "csi_ports",
           "port_n1", "port_n2", "ru_category", "bf_method", "gob_az_beams", "gob_el_beams", "notes")


class Command(BaseCommand):
    help = "建立 / 更新內建天線 preset(1×1 到 64T64R,含 38.901 校準組態)"

    def add_arguments(self, parser):
        parser.add_argument("--update", action="store_true", help="同名已存在時也覆寫欄位(預設只補建缺的)")

    def handle(self, *args, **opts):
        now = TimestampService.get_current_timestamp()
        created = updated = skipped = 0
        for row in PRESETS:
            name, rest = row[0], row[1:]
            defaults = dict(zip(_FIELDS, rest))
            # 面板間距只有多面板才有意義(38.901 Config 1 = 2.5λ)
            if defaults["panels_ng"] > 1 or defaults["panels_mg"] > 1:
                defaults["panel_v_spacing"] = defaults["panel_h_spacing"] = 2.5
            obj = AntennaPreset.objects.filter(name=name).first()
            if obj is None:
                AntennaPreset.objects.create(antenna_preset_uuid=UUIDService.generate_uuid("antenna_preset"),
                                             antenna_preset_created_at=now, antenna_preset_updated_at=now,
                                             name=name, **defaults)
                created += 1
            elif opts["update"]:
                for k, v in defaults.items():
                    setattr(obj, k, v)
                obj.antenna_preset_updated_at = now
                obj.save()
                updated += 1
            else:
                skipped += 1
        self.stdout.write(f"antenna presets: created={created} updated={updated} skipped={skipped} total={AntennaPreset.objects.count()}")
