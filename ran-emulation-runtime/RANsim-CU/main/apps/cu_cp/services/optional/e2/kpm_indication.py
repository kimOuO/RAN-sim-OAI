"""E2-SM-KPM Indication builder — 對齊 OAI Format 3 (UE-level)。

OAI ref:
  - openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_kpm.c::fill_kpm_ind_msg_frm_3()
  - openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_kpm_subs.c (metrics 定義)

送到 RIC 的 KPM metric names + wire 單位（RIC 端按此單位原樣寫入 InfluxDB,全 INTEGER）：
  - DRB.PdcpSduVolumeDL / UL    — kbit
  - DRB.UEThpDl / UL             — bps
  - DRB.RlcSduDelayDl            — μs
  - RRU.PrbTotDl / UL            — PPM (1% = 10000 ppm)
擴展（非 OAI 標準但 5G 常用）：
  - RSRP                         — dBm (38.133 mapping)
  - SINR                         — dB  (38.133 mapping)
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

from main.apps.cu_cp.models.cell_measurement_log import CellMeasurementLog
from main.apps.cu_cp.models.measurement_log import MeasurementLog
from main.apps.cu_cp.models.ue_context import UeContext

# per-UE measurement 超過此秒數沒更新 → 視為 idle,traffic metric 報 0(對齊 OAI idle)。
# 門檻取 5s:active 時 measurement_report 約 1~2.5s 一筆,idle 則數分鐘無更新,可乾淨區分。
_IDLE_STALE_SEC = 5.0


def _cell_prb_pct(serving_cell: str, field: str = "prb_pct_dl") -> float:
    """AL2 — 取該 cell 最近一筆 CellMeasurementLog.prb_pct_{dl,ul}.

    對齊 3GPP TS 28.552 RRU.PrbTotDl/UL — cell-level metric, 不從 per-UE sum.
    沒紀錄回 0.0 (cell idle / 還沒收到 measurement).
    """
    if not serving_cell:
        return 0.0
    last = (
        CellMeasurementLog.objects.filter(cell_id=serving_cell)
        .order_by("-recorded_at")
        .first()
    )
    return float(getattr(last, field, 0.0)) if last else 0.0


# ── KPM 校正 hook(夾在 indication 產出 → e2adapter 之間;env gate,預設關)──
# KPM_CALIB_ENABLE=on 時,把 raw KPM + context 送 kpm-calib 服務,用 calibrated 值取代。
# 失敗/逾時/OOD 一律保留 raw(絕不擋 KPM 流)。
_KPM_CALIB_ENABLE = (os.environ.get("KPM_CALIB_ENABLE") or "off").strip().lower() in ("on", "1", "true")
_KPM_CALIB_URL = os.environ.get("KPM_CALIB_URL", "http://kpm-calib:8200/calibrate")
_KPM_CALIB_HEALTH = _KPM_CALIB_URL.rsplit("/", 1)[0] + "/health"
# reachability 快取:env on 後,實際 toggle 走 kpm-calib 容器 up/down(免重啟 CU、不掉 E2 sub)。
# down 時用快取快速回退 raw,不每筆 timeout。
_CALIB_CACHE = {"ts": 0.0, "ok": False}


def _calib_reachable() -> bool:
    now = time.time()
    if now - _CALIB_CACHE["ts"] < 5.0:
        return _CALIB_CACHE["ok"]
    ok = False
    try:
        with urllib.request.urlopen(_KPM_CALIB_HEALTH, timeout=0.2) as r:
            ok = json.loads(r.read().decode()).get("ok", False)
    except Exception:  # noqa: BLE001
        ok = False
    _CALIB_CACHE["ts"] = now
    _CALIB_CACHE["ok"] = ok
    return ok
_NAME2WIRE = {
    "DRB.UEThpDl": "thp_dl_bps", "DRB.UEThpUl": "thp_ul_bps",
    "DRB.PdcpSduVolumeDL": "vol_dl_kbit", "DRB.PdcpSduVolumeUL": "vol_ul_kbit",
    "DRB.RlcSduDelayDl": "delay_dl_us",
    "RRU.PrbTotDl": "prb_dl_ppm", "RRU.PrbTotUl": "prb_ul_ppm",
}


def _apply_calibration(meas_data: list, last_meas, ue, serving_cell: str) -> None:
    """把 meas_data 的值就地換成 kpm-calib 校正後的值(in-place);任何失敗都保留 raw。"""
    if not _KPM_CALIB_ENABLE or last_meas is None:
        return
    if not _calib_reachable():   # kpm-calib 容器 down → 快速回退 raw(toggle 機制)
        return
    try:
        payload = {
            "ue_id": ue.ue_id,
            "thp_dl_mbps": float(getattr(last_meas, "throughput_dl_mbps", 0.0) or 0.0),
            "thp_ul_mbps": float(getattr(last_meas, "throughput_ul_mbps", 0.0) or 0.0),
            "vol_dl_bytes": float(getattr(last_meas, "pdcp_sdu_volume_dl", 0) or 0),
            "vol_ul_bytes": float(getattr(last_meas, "pdcp_sdu_volume_ul", 0) or 0),
            "delay_dl_ms": float(getattr(last_meas, "rlc_sdu_delay_dl_ms", 0.0) or 0.0),
            "prb_dl_pct": _cell_prb_pct(serving_cell, "prb_pct_dl"),
            "prb_ul_pct": _cell_prb_pct(serving_cell, "prb_pct_ul"),
            "sinr_db": float(getattr(last_meas, "sinr_db", 0.0) or 0.0),
            "rsrp_dbm": float(getattr(last_meas, "rsrp_dbm", 0.0) or 0.0),
        }
        req = urllib.request.Request(
            _KPM_CALIB_URL, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=0.5) as r:
            res = json.loads(r.read().decode())
        if not res.get("ok"):
            return
        cal = res.get("calibrated", {})
        for md in meas_data:
            wk = _NAME2WIRE.get(md["name"])
            if wk and wk in cal:
                md["value"] = cal[wk]
    except Exception:  # noqa: BLE001 — 校正失敗絕不擋 KPM,保留 raw
        return


# OAI 標準 metric → 取值 lambda。
# 送到 RIC 的 wire 單位(RIC 端按此單位原樣寫入 InfluxDB,不再縮放),全部 INTEGER:
#   DRB.PdcpSduVolumeDL/UL = kbit   DRB.RlcSduDelayDl = μs(us)
#   DRB.UEThpDl/UL         = bps    RRU.PrbTotDl/UL   = PPM
# 命門:downstream codec(_value_to_kpm_uint)只 int(round(v)) 不縮放,故此處就把值
# 換算到目標單位再轉 INT。先換到「細單位」再 round,避免在粗單位下捨入掉精度。
METRIC_EXTRACTORS = {
    # DRB.UEThpDl/UL — bps。DU 給 Mbps,×1e6 → bps。
    "DRB.UEThpDl": lambda last_meas, ue: (
        int(round((last_meas.throughput_dl_mbps if last_meas else 0.0) * 1_000_000)), "bps",
    ),
    "DRB.UEThpUl": lambda last_meas, ue: (
        int(round((getattr(last_meas, "throughput_ul_mbps", 0.0) if last_meas else 0.0) * 1_000_000)), "bps",
    ),
    # DRB.PdcpSduVolumeDL/UL — kbit。DU PM aggregator 累計 bytes,×8/1000 → kbit。
    "DRB.PdcpSduVolumeDL": lambda last_meas, ue: (
        int(round((getattr(last_meas, "pdcp_sdu_volume_dl", 0) if last_meas else 0) * 8 / 1000.0)),
        "kbit",
    ),
    "DRB.PdcpSduVolumeUL": lambda last_meas, ue: (
        int(round((getattr(last_meas, "pdcp_sdu_volume_ul", 0) if last_meas else 0) * 8 / 1000.0)),
        "kbit",
    ),
    # RRU.PrbTotDl/UL — PPM。cell-level prb_pct(0~100),×10000 → ppm(1% = 10000 ppm)。
    # cell-level metric (3GPP TS 28.552),不從 per-UE sum;查 serving_cell 最新 CellMeasurementLog。
    "RRU.PrbTotDl": lambda last_meas, ue: (
        int(round(_cell_prb_pct(getattr(ue, "serving_cell", "") or "", "prb_pct_dl") * 10000)),
        "ppm",
    ),
    "RRU.PrbTotUl": lambda last_meas, ue: (
        int(round(_cell_prb_pct(getattr(ue, "serving_cell", "") or "", "prb_pct_ul") * 10000)),
        "ppm",
    ),
    "RSRP": lambda last_meas, ue: (last_meas.rsrp_dbm if last_meas else None, "dBm"),
    "SINR": lambda last_meas, ue: (last_meas.sinr_db if last_meas else None, "dB"),
    # DRB.RlcSduDelayDl — μs。內部 rlc_sdu_delay_dl_ms(ms),×1000 → μs。
    "DRB.RlcSduDelayDl": lambda last_meas, ue: (
        int(round((getattr(last_meas, "rlc_sdu_delay_dl_ms", 0.0) if last_meas else 0.0) * 1000)),
        "us",
    ),
}


def supported_metrics() -> list[str]:
    return list(METRIC_EXTRACTORS.keys())


def build_indication(subscription: dict[str, Any]) -> dict[str, Any] | None:
    """為一個 subscription 產生一筆 KPM Format 3 indication 訊息。

    OAI Format 3 結構：
      indication_message:
        format = 3
        ue_meas_report_lst[]
          ue_id, rrc_ue_id, amf_ue_ngap_id
          meas_data_lst[]
            { name, value, unit }

    回 None 表示沒 UE 配對到 filter / 沒新資料可推。
    """
    if subscription["service_model"] != "KPM":
        return None
    action = subscription.get("action_definition", {})
    metrics: list[str] = action.get("metrics") or []
    if not metrics:
        return None
    ue_filter: list[str] = action.get("ue_filter") or []   # 空 list = 全 UE

    ue_lst: list[dict[str, Any]] = []
    for ue in UeContext.objects.all():
        if ue_filter and ue.ue_id not in ue_filter:
            continue
        # 對齊 O-RAN: KPM Indication 只 cover CONNECTED UE.
        # IDLE UE 沒有 active measurement, 報 last_meas 殘值會誤導 xApp.
        if ue.rrc_state != "CONNECTED":
            continue
        last_meas = (
            MeasurementLog.objects.filter(ue_id=ue.ue_id)
            .order_by("-recorded_at")
            .first()
        )
        # IDLE 偵測 — per-UE measurement 在 idle(無 traffic)時不再更新:DU 的 tick
        # _ue_registry 在靜止+零流量下會被清空 → 不送 per-UE measurement_report →
        # last_meas 凍結在「最後一筆 active 值」。原樣報出會讓 RIC 看到「假流量」
        # (例:idle 卻持續報 ~0.9Mbps / delay 3.6ms)。對齊 OAI(idle KPM 全 0):
        # last_meas 過舊就把 traffic 類 metric 就地歸零(不寫回 DB),保留 RSRP/SINR
        # (UE 位置固定,鏈路仍有效);PRB 走 cell-level CellMeasurementLog 不受影響。
        if last_meas is not None:
            age_sec = time.time() - last_meas.recorded_at.timestamp()
            if age_sec > _IDLE_STALE_SEC:
                last_meas.throughput_dl_mbps = 0.0
                last_meas.throughput_ul_mbps = 0.0
                last_meas.pdcp_sdu_volume_dl = 0
                last_meas.pdcp_sdu_volume_ul = 0
                last_meas.rlc_sdu_delay_dl_ms = 0.0
        meas_data = []
        for m in metrics:
            extractor = METRIC_EXTRACTORS.get(m)
            if not extractor:
                continue
            try:
                value, unit = extractor(last_meas, ue)
            except Exception:
                value, unit = None, ""
            meas_data.append({"name": m, "value": value, "unit": unit})
        # serving cell info — xApp CCO 要按 cell 分組 metric，沒這個就無法做
        # P2.2: 走集中化 helper,有 OAI explicit nr_cellid 就用真值
        from main.apps.cu_cp.services.common.cell_id_map import to_nr_cellid
        from main.apps.cu_cp.models import CellConfig as _CellConfig
        serving_cell = ue.serving_cell or ""
        explicit = (
            _CellConfig.objects.filter(cell_id=serving_cell)
            .values_list("nr_cellid", flat=True)
            .first()
            if serving_cell else None
        )
        nr_cell_id = to_nr_cellid(serving_cell, explicit=explicit) if serving_cell else 0

        # KPM 校正 hook(env gate);把 meas_data 換成校正值,失敗保留 raw
        _apply_calibration(meas_data, last_meas, ue, serving_cell)

        ue_lst.append({
            "ue_id": ue.ue_id,
            "rrc_ue_id": getattr(ue, "rrc_ue_id", None),
            "amf_ue_ngap_id": getattr(ue, "amf_ue_ngap_id", None),
            "serving_cell": serving_cell,
            "nr_cell_id": nr_cell_id,
            "meas_data_lst": meas_data,
        })

    if not ue_lst:
        return None

    return {
        "subscription_id": subscription["subscription_id"],
        "ric_req_id": subscription["ric_req_id"],
        "ran_function_id": subscription["ran_function_id"],
        "indication_header": {
            "timestamp_ms": int(time.time() * 1000),
        },
        "indication_message": {
            "format": 3,
            "ue_meas_report_lst": ue_lst,
        },
    }
