"""SceneApplyService — Stage 1A.

共用 RAN backend scene-apply chain(對齊 /editor handleStartSim C.1〜C.5)。
不論是 /editor live_db 模式還是 /scenarios 劇本模式,都呼這個 service 套用拓樸。

對外只一個 entry: apply(cells, ues_with_positions)。

任何一步失敗只 warn 不擋,跟 Dashboard 原 best-effort 行為一致 — 回傳 errors
list 給 caller 做後續記錄/重試決策。
"""
from __future__ import annotations

import logging
from typing import Any

from main.apps.ue_lifecycle.services import cu_client, du_client, ru_client


logger = logging.getLogger(__name__)


class SceneApplyService:
    """無狀態 service — caller 把組好的 payload 傳進來,內部跑 C.1〜C.5。"""

    @staticmethod
    def apply(
        ru_cells: list[dict[str, Any]],
        du_cells: list[dict[str, Any]],
        ru_ue_payload: list[dict[str, Any]],
        ue_names: list[str],
        *,
        clear_stale_ues: bool = True,
        context: str = "",
    ) -> dict[str, Any]:
        """Run the RU/DU/CU scene-apply chain.

        Args:
            ru_cells: list passed to RU update_cells (空 list 就 skip C.1)
            du_cells: list passed to DU MAC replace_cells (空 list 就 skip C.3)
            ru_ue_payload: list[{id, position{x,y,z}}] 給 RU update_ues
            ue_names: list[str] 給 DU replace_ues + CU release_stale 當 keep list
            clear_stale_ues: 是否在 C.2 帶 clear_stale=True(第一次 setup 用)
            context: log prefix(例如 scenario_id 或 "editor"),純記錄用

        Returns:
            {
              "applied": ["C.1", "C.2", ...],
              "errors": [{"step": "C.x", "error": str}],
            }
        """
        prefix = f"[{context}] " if context else ""
        applied: list[str] = []
        errors: list[dict[str, str]] = []

        def _try(step: str, fn) -> None:
            try:
                fn()
                applied.append(step)
            except Exception as e:  # noqa: BLE001
                errors.append({"step": step, "error": str(e)})
                logger.warning("%sscene-apply %s failed: %s", prefix, step, e)

        # C.1 RU update_cells
        if ru_cells:
            _try("C.1 RU update_cells", lambda: ru_client.update_cells(ru_cells))

        # C.2 RU update_ues
        if ru_ue_payload:
            _try(
                "C.2 RU update_ues",
                lambda: ru_client.update_ues_batch(ru_ue_payload, clear_stale=clear_stale_ues),
            )

        # C.3 DU MAC replace_cells
        if du_cells:
            _try("C.3 DU MAC replace_cells", lambda: du_client.replace_cells(du_cells))

        # C.4 DU Tick replace_ues — empty list 也跑(清空 registry)
        _try("C.4 DU Tick replace_ues", lambda: du_client.replace_ues(ue_names))

        # C.5 CU release_stale
        _try("C.5 CU release_stale", lambda: cu_client.release_stale(ue_names, force=False))

        logger.info(
            "%sscene-apply done: applied=%d errors=%d (cells=%d ues=%d)",
            prefix, len(applied), len(errors), len(ru_cells), len(ue_names),
        )
        return {"applied": applied, "errors": errors}
