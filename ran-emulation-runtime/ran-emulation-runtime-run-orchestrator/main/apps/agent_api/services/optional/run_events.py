"""歸檔資料 → Agent 介面 I-6 的事件紀錄。

I-6 要的是**逐筆訊息副本**,不是統計值。對方的判準(缺漏鄰區、PCI 混淆、覆蓋洞、
換手問題)全靠明細:「回報了哪個 PCI、訊號多少」「重建時前一個服務 cell 是誰」。

我方的資料分在三張表,這裡統一翻成規格的事件格式:
    RunKpmSample.per_ue   → meas_report      (每個視窗每個 UE 一筆量測)
    RunHandoverEvent      → ho_exe_succ / ho_exe_fail / ho_prep_fail / rlf / rrc_reestab_req
    RunControlEvent(son/) → cgi_resolution

兩個要對外講清楚的差異:
  1. 我方量測是**週期性**的(每個 PM 視窗一次),不是 3GPP 的事件觸發式(A3 條件滿足才報)。
     所以 event_trigger 回 "periodic",不假裝是 A3。
  2. rrc_reestab_req 沒有獨立的訊息紀錄,是從 RLF 事件的 reestab 欄位導出的 ——
     同一個 RLF 會同時產生 rlf 與 rrc_reestab_req 兩筆,時間相同。
"""
from __future__ import annotations

# 規格 I-6 的型別枚舉
MEAS_REPORT = "meas_report"
HO_EXE_SUCC = "ho_exe_succ"
HO_EXE_FAIL = "ho_exe_fail"
HO_PREP_FAIL = "ho_prep_fail"
RLF = "rlf"
RRC_REESTAB_REQ = "rrc_reestab_req"
CGI_RESOLUTION = "cgi_resolution"
ALL_TYPES = (MEAS_REPORT, HO_EXE_SUCC, HO_EXE_FAIL, HO_PREP_FAIL, RLF,
             RRC_REESTAB_REQ, CGI_RESOLUTION)

# 我方 outcome → 規格型別
_OUTCOME_TYPE = {"SUCC": HO_EXE_SUCC, "FAIL": HO_EXE_FAIL, "PREP": HO_PREP_FAIL, "RLF": RLF}
# 換手失敗原因 → 規格的 cause_category
_CAUSE_CATEGORY = {
    "HandoverToWrongCell": "other", "TooEarly": "timeout", "TooLate": "timeout",
    "TXnRELOCprepExpiry": "timeout", "Rejected": "rejected", "RLF": "rlf",
}


def _base(type_: str, offset_s: float, gnb_id: str, cell_id: str, ue_id: str | None,
          payload: dict) -> dict:
    return {
        "type": type_,
        "offset_s": round(float(offset_s), 3),
        "gnb_id": gnb_id,
        "cell_id": cell_id,
        "ue_id": ue_id,
        "payload": payload,
    }


def meas_reports(kpm_rows: list[dict], gnb_of_cell: dict[str, str],
                 strip) -> list[dict]:
    """KPM 視窗的 per_ue → 逐筆量測報告。

    每個 (視窗, UE) 就是一次量測回報。鄰區帶 pci / arfcn —— 對方判「回報了不在
    鄰區表裡的 PCI」就靠這個。
    """
    out = []
    for row in kpm_rows:
        t = (row.get("sim_time_ms") or 0) / 1000.0
        for ue_id, m in (row.get("per_ue") or {}).items():
            if not m:
                continue
            serving = strip(m.get("serving_cell") or "")
            reported = []
            for n in (m.get("neighbor_cells_json") or []):
                reported.append({
                    "pci": n.get("pci"),
                    "arfcn": n.get("arfcn"),
                    "rsrp": n.get("rsrp_dbm"),
                    "rsrq": n.get("rsrq_db"),
                    # 我方的真值,對方可用來對答案;真實 UE 量測不會有這個
                    "cell_id": strip(n.get("cell_id") or ""),
                })
            out.append(_base(MEAS_REPORT, t, gnb_of_cell.get(serving, ""), serving, ue_id, {
                "reported": reported,
                "serving_rsrp": m.get("rsrp_dbm"),
                "serving_rsrq": m.get("rsrq_db"),
                "serving_sinr": m.get("sinr_db"),
                # 我方是週期性回報,不是 A3 事件觸發 —— 不假裝
                "event_trigger": "periodic",
            }))
    return out


def handover_events(rows: list[dict], gnb_of_cell: dict[str, str], strip) -> list[dict]:
    """換手 / RLF 事件。RLF 若有重建,額外導出一筆 rrc_reestab_req。"""
    out = []
    for r in rows:
        t = (r.get("at_sim_ms") or 0) / 1000.0
        src = strip(r.get("source_cell") or "")
        tgt = strip(r.get("target_cell") or "")
        d = r.get("detail") if isinstance(r.get("detail"), dict) else {}
        oc = str(r.get("outcome") or "")
        type_ = _OUTCOME_TYPE.get(oc)
        if type_ is None:
            continue
        gnb = gnb_of_cell.get(src, "")
        if type_ == RLF:
            out.append(_base(RLF, t, gnb, src, r.get("ue_id"), {
                "serving_pci": d.get("source_pci"),
                "last_sinr": d.get("sinr_at_rlf"),
                "last_rsrp": None,          # RLF 當下只留了 SINR
                "reason": d.get("reason"),
                "t310_ms": d.get("t310_ms"),
                "reestablished": bool(tgt),
            }))
            if tgt:
                # 重建請求沒有獨立訊息紀錄,由 RLF 的 reestab 欄位導出(時間相同)
                out.append(_base(RRC_REESTAB_REQ, t, gnb_of_cell.get(tgt, ""), tgt, r.get("ue_id"), {
                    "reestablishment_cause": d.get("reason") or "otherFailure",
                    "previous_pci": d.get("source_pci"),
                    "previous_ncgi": src,
                    "target_cell_id": tgt,
                    "derived_from": "rlf",
                }))
            continue
        cause = d.get("failure_cause") or ""
        out.append(_base(type_, t, gnb, src, r.get("ue_id"), {
            "target_cell_id": tgt,
            "target_ncgi": tgt or None,
            "trigger": d.get("trigger"),
            "cause": cause or None,
            "cause_category": _CAUSE_CATEGORY.get(cause) if cause else None,
            "mro_class": d.get("mro_class") or None,
        }))
    return out


def cgi_resolutions(rows: list[dict], gnb_of_cell: dict[str, str], strip) -> list[dict]:
    """自主稽核裡的 CGI 解析 → 規格的 cgi_resolution。"""
    out = []
    for r in rows:
        if not str(r.get("action_type") or "").startswith("cgi_resolution"):
            continue
        d = r.get("detail") if isinstance(r.get("detail"), dict) else {}
        oid = str(r.get("target") or d.get("object_id") or "")
        # object_id 形如 "e03:src|pci2@633333"
        serving, _, rest = oid.partition("|")
        pci = arfcn = None
        if rest.startswith("pci"):
            p, _, a = rest[3:].partition("@")
            pci = int(p) if p.isdigit() else None
            arfcn = int(a) if a.isdigit() else None
        resolved = strip(str(d.get("after") or ""))
        serving = strip(serving)
        out.append(_base(CGI_RESOLUTION, (r.get("at_sim_ms") or 0) / 1000.0,
                         gnb_of_cell.get(serving, ""), serving, None, {
            "pci": pci,
            "arfcn": arfcn,
            "resolved_ncgi": [resolved] if resolved else [],
            "outcome": d.get("action"),          # resolve / fail / skip
            "reason": d.get("reason"),
        }))
    return out
