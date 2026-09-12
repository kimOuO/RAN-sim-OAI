"""ran-sim-protocol — RAN-sim 平台 4 個 system 之間的訊息格式定義。

設計原則：
  - 所有 message 都是 @dataclass（可序列化成 dict / JSON）
  - 系統間傳輸用 HTTP POST body（JSON），不做真 ASN.1 編碼
  - 提供統一的 to_dict() / from_dict() helpers

Modules:
  - f1ap     : CU ↔ DU
  - fapi     : DU ↔ RU
  - ngap     : CU ↔ Mock 5GC
  - e1ap     : CU-CP ↔ CU-UP
  - physics  : RU → Physics REST API
  - common   : 共用 dataclass (CellConfig, DrbConfig, ...)
"""
from ran_sim_protocol.serde import to_dict, from_dict

__version__ = "0.1.0"
__all__ = ["to_dict", "from_dict"]
