# ran-sim-protocol

跨系統訊息格式定義。給 RAN-sim 平台的 4 個 Django 專案（CU、DU、RU、Physics）共用，避免訊息格式各自為政。

## 安裝（每個 Django 專案的 `requirements/base.txt`）

```
ran-sim-protocol @ file:///app/ran-sim-protocol
```

或 dev 階段直接：
```bash
pip install -e /home/mitlab/XAPP_DT/RAN-sim/ran-sim-protocol
```

## 模組

| Module | 用途 | 對應 OAI |
|---|---|---|
| `f1ap`    | CU ↔ DU              | `openair2/F1AP/` |
| `fapi`    | DU ↔ RU              | `nfapi/` |
| `ngap`    | CU ↔ Mock 5GC         | `openair3/NGAP/` |
| `e1ap`    | CU-CP ↔ CU-UP        | `openair2/E1AP/` |
| `physics` | RU → Physics REST    | （無，本平台特有） |
| `common`  | 共用 dataclass        | — |

## 使用方式

```python
from ran_sim_protocol.fapi import DlTtiRequest, DlPduConfig, CqiIndication
from ran_sim_protocol import to_dict, from_dict

# 送
req = DlTtiRequest(
    sfn=10, slot=5,
    pdus=[DlPduConfig(ue_id="ue1", prb_start=0, prb_count=100, mcs=20)],
)
http_body = to_dict(req)         # → dict，可丟給 requests.post(json=...)

# 收
recv_dict = request.data         # Django REST framework
req = from_dict(DlTtiRequest, recv_dict)  # → DlTtiRequest 物件
```

## 不在範圍

- 真 ASN.1 wire format（PER/BER/OER 編碼）
- SCTP / eCPRI 傳輸層
- 加密（內網信任，不需）
