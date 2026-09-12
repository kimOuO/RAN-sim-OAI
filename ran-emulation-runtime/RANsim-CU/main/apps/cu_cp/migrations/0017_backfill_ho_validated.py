"""回填 hoValidated(RIC 第三十七輪第二項第 4 點)。

hoValidated 此前從未被寫成 True —— 既有關係即使有 50 筆 100% 成功的換手史,
欄位仍是 false,第 12 題的鑑別線因此是死的。executor 已改為成功換手即標記,
但既有條目要等下一次換手才會翻(att=0 的關係可能等很久),故一次回填。

規則同 executor:單向、只認非 MANUAL 的成功換手(MANUAL 是佈病腳本搬移)。
"""
from django.db import migrations


def backfill(apps, schema_editor):
    NrCellRelation = apps.get_model("cu_cp", "NrCellRelation")
    HandoverEvent = apps.get_model("cu_cp", "HandoverEvent")
    n = 0
    for rel in NrCellRelation.objects.filter(ho_validated=False):
        if HandoverEvent.objects.filter(
            source_cell=rel.source_cell_id, target_cell=rel.target_cgi,
            status="SUCC",
        ).exclude(trigger="MANUAL").exists():
            rel.ho_validated = True
            rel.save(update_fields=["ho_validated"])
            n += 1
    if n:
        print(f"  backfilled hoValidated=True on {n} relations")


def noop(apps, schema_editor):
    """不還原 —— hoValidated 是歷史事實,回退不該把它抹掉。"""


class Migration(migrations.Migration):
    dependencies = [("cu_cp", "0016_e2subscription")]
    operations = [migrations.RunPython(backfill, noop)]
