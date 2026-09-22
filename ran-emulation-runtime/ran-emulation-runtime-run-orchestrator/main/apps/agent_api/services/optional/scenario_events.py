"""情境事件(介面 I-3 的 events[])—— 型別定義、驗證與執行。

對方用這些事件出考題:在第 N 秒關掉某顆 cell、改發射功率、刪掉一條鄰區關係,
然後看 xApp 能不能診斷出來。所以每個事件都必須:
  (1) 真的改到模擬的行為,不能是只記一筆 log 的空動作;
  (2) 準時 —— 以**劇本時鐘**為準(不是牆鐘),倍速下才對得上對方的 at_offset_s;
  (3) 留下可查的紀錄 —— 落 RunControlEvent,對方由 I-7 取回核對。

哪些做得到、哪些做不到,取決於通道快取:

    cell_outage / energy_saving_state  ✅ 任何模式
        DU 的 is_active,tick 直接跳過該 cell。與 PEE.cellAvailablePer 同一個機制。

    tx_power_change                    ✅ 任何模式
        發射功率是在 RU 執行期疊到快取的 path gain 上的(不在快取裡),所以改得動。

    relation_change                    ✅ 任何模式
        CU 的 NrCellRelation,本來就是執行期資料。

    cell_addition                      ⚠ 僅限快取已含該 cell
        新 cell 要有 path gain 才算得出 RSRP。快取是預算時就按 cell 清單算死的,
        中途冒出來的 cell 沒有任何通道資料。所以只支援「預算時已納入、但初始
        is_active=False 的備用 cell」—— 把它打開就等於新增。場域沒有備用 cell 時
        I-1 不會列出這個型別,I-3 也會明確退回,而不是假裝成功。

    antenna_change                     ❌ cached 模式做不到
        天線方位/下傾會改變射線追蹤的結果,而那是烘在快取裡的。
        要換天線必須用 sidecar 重新合成(path_synth),那是離線工作,不是執行期動作。
        live 模式才有意義 —— live 倍速上限 2x(實測走廊約 6x 但靠快取撐,保守取 2x),且同場域不可並行。

全部拒絕都走「明講理由」而不是靜默失敗:對方拿我方的請求當正確答案存檔,
我方假裝做了但沒做,會讓整個題庫的答案是錯的。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable

from main.utils.logger import get_logger

logger = get_logger(__name__)

# 事件型別 → 能否在 cached 模式執行
SUPPORTED_IN_CACHED = (
    "cell_outage", "energy_saving_state", "tx_power_change", "relation_change",
)
NEEDS_SPARE_CELL = ("cell_addition",)
LIVE_ONLY = ("antenna_change",)
ALL_TYPES = SUPPORTED_IN_CACHED + NEEDS_SPARE_CELL + LIVE_ONLY


# ── 識別對應 ──────────────────────────────────────────────────────
# I-2 給對方的 cell 識別有兩種:`cell_id`(場景裡的名字,如 "src")與 `ncgi`。
# 但執行期的 cell_id 帶著 E2 槽位標籤(如 "e03:src")—— 那是啟動後才確定的。
# 對方不可能知道標籤,所以 I-3 收「不帶標籤」的識別,在這裡轉成執行期的值。
# 兩種都收:對方手上有哪個就用哪個,不必回頭查對照表。


def resolve_cell(ident: str, name_to_runtime: dict[str, str],
                 ncgi_to_name: dict[str, str]) -> str | None:
    """I-2 的 cell_id 或 ncgi → 執行期 cell_id。認不得回 None。"""
    key = str(ident or "").strip()
    if not key:
        return None
    if key in name_to_runtime:          # I-2 的 cell_id
        return name_to_runtime[key]
    if key in ncgi_to_name:             # I-2 的 ncgi
        return name_to_runtime.get(ncgi_to_name[key])
    if key in name_to_runtime.values():  # 已經是執行期值(我方內部呼叫)
        return key
    return None


def _ok(res: dict) -> bool:
    """成功判定。per-run 容器(CU/DU/RU)回 {"status":"success"},
    orchestrator 自己回 {"success":true} —— 兩種都要認,只認一種會把成功當失敗。
    """
    if not isinstance(res, dict):
        return False
    if res.get("success") is True:
        return True
    return str(res.get("status") or "").lower() == "success"


def _msg(res: dict) -> str:
    return str((res or {}).get("message") or (res or {}).get("errors") or "")


def _post(host: str, path: str, body: dict, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(
        f"http://{host}:8000{path}",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode() or "{}") or {}


# ── 各型別的執行 ──────────────────────────────────────────────────


def _set_active(hosts: dict[str, str], cell: str, active: bool) -> dict:
    """同時切 DU(排程)與 RU(發射)。

    只切 DU 的話 RU 照樣發射,UE 仍量得到該 cell 的 RSRP —— 關站在觀測上看不出來。
    只切 RU 的話 DU 還會排程給它。兩邊都要,而且要分別回報,
    其中一邊沒成功必須讓對方看得見。
    """
    op = "enable" if active else "disable"
    du = _post(hosts["du"], f"/api/v0.1/DU/MAC/MacCellController/{op}", {"cell_id": cell})
    ru = _post(hosts["ru"], "/api/v0.1/RU/Config/RuController/set_cell_active",
               {"cell_id": cell, "is_active": active})
    ok = _ok(du) and _ok(ru)
    out = {"applied": ok, "du_applied": _ok(du), "ru_applied": _ok(ru),
           "detail": du.get("data")}
    if not ok:
        out["error"] = f"DU={_msg(du) or 'ok'} / RU={_msg(ru) or 'ok'}"
    return out


def _exec_cell_outage(ev: dict, hosts: dict[str, str]) -> dict:
    """關站。reason 只進紀錄 —— 對模擬行為沒有差別,但對方要據此分類題目。"""
    out = _set_active(hosts, ev["target"], False)
    out["reason"] = (ev.get("params") or {}).get("reason")
    return out


def _exec_energy_saving(ev: dict, hosts: dict[str, str]) -> dict:
    """節能狀態。energySaving = 關站;notEnergySaving = 開站。

    與 cell_outage 走同一個開關是**刻意**的 —— 在我方模型裡兩者對無線面的影響
    完全相同,差別只在成因。分類靠 RunControlEvent 的 action_type,對方由 I-7 分得開。
    """
    state = str((ev.get("params") or {}).get("state_after") or "").strip()
    if state not in ("energySaving", "notEnergySaving"):
        return {"applied": False, "error": f"state_after 必須是 energySaving / notEnergySaving,收到 {state!r}"}
    out = _set_active(hosts, ev["target"], state != "energySaving")
    out["state_after"] = state
    return out


def _exec_tx_power(ev: dict, hosts: dict[str, str]) -> dict:
    """改發射功率。要同時改兩處,否則物理與回報會對不起來:

      RU  Cell.power_dbm         —— 真正影響 RSRP 的那一個(執行期疊到 path gain 上)
      DU  CellState.tx_power_dbm —— 經 F1 帶到 CU,PEE.AvgPower 的輸入

    只改 RU 的話功耗欄位不動;只改 DU 的話功耗變了但訊號沒變。兩邊都要。
    RU 走單點介面 set_cell_power,不走 update_cells —— 後者是全量替換,
    要改一顆得重送整份清單,少送任何一顆就會被刪掉。
    """
    cell = ev["target"]
    after = (ev.get("params") or {}).get("tx_power_dbm_after")
    if after is None:
        return {"applied": False, "error": "params.tx_power_dbm_after 必填"}
    after = float(after)

    ru = _post(hosts["ru"], "/api/v0.1/RU/Config/RuController/set_cell_power",
               {"cell_id": cell, "power_dbm": after})
    if not _ok(ru):
        return {"applied": False, "error": f"RU 未套用:{_msg(ru)}"}
    du = _post(hosts["du"], "/api/v0.1/DU/MAC/MacCellController/update",
               {"cell_id": cell, "tx_power_dbm": after})
    return {
        "applied": _ok(du),
        "tx_power_dbm_before": (ru.get("data") or {}).get("power_dbm_before"),
        "tx_power_dbm_after": after,
        # DU 沒套用的話訊號變了但 PEE.AvgPower 還是舊功率 —— 要讓對方看得見
        "du_applied": _ok(du),
        "error": None if _ok(du) else f"RU 已改但 DU 未套用:{_msg(du)}",
    }


# 規格的 attributes → 我方 NrCellRelation 的旗標。語意是**相反**的:
# 規格講「允許」,我方存的是「封鎖」。對映錯會讓對方以為關掉了換手,實際上打開了。
_ATTR_TO_FLAG = {
    "is_ho_allowed": "hoBlocklist",
    "is_remove_allowed": "noRemove",
    "is_xn_allowed": "xnBlocklist",
}


def _exec_relation_change(ev: dict, hosts: dict[str, str]) -> dict:
    """鄰區關係增刪改 —— 走 CU 既有的 SON 觸發入口(與 xApp 用的是同一條)。

    注意 CU 那支三種動作的參數形狀不同:ADD 吃 target{cgi},REMOVE / FLAG 吃 targetCgi。
    FLAG 一次只設一個旗標,所以 attributes 有幾個就送幾次。
    """
    p = ev.get("params") or {}
    action = str(p.get("action") or "").lower()
    src = p.get("source_ncgi") or ev.get("target")
    tgt = p.get("target_ncgi")
    if not src or not tgt:
        return {"applied": False, "error": "params.source_ncgi 與 target_ncgi 必填"}

    base = {"applied": False, "action": action, "source_ncgi": src, "target_ncgi": tgt}

    if action == "add":
        res = _post(hosts["cu"], "/api/v0.1/CU/E2/Anr/control",
                    {"requestType": "ADD", "sourceCellId": src, "target": {"cgi": tgt}})
        out = res.get("data") or {}
        result = out.get("result")
        # CU 把 NOT_FOUND / 各種 REJECTED 也包在 200 裡 —— 只看 HTTP 會把拒絕當成功
        return {**base, "applied": _ok(res) and result in ("ADDED", "UPDATED", "OK", None),
                "result": result, "detail": out.get("detail")}

    if action == "remove":
        res = _post(hosts["cu"], "/api/v0.1/CU/E2/Anr/control",
                    {"requestType": "REMOVE", "sourceCellId": src, "targetCgi": tgt,
                     "reason": str(p.get("reason") or "agent_event")})
        out = res.get("data") or {}
        result = out.get("result")
        return {**base, "applied": _ok(res) and result == "REMOVED",
                "result": result, "detail": out.get("detail"),
                "error": None if result == "REMOVED" else f"CU 回 {result}"}

    if action == "set":
        attrs = p.get("attributes") or {}
        if not attrs:
            return {**base, "error": "action=set 需要 attributes"}
        results = []
        for key, allowed in attrs.items():
            flag = _ATTR_TO_FLAG.get(key)
            if flag is None:
                results.append({"attribute": key, "result": "UNSUPPORTED_ATTRIBUTE"})
                continue
            # 允許 → 清掉封鎖旗標;不允許 → 設上封鎖旗標
            op = "clear" if bool(allowed) else "set"
            res = _post(hosts["cu"], "/api/v0.1/CU/E2/Anr/control",
                        {"requestType": "FLAG", "sourceCellId": src, "targetCgi": tgt,
                         "flag": flag, "op": op})
            out = res.get("data") or {}
            results.append({"attribute": key, "flag": flag, "op": op,
                            "result": out.get("result")})
        ok = bool(results) and all(str(r.get("result") or "").startswith("FLAG_") for r in results)
        return {**base, "applied": ok, "flags": results,
                "error": None if ok else "部分旗標未套用"}

    return {**base, "error": f"action 必須是 add / remove / set,收到 {action!r}"}


def _exec_cell_addition(ev: dict, hosts: dict[str, str]) -> dict:
    """新增 cell = 把預算時已納入、初始關閉的備用 cell 打開。

    params 裡的 pci / arfcn / tx_power_dbm 只有在與備用 cell 既有設定相符時才有意義;
    位置絕對改不得 —— 位置變了 path gain 就全錯,而那是烘在快取裡的。
    這裡只套用功率(可執行期改),其餘不符就回報差異,讓對方知道實際用的是什麼。
    """
    cell = ev["target"]
    res = _set_active(hosts, cell, True)
    if not res.get("applied"):
        return {"applied": False, "error": f"開不起來 {cell}:{res.get('error')}"}
    out: dict[str, Any] = {"applied": True, "enabled": cell, **res}
    p = ev.get("params") or {}
    if p.get("tx_power_dbm") is not None:
        out["tx_power"] = _exec_tx_power(
            {"target": cell, "params": {"tx_power_dbm_after": p["tx_power_dbm"]}}, hosts)
    if p.get("position") is not None:
        out["position_ignored"] = "位置由通道快取決定,執行期不可改;實際位置見 I-2 的 cells[].position"
    return out


def _exec_antenna_change(ev: dict, hosts: dict[str, str]) -> dict:
    """改天線方位／下傾。**只有 live 模式做得到**。

    cached 模式下 path gain 是預算時以當時的方位射線追蹤出來的,烘在 .npz 裡;
    執行期改 RU 的那張表只會讓資料庫與物理各說各話,對方拿到的觀測資料完全
    反映不出天線動過。所以這裡直接退回,而不是做一半。

    live 模式走即時射線追蹤,每個 tick 重讀 cell 的方位,所以改得動 ——
    前提是 RU 的 memo cache 鍵有把方位算進去(2026-09-22 已修,見
    dl_tti_pipeline.antenna_signature),否則沒移動的 UE 會一直命中舊值。
    """
    if str(ev.get("mode") or "cached") != "live":
        return {"applied": False,
                "error": "antenna_change 在 cached 模式無法執行:天線方位/下傾已烘進通道快取,"
                         "執行期改動不會改變任何 path gain。需要此型別請改用 live 模式"
                         "(倍速上限 2x、同場域不可並行)"}
    p = ev.get("params") or {}
    body: dict[str, Any] = {"cell_id": ev["target"]}
    if p.get("azimuth_deg_after") is not None:
        body["azimuth_deg"] = float(p["azimuth_deg_after"])
    if p.get("tilt_deg_after") is not None:
        body["tilt_deg"] = float(p["tilt_deg_after"])
    if len(body) == 1:
        return {"applied": False,
                "error": "params 需要 azimuth_deg_after 或 tilt_deg_after 至少一個"}

    res = _post(hosts["ru"], "/api/v0.1/RU/Config/RuController/set_cell_antenna", body)
    out = res.get("data") or {}
    return {"applied": _ok(res), "before": out.get("before"), "after": out.get("after"),
            "changed": out.get("changed"),
            "error": None if _ok(res) else f"RU 未套用:{_msg(res)}"}


EXECUTORS: dict[str, Callable[[dict, dict], dict]] = {
    "cell_outage": _exec_cell_outage,
    "energy_saving_state": _exec_energy_saving,
    "tx_power_change": _exec_tx_power,
    "relation_change": _exec_relation_change,
    "cell_addition": _exec_cell_addition,
    "antenna_change": _exec_antenna_change,
}


# ── 驗證 ──────────────────────────────────────────────────────────


def supported_types(cell_ids: list[str], inactive_cell_ids: list[str], mode: str = "cached") -> list[str]:
    """某場域在某模式下實際可觸發的事件型別。

    不可執行的型別不列出來 —— 列了對方就會拿去出題,而我方接不住。
    """
    types = list(SUPPORTED_IN_CACHED)
    if inactive_cell_ids:
        types += list(NEEDS_SPARE_CELL)
    if mode == "live":
        types += list(LIVE_ONLY)
    return types


def event_param_schema() -> dict[str, dict]:
    """給 I-1 附在 event_types 旁的參數綱要 —— 對方照這個組 I-3 的 params。"""
    return {
        "cell_outage": {"reason": "字串,hardware / planned;僅供分類,不影響模擬"},
        "energy_saving_state": {"state_after": "energySaving | notEnergySaving"},
        "tx_power_change": {"tx_power_dbm_after": "數值,dBm"},
        "relation_change": {
            "source_ncgi": "字串", "target_ncgi": "字串",
            "action": "add | remove | set",
            "attributes": "set 時給 {is_ho_allowed, is_remove_allowed}",
        },
        "cell_addition": {
            "tx_power_dbm": "數值,可選;其餘識別以場域既有設定為準",
            "_note": "僅能開啟場域預留的備用 cell(cached 模式下還必須是預算時已納入的);"
                     "target 須為 I-2 中 administrative_state=locked 的 cell",
        },
        "antenna_change": {
            "tilt_deg_after": "數值", "azimuth_deg_after": "數值",
            "_note": "cached 模式不支援(見 I-3 說明)",
        },
    }


def validate(events: list[dict], *, cell_ids: list[str], inactive_cell_ids: list[str],
             duration_s: int, mode: str = "cached",
             name_to_runtime: dict[str, str] | None = None,
             ncgi_to_name: dict[str, str] | None = None) -> tuple[list[dict], list[dict]]:
    """回 (正規化後的事件, 錯誤清單)。有任何錯誤就不該啟動 —— 對方會把請求原樣
    存成正確答案,我方半套執行等於給了錯的答案。

    正規化包含把 I-2 的 cell 識別換成執行期的 cell_id(帶 E2 槽位標籤),
    執行器拿到的一律是可以直接打 DU/RU/CU 的值。
    """
    n2r = name_to_runtime or {c: c for c in cell_ids}
    n2n = ncgi_to_name or {}
    ok: list[dict] = []
    errs: list[dict] = []
    allowed = supported_types(cell_ids, inactive_cell_ids, mode)
    seen_ids: set[str] = set()

    for i, raw in enumerate(events or []):
        eid = str(raw.get("event_id") or f"E{i + 1}")

        def bad(msg: str) -> None:
            errs.append({"event_id": eid, "error": msg})

        etype = str(raw.get("type") or "")
        if etype not in ALL_TYPES:
            bad(f"未知的事件型別 {etype!r};可用:{sorted(ALL_TYPES)}")
            continue
        if etype not in allowed:
            if etype in LIVE_ONLY:
                bad(f"{etype} 僅 live 模式可執行(天線參數已烘進通道快取)")
            elif etype in NEEDS_SPARE_CELL:
                bad(f"{etype} 需要場域預留「預算時已納入但初始關閉」的備用 cell,本場域沒有")
            else:
                bad(f"{etype} 在 {mode} 模式不可執行")
            continue
        if eid in seen_ids:
            bad("event_id 重複")
            continue
        seen_ids.add(eid)

        try:
            at = float(raw.get("at_offset_s"))
        except (TypeError, ValueError):
            bad("at_offset_s 必填且須為數值(自模擬起點的秒數)")
            continue
        if at < 0:
            bad("at_offset_s 不可為負")
            continue
        if duration_s and at > duration_s:
            bad(f"at_offset_s={at} 超過 duration_s={duration_s},該事件永遠不會觸發")
            continue

        params = dict(raw.get("params") or {})
        target_in = str(raw.get("target") or "")

        if etype == "relation_change":
            # target 是關係,不是 cell —— 用 params 裡的 source/target 兩端各自解析
            src_in = params.get("source_ncgi") or target_in
            tgt_in = params.get("target_ncgi")
            src = resolve_cell(src_in, n2r, n2n)
            tgt = resolve_cell(tgt_in, n2r, n2n)
            if src is None:
                bad(f"source_ncgi {src_in!r} 不是本場域的 cell;可用:{cell_ids}")
                continue
            if tgt is None:
                bad(f"target_ncgi {tgt_in!r} 不是本場域的 cell;可用:{cell_ids}")
                continue
            params["source_ncgi"], params["target_ncgi"] = src, tgt
            target = src
        else:
            target = resolve_cell(target_in, n2r, n2n)
            if target is None:
                bad(f"target {target_in!r} 不是本場域的 cell;可用:{cell_ids}")
                continue
            if etype == "cell_addition":
                spare = {resolve_cell(c, n2r, n2n) for c in inactive_cell_ids}
                if target not in spare:
                    bad(f"cell_addition 的 target 須為初始關閉的備用 cell;"
                        f"本場域的備用 cell:{inactive_cell_ids}")
                    continue

        dur = raw.get("duration_s")
        ok.append({
            "event_id": eid,
            "type": etype,
            # 執行器要靠 mode 判斷做不做得到(antenna_change 只有 live 可行)。
            # 記在事件上而不是另外傳,orchestrator 重啟接回時才還原得出來。
            "mode": mode,
            "target": target,                 # 執行期 cell_id(帶槽位標籤)
            "target_requested": target_in,    # 對方原本給的識別,回覆時 echo 用
            "at_offset_s": at,
            "duration_s": None if dur is None else float(dur),
            "params": params,
        })

    ok.sort(key=lambda e: (e["at_offset_s"], e["event_id"]))
    return ok, errs


def expand_with_revert(events: list[dict]) -> list[dict]:
    """duration_s 不為 null 的事件,在 at + duration 補一筆還原動作。

    規格說 duration_s 是「持續時間,null 為至結束」。關站 300 秒後要自己開回來,
    否則對方以為只關了 5 分鐘,實際關到劇本結束 —— 觀測資料與正確答案不符。
    只有語意上可還原的型別才補;不可還原的(如 relation remove)明確不補。
    """
    out = list(events)
    for e in events:
        d = e.get("duration_s")
        if not d or d <= 0:
            continue
        rev: dict | None = None
        if e["type"] in ("cell_outage", "cell_addition"):
            rev = {**e, "type": "energy_saving_state",
                   "params": {"state_after": "notEnergySaving" if e["type"] == "cell_outage" else "energySaving"}}
        elif e["type"] == "energy_saving_state":
            cur = (e.get("params") or {}).get("state_after")
            rev = {**e, "params": {"state_after":
                                   "notEnergySaving" if cur == "energySaving" else "energySaving"}}
        if rev is None:
            continue
        rev = {**rev,
               "event_id": f"{e['event_id']}~revert",
               "at_offset_s": float(e["at_offset_s"]) + float(d),
               "duration_s": None,
               "_revert_of": e["event_id"]}
        out.append(rev)
    out.sort(key=lambda x: (x["at_offset_s"], x["event_id"]))
    return out
