"""UeAttachService — Stage 1B.

共用 UE attach chain(對齊 /editor handleStartSim § D–E + setupUE)。

每個 UE 跑四步:
  1. CU rrc_attach              (idempotent — 已 CONNECTED 跳過)
  2. DU register_ue_at(cell)    (補進 _ue_registry)
  3. CU force_serving_cell      (UeContext.serving_cell 填好)
  4. CU update_traffic_profile  (走 F1AP UeCtxSetup → DU 建 RLC entity)
     只在 caller 明確帶 traffic_profile 或 default_traffic_profile 才推。
     沒帶 → 保留 CU 既存 profile(/editor /draw 頁設過的 traffic 不會被覆蓋)。

任一步失敗只 warn 不擋,回 attached_count + 失敗 UE list 給 caller。
"""
from __future__ import annotations

import logging
from typing import Any

from main.apps.ue_lifecycle.services import cu_client, du_client


logger = logging.getLogger(__name__)


class UeAttachService:
    """無狀態 service — caller 餵 UE list + per-UE config(serving cell, traffic profile)。"""

    @staticmethod
    def attach_all(
        ues: list[dict[str, Any]],
        *,
        default_serving_cell: str = "gnb1_cell0",
        default_traffic_profile: dict[str, Any] | None = None,
        context: str = "",
    ) -> dict[str, Any]:
        """Attach each UE through RRC + RLC setup chain.

        Args:
            ues: list[{name: str, serving_cell?: str, traffic_profile?: dict}]
                 serving_cell / traffic_profile 沒給就 fallback 到 default_*
            default_serving_cell: 沒帶 serving_cell 的 UE 用這個
            default_traffic_profile: 沒帶 traffic_profile 的 UE 用這個。
                None(default) = 不覆寫 CU 既存 profile,跳過 update_traffic_profile 步驟。
            context: log prefix(scenario_id 或 "editor")

        Returns:
            {
              "attached": int,
              "failed": [{"ue": str, "step": str, "error": str}],
              "total": int,
            }
        """
        prefix = f"[{context}] " if context else ""
        failed: list[dict[str, str]] = []
        attached = 0

        for ue in ues:
            ue_name = ue.get("name")
            if not ue_name:
                continue
            serving = ue.get("serving_cell") or default_serving_cell
            # profile resolution:per-UE > default(可能 None — 跳過 update)
            profile: dict[str, Any] | None = ue.get("traffic_profile") or default_traffic_profile

            def _step(label: str, fn) -> bool:
                try:
                    if not fn():
                        failed.append({"ue": ue_name, "step": label, "error": "client returned False"})
                        logger.warning("%sattach UE %s: %s failed", prefix, ue_name, label)
                        return False
                    return True
                except Exception as e:  # noqa: BLE001
                    failed.append({"ue": ue_name, "step": label, "error": str(e)})
                    logger.warning("%sattach UE %s: %s raised %s", prefix, ue_name, label, e)
                    return False

            if not _step("RRC attach", lambda n=ue_name: cu_client.rrc_attach(n)):
                continue
            if not _step("DU register_ue", lambda n=ue_name, c=serving: du_client.register_ue_at(n, serving_cell=c)):
                continue
            if not _step("force_serving_cell", lambda n=ue_name, c=serving: cu_client.force_serving_cell(n, c)):
                continue
            if profile is not None:
                if not _step("update_traffic_profile", lambda n=ue_name, p=profile: cu_client.update_traffic_profile(n, p)):
                    continue
            else:
                logger.debug("%sUE %s: keep existing CU traffic_profile (no override given)", prefix, ue_name)

            attached += 1
            logger.info("%sUE %s attached → serving=%s, profile_override=%s",
                        prefix, ue_name, serving, profile is not None)

        logger.info(
            "%sUE attach summary: attached=%d/%d failed=%d (default_serving=%s)",
            prefix, attached, len(ues), len(failed), default_serving_cell,
        )
        return {"attached": attached, "failed": failed, "total": len(ues)}
