"""ANR 十二題「佈病」腳本 —— 把劇本跑起來後的前置條件一次布好。

用法(在 host):
    CASE=q1  docker exec -i -e CASE=q1  ransim-cu python manage.py shell < scripts/anr_arm.py
    CASE=all docker exec -i -e CASE=all ransim-cu python manage.py shell < scripts/anr_arm.py   # 只印狀態
    CASE=reset ...                                                                             # 清病回健康

前提:對應劇本已 Start(CellConfig / NrCellRelation 已由 seeder 種好)。
每題的病因、指標、正解、驗收見 docs/anr_validation/12題劇本規格.md。

⚠️ 有兩題的病布在 env 不在 DB(腳本會提醒但不能代勞,改 env 要 docker compose up -d):
    Q7  HO_FORCE_FAIL_TARGET=nbr_c0
    Q2(停用分支) ANR_INTRA_ENABLED=false
"""
import os

from django.utils import timezone

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as R
from main.apps.cu_cp.services.business.anr_seeder import nr_arfcn_from_ghz

CASE = (os.environ.get("CASE") or "").lower().strip()


def _cut(src, dst):
    """刪雙向關係 —— 缺漏鄰區型的病因。"""
    n = R.objects.filter(source_cell_id=src, target_cgi=dst).delete()[0]
    n += R.objects.filter(source_cell_id=dst, target_cgi=src).delete()[0]
    print(f"  cut {src} ↔ {dst}: 刪 {n} 筆")


def _mk(src, dst, pci=None, arfcn=None, **kw):
    """補一筆關係(容量填充 / 保護條目用)。"""
    c = CellConfig.objects.filter(cell_id=dst).first()
    now = timezone.now()
    defaults = dict(
        target_pci=pci if pci is not None else (c.pci if c else 0),
        target_arfcn=arfcn if arfcn is not None else (nr_arfcn_from_ghz(c.frequency_ghz) if c else 633333),
        target_rat="NR", xn_x2_established=True, created_at=now, updated_at=now, **kw)
    r, created = R.objects.get_or_create(source_cell_id=src, target_cgi=dst, defaults=defaults)
    if not created:
        for k, v in defaults.items():
            if k not in ("created_at",):
                setattr(r, k, v)
        r.save()
    print(f"  {'建' if created else '改'} {src}→{dst} pci={r.target_pci} "
          f"noRemove={r.no_remove} xn={r.xn_x2_established}")
    return r


def _set(src, dst, **kw):
    n = R.objects.filter(source_cell_id=src, target_cgi=dst).update(updated_at=timezone.now(), **kw)
    print(f"  set {src}→{dst} {kw}  (rows={n})")
    if n == 0:
        print(f"  ⚠️ 找不到關係 {src}→{dst} —— 劇本起來了嗎?seeder 種過了嗎?")


def _age(src, dst, days=30):
    """把 created_at 往前推,做出 relationAgeSec 很大的老化關係。"""
    old = timezone.now() - timezone.timedelta(days=days)
    n = R.objects.filter(source_cell_id=src, target_cgi=dst).update(created_at=old)
    print(f"  age {src}→{dst} → {days} 天前 (rows={n})")


# ── 各題佈病 ────────────────────────────────────────────────
def q1():
    """缺漏鄰區(重建統計反推)"""
    _cut("src_c0", "nbr_c0")

def q2():
    """缺漏鄰區(量測側偵測)。停用分支另需 env ANR_INTRA_ENABLED=false。"""
    _cut("s25_c0", "n35_c0")
    print("  ※ 停用分支:改 docker-compose ANR_INTRA_ENABLED=false 後 docker compose up -d ransim-cu")

def q3():
    """深邊緣稀疏"""
    _cut("s28_c0", "n91_c0")

def q4():
    """未知 cell"""
    _cut("s01_c0", "unk_c0")

def q5():
    """PCI 撞號 —— 病在場景本身(west_c7 / east_c7 同 pci=7),DB 不用動。"""
    dup = [c.cell_id for c in CellConfig.objects.filter(pci=7)]
    print(f"  pci=7 的 cell:{dup}  {'✓ 撞號成立' if len(dup) > 1 else '✗ 劇本沒起來?'}")

def q6():
    """Xn-C 探索失敗:關係在、Xn 不在 → TXnRELOCprepExpiry"""
    _set("s07_c0", "n33_c0", xn_x2_established=False)

