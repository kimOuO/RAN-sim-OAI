"""son_action_log — CU 自主(非 RIC 觸發)的組態變更稽核。

為什麼要單獨一張表:外部 Agent 的介面 I-7 要能分辨「對方注入的事件」與
「我方系統的自主行為」。RunControlEvent 的來源全是 E2Adapter 的稽核列,
也就是 RIC / xApp 下來的;自主 ANR 直接改 NrCellRelation 然後只寫 log,
在對外資料裡完全隱形 —— 對方刻意留空的鄰區關係被我方自動補上,
正確答案就被破壞了而且查不出來。

一個 table 一個檔案(backend_rule §5-1)。
"""
from django.db import models


class SonActionLog(models.Model):
    id = models.AutoField(primary_key=True)
    # 變更的對象:cell / neighbour_relation / xn_link(對齊 I-7 的 object_type)
    object_type = models.CharField(max_length=32)
    object_id = models.CharField(max_length=160, db_index=True)
    # 動作與被改的屬性;before/after 存字串化的值(型別不一,JSON 欄位過重)
    action = models.CharField(max_length=32)          # add / remove / set
    attribute = models.CharField(max_length=64, blank=True, default="")
    before = models.CharField(max_length=128, blank=True, default="")
    after = models.CharField(max_length=128, blank=True, default="")
    # 哪一個自主功能做的(anr_auto / es / cco …),對應 I-7 的 origin=son_function
    function = models.CharField(max_length=32, default="anr_auto")
    reason = models.CharField(max_length=200, blank=True, default="")
    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_son_action_log"
        ordering = ("id",)
