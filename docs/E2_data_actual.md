# E2 實際資料(實測擷取)— 與 `E2_data_example.md` 同排版對照用

> 擷取日期:2026-08-12,場景 anr_missing_neighbor(2 cell / 5 UE / 3 Mbps CBR)。
> **排版刻意與 `E2_data_example.md` 完全一致**(2-space indent、含 `success/message/data` 外層),
> 可直接左右並排逐鍵比對。
>
> **上 E2 wire 時只取 `data` 內容**(外層 `success/message` 是 HTTP API 包裝),
> 再 zlib 壓縮放進 `indicationMessage`。
>
> ### 與範例檔的差異(僅此一項)
> `ue_status[].position` —— **已移除**(2026-08-12)。真實 E2/KPM 不攜帶 UE 位置
> (真網路需定位技術估算);範例檔的 legacy 格式有此欄,本平台決定不送,避免給
> xApp 現實中拿不到的資料。因此 `ue_status` 為 13 欄(範例 14 欄),**其餘結構
> 逐鍵一致**:外層鍵、`data` 鍵、`e2[]`、`pm{}` 每 cell 190 欄全對。

---

## 一、FULLKPM(ran_func 5)— 對應 `E2_data_example.md` 全文

結構:`timestamp_ms / compute_ms / tick_ms / e2[] / ue_status[] / pm{} / bbu_status / warnings`。
pm 每 cell 190 欄鍵名與範例逐鍵一致(已驗證)。

