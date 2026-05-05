"""把 CqiIndication / CrcIndication 推回 DU。

Endpoints（DU 側）：
  POST {DU}/api/v0.1/DU/FAPI/FapiRouter/cqi_indication
  POST {DU}/api/v0.1/DU/FAPI/FapiRouter/crc_indication
"""
from __future__ import annotations

import requests
from django.conf import settings
from ran_sim_protocol.fapi import CqiIndication, CrcIndication
from ran_sim_protocol.serde import to_dict

from main.utils.logger import get_logger


logger = get_logger(__name__)


def _du_url(element: str) -> str:
    return f"http://{settings.HTTP_DU_HOST}:{settings.HTTP_DU_PORT}/api/v0.1/DU/FAPI/FapiRouter/{element}"


def send_cqi_indication(msg: CqiIndication, *, timeout: float = 2.0) -> None:
    try:
        resp = requests.post(_du_url("cqi_indication"), json=to_dict(msg), timeout=timeout)
        if resp.status_code >= 400:
            logger.warning("cqi_indication non-2xx: %d %s", resp.status_code, resp.text[:200])
    except requests.RequestException as exc:
        # 不阻擋主流程：DU 暫離線時 RU 仍要能 ack DL TTI
        logger.warning("cqi_indication failed: %s", exc)


def send_crc_indication(msg: CrcIndication, *, timeout: float = 2.0) -> None:
    try:
        resp = requests.post(_du_url("crc_indication"), json=to_dict(msg), timeout=timeout)
        if resp.status_code >= 400:
            logger.warning("crc_indication non-2xx: %d %s", resp.status_code, resp.text[:200])
    except requests.RequestException as exc:
        logger.warning("crc_indication failed: %s", exc)
