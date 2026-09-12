"""E1 Bearer Context Setup processor — wires PDCP / SDAP / GTP-U.

OAI ref: openair2/LAYER2/nr_pdcp/cucp_cuup_handler.c (e1_bearer_context_setup
at L162-260) — same orchestration, sans real ASN.1.

Public callable: ``E1apHandler.bearer_context_setup(payload)`` returns a
BearerContextSetupResponse-shaped dict. Used by both:
  - cu_cp's CuupClientBusinessService in integrated mode (direct call)
  - cu_up's E1ApRouterActor in split mode (HTTP entry → here)
"""
from __future__ import annotations

from typing import Any

from main.apps.cu_up.models.drb import Drb
from main.apps.cu_up.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.cu_up.services.common.timestamp_service import TimestampService
from main.apps.cu_up.services.common.uuid_service import UUIDService
from main.apps.cu_up.services.optional.gtpu.gtpu_tunnel import GtpuTunnel
from main.apps.cu_up.services.optional.pdcp.pdcp_entity import get_or_create_entity as get_pdcp
from main.apps.cu_up.services.optional.sdap.sdap_entity import get_or_create as get_sdap
from main.utils.logger import get_logger

logger = get_logger(__name__)


class E1apHandler:
    @staticmethod
    def bearer_context_setup(payload: dict[str, Any]) -> dict[str, Any]:
        ue_id = payload["ue_id"]
        drbs_in = payload.get("drbs", [])
        now = TimestampService.now()

        sdap = get_sdap(ue_id)
        drb_setup_list: list[dict[str, Any]] = []

        for drb in drbs_in:
            drb_id = drb["drb_id"]
            qos_5qi = drb["qos_5qi"]
            rlc_mode = drb.get("rlc_mode", "AM")

            # 1) GTP-U N3 (toward UPF) — peer addr/TEID are unknown in this mock
            n3 = GtpuTunnel.create_tunnel(ue_id, drb_id, kind="N3")

            # 2) GTP-U F1-U (toward DU) — DU peer details fill in via Modification
            f1u = GtpuTunnel.create_tunnel(ue_id, drb_id, kind="F1U")

            # 3) PDCP entity
            get_pdcp(ue_id, drb_id)

            # 4) SDAP — default 1:1 mapping QFI=qos_5qi → drb_id
            sdap.map_qfi(qos_5qi, drb_id, default=(len(drb_setup_list) == 0))

            # 5) Persist Drb row
            drb_uuid = UUIDService.generate_uuid("drb", f"{ue_id}:{drb_id}")
            SqlDbBusinessService.upsert_compound(
                Drb,
                keys={"ue_id": ue_id, "drb_id": drb_id},
                defaults={
                    "drb_uuid": drb_uuid,
                    "qos_5qi": qos_5qi,
                    "rlc_mode": rlc_mode,
                    "gtp_teid_ul": f1u.local_teid,
                    "gtp_teid_dl": 0,
                    "created_at": now,
                },
            )

            drb_setup_list.append({
                "drb_id": drb_id,
                "success": True,
                "cu_up_tunnel_addr": "127.0.0.1",
                "cu_up_teid": f1u.local_teid,
                "n3_local_teid": n3.local_teid,
            })

        logger.info("E1 Bearer Context Setup: ue=%s drbs=%d", ue_id, len(drb_setup_list))
        return {
            "ue_id": ue_id,
            "drb_setup_list": drb_setup_list,
            "success": True,
        }
