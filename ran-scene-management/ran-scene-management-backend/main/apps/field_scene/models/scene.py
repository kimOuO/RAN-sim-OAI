"""scene — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Scene(models.Model):
    id = models.AutoField(primary_key=True)
    scene_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default='')
    origin_lat = models.FloatField(null=True, blank=True)
    origin_lon = models.FloatField(null=True, blank=True)
    bounds = models.JSONField(null=True, blank=True)
    # 劇本匯入相容:原 scenario_id(往返用)、原 scene_id(Physics/Omniverse 幾何場景預設名)、geometry_source(倉庫版劇本)
    legacy_scenario_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    geometry_scene_id = models.CharField(max_length=128, blank=True, default="")
    geometry_source = models.JSONField(null=True, blank=True)
    ground_material = models.ForeignKey("field_scene.Material", on_delete=models.PROTECT, to_field="material_uuid", db_column="f_material_uuid", related_name="scenes", db_index=True, null=True, blank=True)
    # run 層級天線(Sionna 的 tx_array / rx_array 是 scene-global,一個 run 只能一組;P5-Q2 2026-09-13)
    # None → gNB 取第一個 cell 的 RU preset、UE 取第一個 UE 的 preset(舊行為),都沒有就 1×1。
    gnb_antenna_preset = models.ForeignKey("equipment_preset.AntennaPreset", on_delete=models.SET_NULL, to_field="antenna_preset_uuid", db_column="f_gnb_antenna_preset_uuid", related_name="scenes_as_gnb", null=True, blank=True)
    ue_antenna_preset = models.ForeignKey("equipment_preset.AntennaPreset", on_delete=models.SET_NULL, to_field="antenna_preset_uuid", db_column="f_ue_antenna_preset_uuid", related_name="scenes_as_ue", null=True, blank=True)
    # E2 區塊(2026-09-27 多 gNB 改版,取代 2026-09-22 的單一槽位 e2_slot)。
    # 一場的每個 gNB 各是一個 E2 node:第 i 個 gNB(Gnb.e2_index)的槽位 = 16·e2_block + i,
    # gNB ID = 0x000e00 | 槽位,meid = gnb_208_095_000eXY(X = 區塊、Y = gNB 序號)。
    # 釘住區塊 → 每個 gNB 的 meid 與每個 cell 的 NCI 在啟動前就確定,外部 Agent 才能事先部署 xApp;
    # 代價是同一場域同時只能跑一場。null = 啟動時動態配區塊。
    # 範圍 1–15:區塊 0(e00)保留給 RIC 常駐 xApp;≥ 16 時 0xe00|0x100 進位成 0xf00,命名不一致。
    # 規格見 docs/architecture/multi_gnb_plan.md D3。
    e2_block = models.IntegerField(null=True, blank=True, unique=True,
                                   validators=[MinValueValidator(1), MaxValueValidator(15)])
    # 2026-09-22:場景分類(corridor / anr / intent / scale / other)。
    # 以前分類是前端用名字前綴猜的,外部 Agent 的 I-1 拿不到;改成資料。
    # null = 未宣告 → 前端與 I-1 退回前綴規則,既有場景顯示不變。
    category = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    scene_created_at = models.DateTimeField()
    scene_updated_at = models.DateTimeField()

    class Meta:
        app_label = "field_scene"
        db_table = "scene_layout_scene"
        ordering = ("id",)
