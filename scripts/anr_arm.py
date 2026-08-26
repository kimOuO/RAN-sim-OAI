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
    """改既有關係的屬性;關係不存在就先建。

    ⚠️ 為什麼要 create-if-missing:seed_from_cells() **只種同 gNB 內**的鄰區
    (`if tgt.gnb_id != src.gnb_id: continue`),而 ANR 劇本每個 gNB 只有一個
    cell → 基準 NRT 恆為空。第 6/10/12 題要改「既有關係」的屬性,若不先建
    就永遠改不到(2026-08-24 十二題健康檢查踩到:三題同時因此失敗)。
    真實網路裡這些關係是 ANR 自動建立或 OAM 佈的,這裡等價於「已經有這條關係」。
    """
    if not R.objects.filter(source_cell_id=src, target_cgi=dst).exists():
        print(f"  (關係 {src}→{dst} 不存在,先建 —— 基準 NRT 為空是預期的)")
        _mk(src, dst)
    n = R.objects.filter(source_cell_id=src, target_cgi=dst).update(updated_at=timezone.now(), **kw)
    print(f"  set {src}→{dst} {kw}  (rows={n})")


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
    # UE 搬回 s25 —— 佈病前 RLF 重建已把 UE 帶去 n37(坑 2:重建不看 NRT),
    # 來源歸屬不在 s25 的話,guard 會替 n37 建關係,考點的 s25→n35 缺漏驗不到。
    from main.apps.cu_cp.models.ue_context import UeContext as _U
    from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
    moved = sum(1 for u in _U.objects.filter(ue_id__startswith="mm").exclude(serving_cell="s25_c0")
                if execute_f1_handover(ue_id=u.ue_id, target_cell="s25_c0", trigger="MANUAL"))
    print(f"  已把 {moved} 台 UE 搬回 s25_c0")
    print("  ※ 停用分支:改 docker-compose ANR_INTRA_ENABLED=false 後 docker compose up -d ransim-cu")

def q3():
    """深邊緣稀疏"""
    _cut("s28_c0", "n91_c0")
    from main.apps.cu_cp.models.ue_context import UeContext as _U
    from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
    moved = sum(1 for u in _U.objects.filter(ue_id__startswith="dw").exclude(serving_cell="s28_c0")
                if execute_f1_handover(ue_id=u.ue_id, target_cell="s28_c0", trigger="MANUAL"))
    print(f"  已把 {moved} 台 UE 搬回 s28_c0(坑1)")

def q4():
    """未知 cell"""
    _cut("s01_c0", "unk_c0")

def q5():
    """PCI 撞號 —— 病在場景本身(west_c7 / east_c7 同 pci=7)。

    v10 自動鏈(RIC 第二十九輪)加了消歧前提:來源 cell(mid_c0)的 NRT
    必須**只含其中一顆**(owned 唯一)→ xApp 才敢下群組換手。
    佈病:確保 mid→east_c7 在、mid→west_c7 不在;UE 搬回 mid_c0(坑1)。"""
    dup = [c.cell_id for c in CellConfig.objects.filter(pci=7)]
    print(f"  pci=7 的 cell:{dup}  {'✓ 撞號成立' if len(dup) > 1 else '✗ 劇本沒起來?'}")
    _mk("mid_c0", "east_c7")                       # owned 唯一
    n = R.objects.filter(source_cell_id="mid_c0", target_cgi="west_c7").delete()[0]
    print(f"  NRT:mid→east_c7 確保存在;mid→west_c7 刪除 {n} 筆(owned 唯一成立)")
    from main.apps.cu_cp.models.ue_context import UeContext as _U
    from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
    moved = sum(1 for u in _U.objects.filter(ue_id__startswith="cf").exclude(serving_cell="mid_c0")
                if execute_f1_handover(ue_id=u.ue_id, target_cell="mid_c0", trigger="MANUAL"))
    print(f"  已把 {moved} 台 UE 搬回 mid_c0")