```json
{
  "success": true,
  "message": "OK",
  "data": {
    "timestamp_ms": 1786526657412,
    "compute_ms": 43,
    "tick_ms": 500,
    "e2": [
      {
        "gnb_id": "keep",
        "timestamp": 1786526657,
        "cells": [
          {
            "cell_id": "keep_c0",
            "ran_name": "keep",
            "pci": 40,
            "ues": [
              {
                "role": 1,
                "ue_id": "su0",
                "interfered": 0,
                "rsrp": -80,
                "rsrq": -10,
                "sinr": 11,
                "neighbors": [
                  {
                    "main_c0": {
                      "rsrp": -92,
                      "rsrq": -22
                    }
                  }
                ],
                "dl_throughput": 4,
                "ul_throughput": 0,
                "rb_start": 0,
                "rb_width": 18
              },
              {
                "role": 1,
                "ue_id": "su1",
                "interfered": 0,
                "rsrp": -80,
                "rsrq": -10,
                "sinr": 11,
                "neighbors": [
                  {
                    "main_c0": {
                      "rsrp": -92,
                      "rsrq": -22
                    }
                  }
                ],
                "dl_throughput": 4,
                "ul_throughput": 0,
                "rb_start": 18,
                "rb_width": 18
              },
              {
                "role": 1,
                "ue_id": "su2",
                "interfered": 0,
                "rsrp": -80,
                "rsrq": -10,
                "sinr": 11,
                "neighbors": [
                  {
                    "main_c0": {
                      "rsrp": -92,
                      "rsrq": -22
                    }
                  }
                ],
                "dl_throughput": 3,
                "ul_throughput": 0,
                "rb_start": 36,
                "rb_width": 18
              },
              {
                "role": 1,
                "ue_id": "su3",
                "interfered": 0,
                "rsrp": -80,
                "rsrq": -10,
                "sinr": 11,
                "neighbors": [
                  {
                    "main_c0": {
                      "rsrp": -92,
                      "rsrq": -22
                    }
                  }
                ],
                "dl_throughput": 4,
                "ul_throughput": 0,
                "rb_start": 54,
                "rb_width": 18
              },
              {
                "role": 1,
                "ue_id": "su4",
                "interfered": 0,
                "rsrp": -80,
                "rsrq": -10,
                "sinr": 11,
                "neighbors": [
                  {
                    "main_c0": {
                      "rsrp": -92,
                      "rsrq": -22
                    }
                  }
                ],
                "dl_throughput": 4,
                "ul_throughput": 0,
                "rb_start": 72,
                "rb_width": 18
              }
            ]
          }
        ]
      },
      {
        "gnb_id": "main",
        "timestamp": 1786526657,
        "cells": [
          {
            "cell_id": "main_c0",
            "ran_name": "main",
            "pci": 10,
            "ues": []
          }
        ]
      }
    ],
    "ue_status": [
      {
        "ue_id": "su0",
        "serving_gnb": "keep",
        "serving_pci": 40,
        "rsrp_dbm": -80.0,
        "sinr_db": 10.7,
        "all_rsrp": {
          "keep": -80.0,
          "main": -91.7
        },
        "throughput_dl_mbps": 4,
        "throughput_ul_mbps": 0,
        "quality": "good",
        "qos_5qi": 9,
        "role": 1,
        "mcs_dl": 8,
        "rb_width_dl": 18
      },
      {
        "ue_id": "su1",
        "serving_gnb": "keep",
        "serving_pci": 40,
        "rsrp_dbm": -80.0,
        "sinr_db": 10.7,
        "all_rsrp": {
          "keep": -80.0,
          "main": -91.7
        },
        "throughput_dl_mbps": 4,
        "throughput_ul_mbps": 0,
        "quality": "good",
        "qos_5qi": 9,
        "role": 1,
        "mcs_dl": 8,
        "rb_width_dl": 18
      },
      {
        "ue_id": "su2",
        "serving_gnb": "keep",
        "serving_pci": 40,
        "rsrp_dbm": -80.0,
        "sinr_db": 10.7,
        "all_rsrp": {
          "keep": -80.0,
          "main": -91.7
        },
        "throughput_dl_mbps": 3,
        "throughput_ul_mbps": 0,
        "quality": "good",
        "qos_5qi": 9,
        "role": 1,
        "mcs_dl": 8,
        "rb_width_dl": 18
      },
      {
        "ue_id": "su3",
        "serving_gnb": "keep",
        "serving_pci": 40,
        "rsrp_dbm": -80.0,
        "sinr_db": 10.7,
        "all_rsrp": {
          "keep": -80.0,
          "main": -91.7
        },
        "throughput_dl_mbps": 4,
        "throughput_ul_mbps": 0,
        "quality": "good",
        "qos_5qi": 9,
        "role": 1,
        "mcs_dl": 8,
        "rb_width_dl": 18
      },
      {
        "ue_id": "su4",
        "serving_gnb": "keep",
        "serving_pci": 40,
        "rsrp_dbm": -80.0,
        "sinr_db": 10.7,
        "all_rsrp": {
          "keep": -80.0,
          "main": -91.7
        },
        "throughput_dl_mbps": 4,
        "throughput_ul_mbps": 0,
        "quality": "good",
        "qos_5qi": 9,
        "role": 1,
        "mcs_dl": 8,
        "rb_width_dl": 18
      }
    ],
    "pm": {
      "gnb-keep": [
        {
          "cell_id": "keep_c0",
          "cu_timestamp_start": "20260812.0924+0000",
          "cu_timestamp_end": "0924+0000",
          "cu_filename": "A20260812.0924+0000-0924+0000_keep-cu.xml",
          "du_timestamp_start": "20260812.0924+0000",
          "du_timestamp_end": "0924+0000",
          "du_filename": "A20260812.0924+0000-0924+0000_keep-du.xml",
          "cu_CU_Capability": "1",
          "cu_RRC.ConnEstabAtt.sum": "10",
          "cu_RRC.ConnEstabAtt.mo-Data": "10",
          "cu_RRC.ConnEstabAtt.mo-Signalling": "0",
          "cu_RRC.ConnEstabSucc.sum": "10",
          "cu_RRC.ConnEstabSucc.mo-Data": "10",
          "cu_RRC.ConnEstabSucc.mo-Signalling": "0",
          "cu_RRC.ConnEstabSucc.emergency": "0",
          "cu_RRC.ConnMax": "5",
          "cu_RRC.ConnMean": "4",
          "cu_RRC.ConnReEstabSetup.sum": "2",
          "cu_RRC.ReEstabAtt": "2",
          "cu_RRC.ReEstabAtt.otherFailure": "0",
          "cu_RRC.ReEstabSuccWithUeContext.sum": "0",
          "cu_RRC.ReEstabSuccWithUeContext.otherFailure": "0",
          "cu_RRC.ReEstabSuccWithoutUeContext.sum": "2",
          "cu_RRC.ReEstabSuccWithoutUeContext.otherFailure": "0",
          "cu_MM.HoExeIntraFreqReq": "57",
          "cu_MM.HoExeIntraFreqSucc": "57",
          "cu_MM.HoExeIntraReq": "57",
          "cu_MM.HoExeIntraSucc": "57",
          "cu_MM.HoPrepIntraReq": "57",
          "cu_MM.HoPrepIntraSucc": "57",
          "cu_gnb.MR.Event.A3": "57",
          "cu_UECNTX.ConnEstabAtt.sum": "10",
          "cu_UECNTX.ConnEstabAtt.mo-Data": "10",
          "cu_UECNTX.ConnEstabAtt.mo-Signalling": "0",
          "cu_UECNTX.ConnEstabSucc.sum": "10",
          "cu_UECNTX.ConnEstabSucc.mo-Data": "10",
          "cu_UECNTX.ConnEstabSucc.mo-Signalling": "0",
          "cu_UECNTX.Release.5GCinit.NASCause": "0",
          "cu_UECNTX.Release.5GCinit.RNCause": "0",
          "cu_UECNTX.Release.5GCinit.sum": "0",
          "cu_gnb.UECNTX.Release.gNBinit.RNCause": "0",
          "cu_gnb.UECNTX.Release.gNBinit.sum": "0",
          "cu_SM.PDUSessionSetupReq": "10",
          "cu_SM.PDUSessionSetupSucc": "10",
          "cu_gnb.SM.PDUSessionRelease.Att": "0",
          "cu_gnb.SM.PDUSessionRelease.Succ": "0",
          "cu_DRB.EstabAtt.5QI.sum": "10",
          "cu_DRB.EstabAtt.5QI9": "10",
          "cu_DRB.EstabSucc.5QI.sum": "10",
          "cu_DRB.EstabSucc.5QI9": "10",
          "cu_DRB.InitialEstabAtt.5QI.sum": "10",
          "cu_DRB.InitialEstabAtt.5QI1": "0",
          "cu_DRB.InitialEstabSucc.5QI.sum": "10",
          "cu_DRB.InitialEstabSucc.5QI9": "10",
          "cu_DRB.PdcpPacketDiscardDL.5QI9": "0",
          "cu_DRB.PdcpReordDelayUl": "0",
          "cu_DRB.RelActNbr.5QI.sum": "0",
          "cu_DRB.RelActNbr.5QI9": "0",
          "cu_DRB.SessionTime.5QI.sum": "29820",
          "cu_DRB.SessionTime.5QI9": "29820",
          "cu_DRB.PdcpSduVolumeDL_5QI1": "0",
          "cu_DRB.PdcpSduVolumeUl_5QI1": "0",
          "cu_gnb.DRB.SdapSduVolumeDL.5QI1": "0",
          "cu_gnb.DRB.SdapSduVolumeUl.5QI1": "0",
          "cu_DRB.PdcpSduVolumeDL_5QI4": "0",
          "cu_DRB.PdcpSduVolumeUl_5QI4": "0",
          "cu_gnb.DRB.SdapSduVolumeDL.5QI4": "0",
          "cu_gnb.DRB.SdapSduVolumeUl.5QI4": "0",
          "cu_DRB.PdcpSduVolumeDL_5QI9": "48812630",
          "cu_DRB.PdcpSduVolumeUl_5QI9": "842639",
          "cu_gnb.DRB.SdapSduVolumeDL.5QI9": "48812630",
          "cu_gnb.DRB.SdapSduVolumeUl.5QI9": "842639",
          "cu_QF.EstabAttNbr.5QI.sum": "0",
          "cu_QF.EstabAttNbr.5QI9": "0",
          "cu_QF.EstabSuccNbr.5QI.sum": "0",
          "cu_QF.EstabSuccNbr.5QI9": "0",
          "cu_QF.InitialEstabAttNbr.5QI.sum": "0",
          "cu_QF.InitialEstabAttNbr.5QI9": "0",
          "cu_QF.InitialEstabSuccNbr.5QI.sum": "0",
          "cu_QF.InitialEstabSuccNbr.5QI9": "0",
          "cu_QF.RelActNbr.Qos.sum": "0",
          "cu_QF.RelActNbr.Qos9": "0",
          "cu_QF.ReleaseAttNbr.5QI.sum": "0",
          "cu_QF.ReleaseAttNbr.5QI9": "0",
          "cu_gnb.RRC.ConnEstabSetup.emergency": "0",
          "cu_gnb.RRC.ConnEstabSetup.mo-Data": "0",
          "cu_gnb.RRC.ConnEstabSetup.mo-Signalling": "0",
          "cu_gnb.RRC.ConnEstabSetup.sum": "10",
          "cu_gnb.RRC.ConnReConfigAtt": "57",
          "cu_gnb.RRC.ConnReConfigSucc": "57",
          "cu_gnb.RRC.ConnReEstab.ReEstab.otherFailure": "0",
          "cu_gnb.RRC.ConnReEstab.ReEstab.sum": "0",
          "cu_gnb.RRC.ConnReEstabSetup.otherFailure": "0",
          "cu_gnb.RRC.ConnRelease.Other": "0",
          "cu_gnb.RRC.ConnRelease.sum": "0",
          "cu_gnb.RRC.SigTimeReEstab.Avg": "0",
          "cu_gnb.RRC.SigTimeReEstab.Max": "0",
          "cu_gnb.RRC.SigTimeReconfig.Avg": "0",
          "cu_gnb.RRC.SigTimeReconfig.Max": "0",
          "cu_gnb.RRC.SigTimeSetup.Avg": "0",
          "cu_gnb.RRC.SigTimeSetup.Max": "0",
          "du_169:PEE.AvgTemperature": "0.00",
          "du_170:PEE.MinTemperature": "0.00",
          "du_171:PEE.MaxTemperature": "0.00",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS0": "2",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS1": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS2": "2",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS3": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS4": "5",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS5": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS6": "5",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS7": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS8": "493",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS9": "1",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS10": "3",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS11": "1",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS12": "3",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS13": "1",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS14": "3",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS15": "1",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS16": "3",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS17": "1",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS18": "3",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS19": "1",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS20": "3",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS21": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS22": "3",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS23": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS24": "3",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS25": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS26": "3",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS27": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS28": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS29": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS30": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS31": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS0": "4",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS1": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS2": "5",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS3": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS4": "5",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS5": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS6": "493",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS7": "1",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS8": "3",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS9": "1",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS10": "3",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS11": "1",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS12": "3",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS13": "1",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS14": "3",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS15": "1",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS16": "3",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS17": "1",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS18": "3",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS19": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS20": "3",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS21": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS22": "3",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS23": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS24": "3",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS25": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS26": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS27": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS28": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS29": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS30": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS31": "0",
          "du_CARR.WBCQIDist.BinCQI0.BinTable2": "5",
          "du_CARR.WBCQIDist.BinCQI1.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI2.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI3.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI4.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI5.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI6.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI7.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI8.BinTable2": "5",
          "du_CARR.WBCQIDist.BinCQI9.BinTable2": "530",
          "du_CARR.WBCQIDist.BinCQI10.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI11.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI12.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI13.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI14.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI15.BinTable2": "0",
          "du_CARR.PRBUsageDLNbr": "4608",
          "du_CARR.PRBUsageULNbr": "250",
          "du_DRB.AirIfDelayDlAvg.5QI1": "0",
          "du_DRB.AirIfDelayDlAvg.5QI9": "9",
          "du_DRB.AirIfDelayUlAvg.5QI1": "0",
          "du_DRB.AirIfDelayUlAvg.5QI9": "0"
        }
      ],
      "gnb-main": [
        {
          "cell_id": "main_c0",
          "cu_timestamp_start": "20260812.0924+0000",
          "cu_timestamp_end": "0924+0000",
          "cu_filename": "A20260812.0924+0000-0924+0000_main-cu.xml",
          "du_timestamp_start": "20260812.0924+0000",
          "du_timestamp_end": "0924+0000",
          "du_filename": "A20260812.0924+0000-0924+0000_main-du.xml",
          "cu_CU_Capability": "1",
          "cu_RRC.ConnEstabAtt.sum": "0",
          "cu_RRC.ConnEstabAtt.mo-Data": "0",
          "cu_RRC.ConnEstabAtt.mo-Signalling": "0",
          "cu_RRC.ConnEstabSucc.sum": "0",
          "cu_RRC.ConnEstabSucc.mo-Data": "0",
          "cu_RRC.ConnEstabSucc.mo-Signalling": "0",
          "cu_RRC.ConnEstabSucc.emergency": "0",
          "cu_RRC.ConnMax": "4",
          "cu_RRC.ConnMean": "0",
          "cu_RRC.ConnReEstabSetup.sum": "0",
          "cu_RRC.ReEstabAtt": "0",
          "cu_RRC.ReEstabAtt.otherFailure": "0",
          "cu_RRC.ReEstabSuccWithUeContext.sum": "0",
          "cu_RRC.ReEstabSuccWithUeContext.otherFailure": "0",
          "cu_RRC.ReEstabSuccWithoutUeContext.sum": "0",
          "cu_RRC.ReEstabSuccWithoutUeContext.otherFailure": "0",
          "cu_MM.HoExeIntraFreqReq": "65",
          "cu_MM.HoExeIntraFreqSucc": "65",
          "cu_MM.HoExeIntraReq": "65",
          "cu_MM.HoExeIntraSucc": "65",
          "cu_MM.HoPrepIntraReq": "66",
          "cu_MM.HoPrepIntraSucc": "65",
          "cu_gnb.MR.Event.A3": "66",
          "cu_UECNTX.ConnEstabAtt.sum": "0",
          "cu_UECNTX.ConnEstabAtt.mo-Data": "0",
          "cu_UECNTX.ConnEstabAtt.mo-Signalling": "0",
          "cu_UECNTX.ConnEstabSucc.sum": "0",
          "cu_UECNTX.ConnEstabSucc.mo-Data": "0",
          "cu_UECNTX.ConnEstabSucc.mo-Signalling": "0",
          "cu_UECNTX.Release.5GCinit.NASCause": "0",
          "cu_UECNTX.Release.5GCinit.RNCause": "0",
          "cu_UECNTX.Release.5GCinit.sum": "0",
          "cu_gnb.UECNTX.Release.gNBinit.RNCause": "0",
          "cu_gnb.UECNTX.Release.gNBinit.sum": "0",
          "cu_SM.PDUSessionSetupReq": "0",
          "cu_SM.PDUSessionSetupSucc": "0",
          "cu_gnb.SM.PDUSessionRelease.Att": "0",
          "cu_gnb.SM.PDUSessionRelease.Succ": "0",
          "cu_DRB.EstabAtt.5QI.sum": "0",
          "cu_DRB.EstabAtt.5QI9": "0",
          "cu_DRB.EstabSucc.5QI.sum": "0",
          "cu_DRB.EstabSucc.5QI9": "0",
          "cu_DRB.InitialEstabAtt.5QI.sum": "0",
          "cu_DRB.InitialEstabAtt.5QI1": "0",
          "cu_DRB.InitialEstabSucc.5QI.sum": "0",
          "cu_DRB.InitialEstabSucc.5QI9": "0",
          "cu_DRB.PdcpPacketDiscardDL.5QI9": "0",
          "cu_DRB.PdcpReordDelayUl": "0",
          "cu_DRB.RelActNbr.5QI.sum": "0",
          "cu_DRB.RelActNbr.5QI9": "0",
          "cu_DRB.SessionTime.5QI.sum": "3281",
          "cu_DRB.SessionTime.5QI9": "3281",
          "cu_DRB.PdcpSduVolumeDL_5QI1": "0",
          "cu_DRB.PdcpSduVolumeUl_5QI1": "0",
          "cu_gnb.DRB.SdapSduVolumeDL.5QI1": "0",
          "cu_gnb.DRB.SdapSduVolumeUl.5QI1": "0",
          "cu_DRB.PdcpSduVolumeDL_5QI4": "0",
          "cu_DRB.PdcpSduVolumeUl_5QI4": "0",
          "cu_gnb.DRB.SdapSduVolumeDL.5QI4": "0",
          "cu_gnb.DRB.SdapSduVolumeUl.5QI4": "0",
          "cu_DRB.PdcpSduVolumeDL_5QI9": "0",
          "cu_DRB.PdcpSduVolumeUl_5QI9": "0",
          "cu_gnb.DRB.SdapSduVolumeDL.5QI9": "0",
          "cu_gnb.DRB.SdapSduVolumeUl.5QI9": "0",
          "cu_QF.EstabAttNbr.5QI.sum": "0",
          "cu_QF.EstabAttNbr.5QI9": "0",
          "cu_QF.EstabSuccNbr.5QI.sum": "0",
          "cu_QF.EstabSuccNbr.5QI9": "0",
          "cu_QF.InitialEstabAttNbr.5QI.sum": "0",
          "cu_QF.InitialEstabAttNbr.5QI9": "0",
          "cu_QF.InitialEstabSuccNbr.5QI.sum": "0",
          "cu_QF.InitialEstabSuccNbr.5QI9": "0",
          "cu_QF.RelActNbr.Qos.sum": "0",
          "cu_QF.RelActNbr.Qos9": "0",
          "cu_QF.ReleaseAttNbr.5QI.sum": "0",
          "cu_QF.ReleaseAttNbr.5QI9": "0",
          "cu_gnb.RRC.ConnEstabSetup.emergency": "0",
          "cu_gnb.RRC.ConnEstabSetup.mo-Data": "0",
          "cu_gnb.RRC.ConnEstabSetup.mo-Signalling": "0",
          "cu_gnb.RRC.ConnEstabSetup.sum": "0",
          "cu_gnb.RRC.ConnReConfigAtt": "65",
          "cu_gnb.RRC.ConnReConfigSucc": "65",
          "cu_gnb.RRC.ConnReEstab.ReEstab.otherFailure": "0",
          "cu_gnb.RRC.ConnReEstab.ReEstab.sum": "0",
          "cu_gnb.RRC.ConnReEstabSetup.otherFailure": "0",
          "cu_gnb.RRC.ConnRelease.Other": "0",
          "cu_gnb.RRC.ConnRelease.sum": "0",
          "cu_gnb.RRC.SigTimeReEstab.Avg": "0",
          "cu_gnb.RRC.SigTimeReEstab.Max": "0",
          "cu_gnb.RRC.SigTimeReconfig.Avg": "0",
          "cu_gnb.RRC.SigTimeReconfig.Max": "0",
          "cu_gnb.RRC.SigTimeSetup.Avg": "0",
          "cu_gnb.RRC.SigTimeSetup.Max": "0",
          "du_169:PEE.AvgTemperature": "0.00",
          "du_170:PEE.MinTemperature": "0.00",
          "du_171:PEE.MaxTemperature": "0.00",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS0": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS1": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS2": "2",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS3": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS4": "2",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS5": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS6": "5",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS7": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS8": "5",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS9": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS10": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS11": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS12": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS13": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS14": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS15": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS16": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS17": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS18": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS19": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS20": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS21": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS22": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS23": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS24": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS25": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS26": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS27": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS28": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS29": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS30": "0",
          "du_CARR.PDSCHMCSDist.BinTable2.BinMCS31": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS0": "2",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS1": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS2": "2",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS3": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS4": "5",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS5": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS6": "5",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS7": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS8": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS9": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS10": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS11": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS12": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS13": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS14": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS15": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS16": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS17": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS18": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS19": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS20": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS21": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS22": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS23": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS24": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS25": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS26": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS27": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS28": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS29": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS30": "0",
          "du_CARR.PUSCHMCSDist.BinTable1.BinMCS31": "0",
          "du_CARR.WBCQIDist.BinCQI0.BinTable2": "9",
          "du_CARR.WBCQIDist.BinCQI1.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI2.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI3.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI4.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI5.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI6.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI7.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI8.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI9.BinTable2": "5",
          "du_CARR.WBCQIDist.BinCQI10.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI11.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI12.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI13.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI14.BinTable2": "0",
          "du_CARR.WBCQIDist.BinCQI15.BinTable2": "0",
          "du_CARR.PRBUsageDLNbr": "318",
          "du_CARR.PRBUsageULNbr": "0",
          "du_DRB.AirIfDelayDlAvg.5QI1": "0",
          "du_DRB.AirIfDelayDlAvg.5QI9": "0",
          "du_DRB.AirIfDelayUlAvg.5QI1": "0",
          "du_DRB.AirIfDelayUlAvg.5QI9": "0"
        }
      ]
    },
    "bbu_status": {
      "gnb-keep": {
        "cpu": 0.0,
        "cpu_power": 0.0,
        "cpu_temp": 0.0,
        "load_average": 0.0,
        "mem": 0.0,
        "tot_power": 0.0
      },
      "gnb-main": {
        "cpu": 0.0,
        "cpu_power": 0.0,
        "cpu_temp": 0.0,
        "load_average": 0.0,
        "mem": 0.0,
        "tot_power": 0.0
      },
      "timestamp": "1786526657412"
    },
    "warnings": []
  }
}
```

