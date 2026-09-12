# ASN.1 Schemas

E2 adapter 需要以下 ASN.1 schema 才能 encode/decode E2AP / E2SM PDU。

對方（Near-RT RIC team）確認使用 standard O-RAN：

| 檔名 | 內容 | 來源 |
|:---|:---|:---|
| `e2ap_v2.asn1` | E2AP v2.0.3 | O-RAN WG3 |
| `e2sm_v3.00.asn` | E2SM common (v3.00) | O-RAN WG3 |
| `e2sm_kpm_v2.0.03.asn` | E2SM-KPM v2.0.03 | O-RAN WG3 |
| `e2sm_rc_v01.03.asn` | E2SM-RC v01.03 | O-RAN WG3 |

## 取得方式（任選一）

**從 FlexRIC repo（最常用，已驗證跟 OAI 對齊）：**
```bash
git clone --depth 1 https://gitlab.eurecom.fr/mosaic5g/flexric.git /tmp/flexric
cp /tmp/flexric/src/asn1/asn1/e2ap_v2.asn1               ./
cp /tmp/flexric/src/asn1/asn1/e2sm_v3.00.asn             ./
cp /tmp/flexric/src/asn1/asn1/e2sm_kpm_v2.0.03.asn       ./
cp /tmp/flexric/src/asn1/asn1/e2sm_rc_v01.03.asn         ./
rm -rf /tmp/flexric
```

**從 O-RAN WG3 spec PDF 抽（後備）：**
- TS O-RAN.WG3.E2AP-v02.03 §10  — `e2ap_v2.asn1`
- TS O-RAN.WG3.E2SM-KPM-v02.00.03 §8 — `e2sm_kpm_v2.0.03.asn`
- TS O-RAN.WG3.E2SM-RC-v01.03 §8 — `e2sm_rc_v01.03.asn`

## 驗證

放好檔案後，asn1tools 會在 adapter 啟動時自動 compile：

```bash
docker logs ransim-e2adapter | grep -i asn1
# expect: ASN.1 schemas compiled OK: ['e2ap_v2.asn1', 'e2sm_v3.00.asn', ...]
```

或打 status endpoint：

```bash
curl -X POST http://10.3.0.217:8201/api/v0.1/E2Adapter/Status/AdapterStatusReader/read \
  -H "Content-Type: application/json" -d '{}' | jq .data.schemas
# expect: {"loaded": true, "file_list": [...4 files], "error": ""}
```

## 注意

- 不要把 `.asn` / `.asn1` 檔本身 commit 進 repo（FlexRIC 是 LGPL/AGPL，且檔案大）
- 加進 `.gitignore`（已加）
- Production 部署時用 init container 或 build 階段把 schemas 拉進 image