def q6():
    """Xn-C 探索失敗:關係在、Xn 不在 → TXnRELOCprepExpiry。

    v10 正解改了:不再是「不動手只通報」,而是 set xnBlocklist 禁用換手路徑
    (TS 28.313 §6.4.1.3.7,不拆線),Xn 恢復後 clear。
    佈病時必須確保 xnBlocklist 是關的 —— 否則病一開始就被治好了。
    """
    _set("s07_c0", "n33_c0", xn_x2_established=False, xn_blocklist=False)
    # 坑1:佈病前 UE 已被換/駐留到 n33(barred 擋重建不擋既有駐留)→ 搬回 s07
    from main.apps.cu_cp.models.ue_context import UeContext as _U
    from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
    moved = sum(1 for u in _U.objects.filter(ue_id__startswith="xd").exclude(serving_cell="s07_c0")
                if execute_f1_handover(ue_id=u.ue_id, target_cell="s07_c0", trigger="MANUAL"))
    print(f"  已把 {moved} 台 UE 搬回 s07_c0")
    print("  ※ v10 正解:xApp 應 set xnBlocklist;恢復用 CASE=q6_restore")


def q6_restore():
    """Xn 修復(管理面完成)—— 驗 xApp 會不會把 xnBlocklist 清掉。"""
    _set("s07_c0", "n33_c0", xn_x2_established=True)
    print("  ※ Xn 已恢復,xApp 應 clear xnBlocklist")

def q7():
    """有害鄰居:關係要「在」,但換過去一律失敗。

    前提是關係存在 —— 基準 NRT 為空(seeder 只種同 gNB 內),所以要先建;
    原本這裡只做檢查不建立,導致第7題永遠卡在「關係不在」(2026-08-24 檢查踩到)。
    """
    r = _mk("src_c0", "nbr_c0", ho_blocklist=False, no_remove=False)  # 病要能發作
    print(f"  src_c0→nbr_c0 ho_blocklist={r.ho_blocklist} no_remove={r.no_remove} v={r.version}")
    print("  ※ v10 正解為**成對**:hoBlocklist + noRemove 一起 set")
    print("     (TS 28.313 §6.4.1.3.5 Step 2 本即複合動作;只 set 一個算不完整)")
    print("  ※ 必要 env:HO_FORCE_FAIL_TARGET=nbr_c0(改完 docker compose up -d ransim-cu)")

def q8():
    """跨頻:砍掉 3.5G→2.1G 整層關係;UE 搬回 s11(坑1,壅塞與歸屬都要在 s11)"""
    for t in ("f55_c0", "f61_c0", "f68_c0"):
        _cut("s11_c0", t)
    from main.apps.cu_cp.models.ue_context import UeContext as _U
    from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
    moved = sum(1 for u in _U.objects.filter(ue_id__startswith="if").exclude(serving_cell="s11_c0")
                if execute_f1_handover(ue_id=u.ue_id, target_cell="s11_c0", trigger="MANUAL"))
    print(f"  已把 {moved} 台 UE 搬回 s11_c0")

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
    _set("s15_c0", "b07_c0")          # 先確保關係存在(值會照 cell 實際 pci)
    _set("s15_c0", "b07_c0", target_pci=205)   # 再改成過期的舊 PCI

    # UE 搬回 s15 —— sim 是先跑再佈病,A3 已趁 PCI 還正確時把 UE 全換去 b07;
    # 病是「s15 往 b07 的換手因舊 PCI 失敗」,UE 不在 s15 病就不發作
    # (2026-08-25 佈第 10 題 fixture 時踩到:att=0、失敗全空)。
    # 搬回後 A3 會再嘗試 → 撞 stale PCI → CellNotAvailable,失敗不改 serving,
    # UE 留在 s15 反覆嘗試 → 失敗率持續 —— 這正是卷面要的樣貌。
    from main.apps.cu_cp.models.ue_context import UeContext as _U
    from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
    moved = sum(1 for u in _U.objects.filter(serving_cell="b07_c0")
                if execute_f1_handover(ue_id=u.ue_id, target_cell="s15_c0", trigger="MANUAL"))
    print(f"  已把 {moved} 台 UE 搬回 s15_c0(A3 將反覆撞 stale PCI)")
    c = CellConfig.objects.filter(cell_id="b07_c0").first()
    print(f"  b07_c0 實際 pci={getattr(c, 'pci', None)}(應為 233)→ 對應過期成立")