---

## 二、ANR(ran_func 6)— 範例檔**沒有**的新增部分

`E2_data_example.md` 是 legacy FULLKPM 格式,不含 ANR。以下五大塊為本平台新增
(對應 ANR情境_v8 卷面資料塊),同樣走 JSON + zlib 上 wire:

| 資料塊 | 對應卷面 |
|---|---|
| `e2NodeInformation` | NRT 鄰區關係表(§9.3.38)+ 變更審計 |
| `kpmIndication` | HO 速率/成功比 + 失敗原因(cell 級 + per 關係)|
| `rlfKpm` | RLF/掉話/重建 inbound(依來源 PCI)|
| `mroKpm` | MRO 歸因三聯 |
| `e2MessageCopyAggregate` | 依 PCI 的 RSRP 統計 |

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "timestamp_ms": 1786526657479,
    "e2NodeInformation": {
      "servingCells": [
        {
          "ncgi": "keep_c0",
          "physicalCellId": 40,
          "arfcn": 633333,
          "radioAccessTechnology": "NR"
        },
        {
          "ncgi": "main_c0",
          "physicalCellId": 10,
          "arfcn": 633333,
          "radioAccessTechnology": "NR"
        }
      ],
      "frequencyRelations": [
        {
          "radioAccessTechnology": "NR",
          "arfcn": 633333
        }
      ],
      "neighbourCellRelations": [
        {
          "sourceCellNcgi": "keep_c0",
          "targetCellGlobalId": "main_c0",
          "targetPhysicalCellId": 10,
          "targetArfcn": 633333,
          "targetRadioAccessTechnology": "NR",
          "isHoAllowed": true,
          "isRemoveAllowed": true,
          "isXnAllowed": true,
          "xnX2Established": false,
          "hoValidated": false,
          "version": 1,
          "relationAgeSec": 1463.65521,
          "flags": {
            "hoBlocklist": false,
            "noRemove": false,
            "xnBlocklist": false
          }
        },
        {
          "sourceCellNcgi": "main_c0",
          "targetCellGlobalId": "keep_c0",
          "targetPhysicalCellId": 40,
          "targetArfcn": 633333,
          "targetRadioAccessTechnology": "NR",
          "isHoAllowed": true,
          "isRemoveAllowed": true,
          "isXnAllowed": true,
          "xnX2Established": true,
          "hoValidated": true,
          "version": 8,
          "relationAgeSec": 3332.136589,
          "flags": {
            "hoBlocklist": false,
            "noRemove": false,
            "xnBlocklist": false
          }
        }
      ],
      "relationChangeEvents": [
        {
          "action": "FLAG",
          "targetCellGlobalId": "keep_c0",
          "by": "xapp",
          "at": "2026-08-12T09:23:13.870873+00:00",
          "detail": "hoBlocklist=False"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "keep_c0",
          "by": "xapp",
          "at": "2026-08-12T09:23:11.780328+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "keep_c0",
          "by": "xapp",
          "at": "2026-08-12T09:23:09.698455+00:00",
          "detail": "updated"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "keep_c0",
          "by": "xapp",
          "at": "2026-08-12T09:12:29.485927+00:00",
          "detail": "hoBlocklist=False"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "keep_c0",
          "by": "xapp",
          "at": "2026-08-12T09:10:08.216088+00:00",
          "detail": "hoBlocklist=False"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "keep_c0",
          "by": "xapp",
          "at": "2026-08-12T09:10:06.140874+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "keep_c0",
          "by": "xapp",
          "at": "2026-08-12T09:10:04.074718+00:00",
          "detail": "updated"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "main_c0",
          "by": "xapp",
          "at": "2026-08-12T08:59:53.839970+00:00",
          "detail": "created"
        },
        {
          "action": "REMOVE",
          "targetCellGlobalId": "main_c0",
          "by": "xapp",
          "at": "2026-08-12T08:59:43.702457+00:00",
          "detail": "aging"
        },
        {
          "action": "REMOVE",
          "targetCellGlobalId": "ghost_c0",
          "by": "xapp",
          "at": "2026-08-12T08:42:46.919209+00:00",
          "detail": "aging"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "main_c0",
          "by": "xapp",
          "at": "2026-08-12T08:29:22.646048+00:00",
          "detail": "created"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T07:45:33.149298+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "src_c0",
          "by": "xapp",
          "at": "2026-08-12T07:08:02.507716+00:00",
          "detail": "created"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T07:08:02.367043+00:00",
          "detail": "created"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "T2",
          "by": "xapp",
          "at": "2026-08-12T06:01:12.977394+00:00",
          "detail": "created"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "T",
          "by": "xapp",
          "at": "2026-08-12T06:01:12.968153+00:00",
          "detail": "hoBlocklist=False"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "T",
          "by": "xapp",
          "at": "2026-08-12T06:01:12.960878+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "src_c0",
          "by": "xapp",
          "at": "2026-08-12T04:19:53.999994+00:00",
          "detail": "created"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T04:19:53.972093+00:00",
          "detail": "created"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "das1_c1",
          "by": "xapp",
          "at": "2026-08-12T04:01:55.051257+00:00",
          "detail": "hoBlocklist=False"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "das1_c1",
          "by": "xapp",
          "at": "2026-08-12T04:01:54.031565+00:00",
          "detail": "hoBlocklist=False"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "das1_c1",
          "by": "xapp",
          "at": "2026-08-12T04:01:53.009703+00:00",
          "detail": "hoBlocklist=False"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T03:19:08.679186+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T03:19:07.167073+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T03:19:05.654902+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T03:07:32.315094+00:00",
          "detail": "hoBlocklist=False"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T03:04:29.053611+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T03:04:28.014244+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T03:04:26.988476+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:59:56.177672+00:00",
          "detail": "hoBlocklist=False"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:54:29.288544+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:54:28.973819+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:54:28.657150+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:54:28.339965+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:54:28.032111+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:54:27.715830+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:54:27.397207+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:54:27.083308+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:54:26.771286+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:54:26.455514+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:53:55.978354+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:53:54.937485+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:53:53.916725+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:46:31.981838+00:00",
          "detail": "updated"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:46:30.953769+00:00",
          "detail": "updated"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:46:29.933819+00:00",
          "detail": "created"
        },
        {
          "action": "REMOVE",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:16:37.917025+00:00",
          "detail": "aging"
        },
        {
          "action": "FLAG",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:16:33.897000+00:00",
          "detail": "hoBlocklist=True"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "nbr_c0",
          "by": "xapp",
          "at": "2026-08-12T02:07:48.764818+00:00",
          "detail": "created"
        },
        {
          "action": "ADD",
          "targetCellGlobalId": "src_c0",
          "by": "xapp",
          "at": "2026-08-12T01:32:24.799723+00:00",
          "detail": "created"
        }
      ]
    },
    "kpmIndication": {
      "windowMin": 10.0,
      "cellLevel": {
        "main_c0": {
          "MM.HoExeAttRatePerMin": 0.5,
          "MM.HoExeSuccRatio_last50": 0.98,
          "sampleCount_last50": 50,
          "handoverFailureCauseRatePerMin": {},
          "handoverFailureCauseCumulativeSinceCreation": {}
        },
        "keep_c0": {
          "MM.HoExeAttRatePerMin": 0.0,
          "MM.HoExeSuccRatio_last50": 1.0,
          "sampleCount_last50": 50,
          "handoverFailureCauseRatePerMin": {},
          "handoverFailureCauseCumulativeSinceCreation": {}
        }
      },
      "perNeighbourRelation": [
        {
          "sourceCellNcgi": "keep_c0",
          "targetCellGlobalId": "main_c0",
          "MM.HoExeAttRatePerMin": 0.0,
          "MM.HoExeSuccRatio_last50": 1.0,
          "sampleCount_last50": 50,
          "handoverFailureCauseRatePerMin": {},
          "handoverFailureCauseCumulativeSinceCreation": {}
        },
        {
          "sourceCellNcgi": "main_c0",
          "targetCellGlobalId": "keep_c0",
          "MM.HoExeAttRatePerMin": 0.5,
          "MM.HoExeSuccRatio_last50": 0.98,
          "sampleCount_last50": 50,
          "handoverFailureCauseRatePerMin": {},
          "handoverFailureCauseCumulativeSinceCreation": {}
        }
      ]
    },
    "rlfKpm": {
      "windowMin": 10.0,
      "cellLevel": {
        "keep_c0": {
          "RLF.DetectedRate": 0.2,
          "RLF.DropWithoutReestablishmentRate": 0.0,
          "RRC.ConnReEstabInboundRatePerMin": 0.2
        }
      },
      "reestablishmentInboundByPreviousPci": [
        {
          "cellNcgi": "keep_c0",
          "byPreviousPci": [
            {
              "previousPhysicalCellId": 40,
              "ratePerMin": 0.2
            }
          ]
        }
      ]
    },
    "mroKpm": {
      "windowMin": 10.0,
      "tShortSec": 5.0,
      "cellLevel": {
        "keep_c0": {
          "HO.IntraSys.TooEarlyRate": 0.2,
          "HO.IntraSys.TooLateRate": 0.0,
          "HO.IntraSys.ToWrongCellRate": 0.0
        }
      },
      "total": {
        "HO.IntraSys.TooEarlyRate": 0.2,
        "HO.IntraSys.TooLateRate": 0.0,
        "HO.IntraSys.ToWrongCellRate": 0.0
      }
    },
    "e2MessageCopyAggregate": {
      "windowMin": 10.0,
      "rowsScanned": 2439,
      "measurementReportAggregate": [
        {
          "reportedRadioAccessTechnology": "NR",
          "reportedArfcn": 633333,
          "reportedPhysicalCellId": 10,
          "sampleRatePerMin": 242.8,
          "rsrpPercentile50Dbm": -77.0,
          "rsrpPercentile90Dbm": -76.9,
          "rsrpStandardDeviationDb": 4.6,
          "servingRsrpPercentile50Dbm": -42.2
        },
        {
          "reportedRadioAccessTechnology": "NR",
          "reportedArfcn": 633333,
          "reportedPhysicalCellId": 40,
          "sampleRatePerMin": 244.6,
          "rsrpPercentile50Dbm": -42.2,
          "rsrpPercentile90Dbm": -37.1,
          "rsrpStandardDeviationDb": 12.9,
          "servingRsrpPercentile50Dbm": -42.2
        }
      ]
    }
  }
}
```

---

## 對照速查

| | FULLKPM(func 5) | ANR(func 6) |
|---|---|---|
| 範例檔有嗎 | ✅ 結構一致(除 position 已移除)| ❌ 全新增 |
| indicationHeader | `{"format":"DTFULLKPM-v1","encoding":"zlib",…}` | `{"format":"DT-ANR-v1","encoding":"zlib",…}` |
| 壓縮後大小 | ~2.5 KB | ~0.7–3 KB |
| 對接文件 | `api/e2sm_fullkpm.md` | `api/e2sm_anr.md` |
