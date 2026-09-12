"""Cell 配置 Actor — CU 透過 ue_context_setup 流程觸發,亦可由本端 admin 直配。"""
from __future__ import annotations

import json

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.mac.models.cell_state import CellState
from main.apps.mac.serializers.cell_state_serializers import (
    CellStateListWriteSerializer,
    CellStateReadSerializer,
    CellStateWriteSerializer,
)
from main.apps.mac.services.business.relational_db_operations import RelationalDbBusinessService
from main.apps.mac.services.common.timestamp_service import TimestampService
from main.apps.mac.services.common.uuid_service import UUIDService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class MacCellController:
    """Component name in URL: /api/v0.1/DU/MAC/MacCellController/<element>"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def create(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        ser = CellStateWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)

        validated = dict(ser.validated_data)
        cell_uuid = UUIDService.generate_uuid("cell", validated["cell_id"])
        ts = TimestampService.now_ms()

        entity_data = {
            "cell_uuid": cell_uuid,
            "cell_created_at": ts,
            "cell_updated_at": ts,
            **validated,
        }

        try:
            obj, created = _upsert_with_created_flag(CellState, "cell_uuid", cell_uuid, entity_data)
        except Exception as e:
            logger.exception("Cell create failed")
            return error_response(f"Cell create failed: {e}", http_status=500)

        # F1 active 後新增 / 修改 cell → 通知 CU(F1 還在 INIT 時 skip,F1Setup 會帶過去)
        from main.apps.f1ap_du.services.optional.lifecycle import du_config_update
        cfg = du_config_update.cell_state_to_config(obj)
        if created:
            du_config_update.send(cells_to_add=[cfg])
        else:
            du_config_update.send(cells_to_modify=[cfg])

        out = CellStateReadSerializer(obj.__dict__).data
        logger.info(
            "MacCellController.create cell_id=%s pci=%s (created=%s)", obj.cell_id, obj.pci, created,
        )
        return success_response(out, "Cell created", http_status=201)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        cell_id = payload.get("cell_id")
        if cell_id:
            obj = RelationalDbBusinessService.get_entity(CellState, "cell_id", cell_id)
            if not obj:
                return error_response("Cell not found", http_status=404)
            return success_response(CellStateReadSerializer(obj.__dict__).data, "OK")

        rows = RelationalDbBusinessService.list_entities(CellState)
        data = [CellStateReadSerializer(r.__dict__).data for r in rows]
        return success_response(data, "OK")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def replace_cells(request):
        """全量替換 — 接收 {cells: [...]}，把 incoming 不在的舊 cell 刪掉，再 upsert。

        Dashboard Start Sim 用這個推完整 cell list 給 DU；
        對應 RU `update_cells` 的 pattern。Cell 增減同步觸發 du_config_update。
        """
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        ser = CellStateListWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)

        cells_in = ser.validated_data["cells"]
        if not cells_in:
            return error_response("cells must not be empty", http_status=400)

        ts = TimestampService.now_ms()
        incoming_ids = [c["cell_id"] for c in cells_in]

        # 1. 刪除不在 incoming list 的 cell
        stale_qs = CellState.objects.exclude(cell_id__in=incoming_ids)
        stale_cells = list(stale_qs)
        deleted_count = stale_qs.count()
        if deleted_count > 0:
            stale_qs.delete()
            logger.info("replace_cells: removed %d stale cells", deleted_count)

        # 2. upsert 每個 incoming
        from main.apps.f1ap_du.services.optional.lifecycle import du_config_update
        added, modified = [], []
        for c in cells_in:
            cell_uuid = UUIDService.generate_uuid("cell", c["cell_id"])
            entity_data = {
                "cell_uuid": cell_uuid,
                "cell_created_at": ts,
                "cell_updated_at": ts,
                **c,
            }
            obj, created = _upsert_with_created_flag(CellState, "cell_uuid", cell_uuid, entity_data)
            (added if created else modified).append(du_config_update.cell_state_to_config(obj))

        # 3. 通知 CU（F1 active 時才送，bootstrap 階段 skip）
        cells_to_delete = [du_config_update.cell_state_to_config(c) for c in stale_cells]
        if added or modified or cells_to_delete:
            du_config_update.send(
                cells_to_add=added or None,
                cells_to_modify=modified or None,
                cells_to_delete=cells_to_delete or None,
            )

        rows = list(CellState.objects.all())
        out = [CellStateReadSerializer(r.__dict__).data for r in rows]
        logger.info(
            "replace_cells ok: total=%d added=%d modified=%d deleted=%d",
            len(rows), len(added), len(modified), deleted_count,
        )
        return success_response(out, f"replaced cells: {len(rows)}", http_status=200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def disable(request):
        """關掉 cell（energy saving xApp 用）。

        body: {"cell_id": "..."}
        效果：CellState.is_active = False；通知 CU via gNB-DU Config Update；
              tick driver 跳過 inactive cell 不發 FAPI。
        """
        return _set_cell_active(request, active=False)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def enable(request):
        """重新啟用 cell。"""
        return _set_cell_active(request, active=True)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def update(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        cell_id = payload.pop("cell_id", None)
        if not cell_id:
            return error_response("cell_id is required", http_status=400)

        payload["cell_updated_at"] = TimestampService.now_ms()
        rows = RelationalDbBusinessService.update_entity(
            CellState, "cell_id", cell_id, payload,
        )
        if rows:
            from main.apps.f1ap_du.services.optional.lifecycle import du_config_update
            obj_for_notify = RelationalDbBusinessService.get_entity(CellState, "cell_id", cell_id)
            if obj_for_notify:
                du_config_update.send(
                    cells_to_modify=[du_config_update.cell_state_to_config(obj_for_notify)],
                )
        if rows == 0:
            return error_response("Cell not found", http_status=404)
        obj = RelationalDbBusinessService.get_entity(CellState, "cell_id", cell_id)
        return success_response(CellStateReadSerializer(obj.__dict__).data, "Updated")


def _upsert_with_created_flag(model_class, lookup_field, lookup_value, data):
    """upsert + 回傳 (obj, was_created)。Business Service 通用 API 不暴露 created flag。"""
    obj, created = model_class.objects.update_or_create(
        **{lookup_field: lookup_value}, defaults=data,
    )
    return obj, created


def _set_cell_active(request, *, active: bool):
    """Toggle CellState.is_active 並通知 CU（cells_to_modify 路徑）。

    對齊 OAI / 3GPP 並沒有真正的 cell on/off 訊號 — 我們用 gNB-DU Configuration Update
    cells_to_modify 把新狀態（含 is_active flag）推給 CU，最接近的對齊 procedure。
    """
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError as e:
        return error_response("Invalid JSON", str(e), http_status=400)

    cell_id = payload.get("cell_id")
    if not cell_id:
        return error_response("cell_id required", http_status=400)

    obj = CellState.objects.filter(cell_id=cell_id).first()
    if obj is None:
        return error_response(f"cell_id {cell_id} not found", http_status=404)

    if obj.is_active == active:
        return success_response(
            CellStateReadSerializer(obj.__dict__).data,
            f"cell_id {cell_id} already {'active' if active else 'inactive'}",
        )

    obj.is_active = active
    obj.cell_updated_at = TimestampService.now_ms()
    obj.save(update_fields=["is_active", "cell_updated_at"])

    # 通知 CU（F1 active 時才送）
    from main.apps.f1ap_du.services.optional.lifecycle import du_config_update
    cfg = du_config_update.cell_state_to_config(obj)
    du_config_update.send(cells_to_modify=[cfg])

    logger.info(
        "MacCellController.%s cell_id=%s pci=%s",
        "enable" if active else "disable",
        obj.cell_id, obj.pci,
    )
    return success_response(
        CellStateReadSerializer(obj.__dict__).data,
        f"cell_id {cell_id} {'enabled' if active else 'disabled'}",
    )