def q11():
    """臨時節點生命週期(v10)—— 進場要建、離場雙歸零要回收。

    v10 把觸發背景定為「臨時節點」,並要求組態面(CCC 新實例)與量測面
    (從無到有的樣本)互證。這裡把 tmp_c0 的 created_at 推成「剛剛」,
    讓 cccConfigurationEvents 有真的誕生事件 —— 而不是靠劇本重啟時
    所有 cell 都落在回看窗內的假訊號(那分不出誰才是新來的)。
    """
    # 老化零活動 + 受保護條目(回收段的判斷對象與保護對象)
    # RIC 第三十二輪 v10 判準:雙歸零(meas+att 同 0 持續 300s)→ REMOVE。
    # old_c0(ghost)標 protected:驗 REMOVE→REJECTED_PROTECTED→SMO 不重試。
    _mk("main_c0", "old_c0", pci=940, no_remove=True); _age("main_c0", "old_c0", 30)
    _mk("main_c0", "keep_c0", no_remove=True)
    # 殭屍本體:main→tmp_c0 存在且雙零(tmp 在 (0,260) UE 走廊外,天然無量測)
    _mk("main_c0", "tmp_c0")
    print("  殭屍 main_c0→tmp_c0 已建(雙零候選);main_c0→old_c0 標 protected(拒絕路徑)")

    # 臨時節點:標成剛誕生,並刪掉指向它的關係讓 ANR 必須重新發現
    tmp = CellConfig.objects.filter(cell_id="tmp_c0").first()
    if tmp is None:
        print("  ⚠️ 場景沒有 tmp_c0 —— 請確認跑的是更新後的 anr_stale_relation 劇本")
    else:
        CellConfig.objects.filter(cell_id="tmp_c0").update(created_at=timezone.now())
        print("  tmp_c0 標記為剛誕生(CCC 事件)")
    print("  ※ 回收段判準為**雙歸零**(measSampleRatePerMin 與 att 同步為 0),不是年齡")

def q12():
    """屬性稽核 —— v10 改為「修復」:清掉無依據的封鎖,正當封鎖不得碰。

    要造出兩條**外觀相同、來歷不同**的封鎖,差別只在行為訊號:
      d02_c0  無依據封鎖:量測強、換手嘗試 0、hoValidated=false、無失敗史 → 該修
      n80_c0  正當封鎖  :量測弱、hoValidated=true、有大量接取失敗史   → 不得碰
    v10 明訂旗標非 E2 可觀測,所以 xApp 只能靠上面四項行為訊號分辨 ——
    這正是本題的考點,佈病時兩條的旗標必須一模一樣。
    """
    from datetime import timedelta
    from main.apps.cu_cp.models.handover_event import HandoverEvent
    from main.apps.cu_cp.services.common.uuid_service import UUIDService

    _set("s19_c0", "d02_c0", ho_blocklist=True, xn_blocklist=True,
         ho_validated=False)                      # 從未成功服務過 → 封鎖無依據
    _set("s19_c0", "n80_c0", ho_blocklist=True, xn_blocklist=True,
         ho_validated=True)                       # 曾正常服務,後因劣化被封

    # n80 的失敗史 —— 「因失敗而封」的證據;d02 刻意一筆都沒有
    now = timezone.now()
    have = HandoverEvent.objects.filter(source_cell="s19_c0", target_cell="n80_c0").count()
    mk = 0
    for i in range(max(0, 40 - have)):
        HandoverEvent.objects.create(
            ho_uuid=UUIDService.random_uuid(), ue_id=f"hist{i%5}",
            source_cell="s19_c0", target_cell="n80_c0", trigger="A3_TTT",
            status="FAIL", failure_cause="RandomAccessProblem",
            started_at=now - timedelta(hours=6, minutes=i),
            completed_at=now - timedelta(hours=6, minutes=i))
        mk += 1
    print(f"  n80_c0 失敗史 +{mk} 筆(共 {have + mk});d02_c0 失敗史 0 筆 ← 鑑別點")

    # UE 必須駐留 s19_c0 —— 真實情境裡 UE 之所以沒過去 d02,正是因為它從一開始
    # 就被封鎖;但 sim 是先跑再佈病,A3 早把 UE 全搬到 d02 了。
    # 不搬回來的話 s19 的 att=0 有「根本沒人用」的良性解釋,
    # 「強訊號而零嘗試」的矛盾就不成立(RIC 2026-08-25 指出)。
    from main.apps.cu_cp.models.ue_context import UeContext as _U
    from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
    moved = 0
    for u in _U.objects.filter(serving_cell="d02_c0"):
        if execute_f1_handover(ue_id=u.ue_id, target_cell="s19_c0", trigger="MANUAL"):
            moved += 1
    print(f"  已把 {moved} 台 UE 搬回 s19_c0(封鎖後 A3 不會再把它們拉走)")
    print("  ※ v10 正解:clear d02 的 hoBlocklist/xnBlocklist;n80 維持不動")


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
CASES["q6_restore"] = q6_restore

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