def q7():
    """有害鄰居 —— 病在 env,DB 只確認關係健在。"""
    r = R.objects.filter(source_cell_id="src_c0", target_cgi="nbr_c0").first()
    print(f"  src_c0→nbr_c0 {'存在' if r else '不存在(要先 ADD)'};"
          f" ho_blocklist={getattr(r, 'ho_blocklist', None)}")
    print("  ※ 必要 env:HO_FORCE_FAIL_TARGET=nbr_c0(改完 docker compose up -d ransim-cu)")

def q8():
    """跨頻:砍掉 3.5G→2.1G 整層關係"""
    for t in ("f55_c0", "f61_c0", "f68_c0"):
        _cut("s11_c0", t)

def q9():
    """NRT 容量修剪:把三個 cell 填到 used==limit,含零活動 x24_c0 與受保護 x25_c0"""
    from main.utils.env_loader import get_int
    limit = get_int("ANR_NRT_CAPACITY", 32)
    for src in ("n60_c0", "n61_c0", "n62_c0"):
        _cut(src, "n77_c0")
        _mk(src, "x24_c0", pci=924)                    # 零活動 → 修剪候選
        _mk(src, "x25_c0", pci=925, no_remove=True)    # 受保護 → REMOVE 必須被拒
        cur = R.objects.filter(source_cell_id=src).count()
        i = 0
        while cur < limit:                              # 填到滿
            i += 1
            _mk(src, f"pad{i:02d}_c0", pci=900 + i)
            cur += 1
        while cur > limit:                              # 超了就砍 pad
            p = R.objects.filter(source_cell_id=src, target_cgi__startswith="pad").first()
            if not p:
                break
            p.delete(); cur -= 1
        print(f"  {src}: used={cur}/{limit} {'✓' if cur == limit else '✗'}")

def q10():
    """過期 PCI 對應:關係留舊 pci=205,cell 實際 233"""
    _set("s15_c0", "b07_c0", target_pci=205)
    c = CellConfig.objects.filter(cell_id="b07_c0").first()
    print(f"  b07_c0 實際 pci={getattr(c, 'pci', None)}(應為 233)→ 對應過期成立")

def q11():
    """老化 / 自動刪除:一筆老化零活動 + 一筆受保護"""
    _mk("main_c0", "old_c0", pci=940); _age("main_c0", "old_c0", 30)
    _mk("main_c0", "keep_c0", no_remove=True)

def q12():
    """屬性稽核:一筆屬性看似異常但有正當理由的關係"""
    _set("s19_c0", "d02_c0", is_ho_allowed=False)
    print("  ※ 正解是「不動手」—— 此屬性有正當來源,xApp 改它就是誤判")


def reset():
    """清病:全部關係回健康預設(不刪 cell)。"""
    n = R.objects.all().update(
        xn_x2_established=True, is_ho_allowed=True, is_remove_allowed=True,
        is_xn_allowed=True, ho_blocklist=False, no_remove=False,
        xn_blocklist=False, updated_at=timezone.now())
    d = R.objects.filter(target_cgi__startswith="pad").delete()[0]
    d += R.objects.filter(target_cgi__in=["x24_c0", "x25_c0", "old_c0"]).delete()[0]
    print(f"  關係回健康:{n} 筆;刪合成關係 {d} 筆")
    print("  ※ 被刪掉的真實關係不會自己回來 —— 重跑劇本或呼叫 /Anr/reseed")


def status():
    print(f"  cells      : {CellConfig.objects.count()}")
    print(f"  relations  : {R.objects.count()}")
    print(f"  xn=False   : {R.objects.filter(xn_x2_established=False).count()}")
    print(f"  blocklisted: {R.objects.filter(ho_blocklist=True).count()}")
    print(f"  noRemove   : {R.objects.filter(no_remove=True).count()}")
    for r in R.objects.all().order_by("source_cell_id", "target_cgi"):
        print(f"    {r.source_cell_id:10s}→{r.target_cgi:10s} pci={r.target_pci:>4} "
              f"v={r.version} ho={r.is_ho_allowed} xn={r.xn_x2_established} "
              f"blk={r.ho_blocklist} keep={r.no_remove}")


CASES = {f"q{i}": fn for i, fn in enumerate(
    [q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, q11, q12], start=1)}

print(f"=== ANR arm: CASE={CASE or '(未給)'} ===")
if CASE in CASES:
    print(CASES[CASE].__doc__)
    CASES[CASE]()
    print("--- 佈病後狀態 ---"); status()
elif CASE == "reset":
    reset(); status()
elif CASE in ("all", "status", ""):
    if CASE in ("all", ""):
        print("可用:", " ".join(CASES), "reset status")
    status()
else:
    print(f"未知 CASE={CASE};可用:{' '.join(CASES)} reset status")
