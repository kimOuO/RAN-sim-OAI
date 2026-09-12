"""URL: /api/v0.1/DU/MAC/<Component>/<Element>"""
from django.urls import path

from main.apps.mac.actors.cell_actor import MacCellController
from main.apps.mac.actors.harq_actor import MacHarqController
from main.apps.mac.actors.scheduler_actor import MacSchedulerController
from main.apps.mac.actors.ue_state_actor import MacUeStateController

urlpatterns = [
    path("MacCellController/create", MacCellController.create, name="mac_cell_create"),
    path("MacCellController/read", MacCellController.read, name="mac_cell_read"),
    path("MacCellController/update", MacCellController.update, name="mac_cell_update"),
    path("MacCellController/replace_cells", MacCellController.replace_cells, name="mac_cell_replace_cells"),
    path("MacCellController/disable", MacCellController.disable, name="mac_cell_disable"),
    path("MacCellController/enable", MacCellController.enable, name="mac_cell_enable"),
    path("MacUeStateController/read", MacUeStateController.read, name="mac_ue_read"),
    path("MacHarqController/read", MacHarqController.read, name="mac_harq_read"),
    # per-scenario 物理參數(inter-freq / discard / tx_power)— 劇本 start 套用,免 DU 專用 env
    path("MacScheduler/set_runtime_phys", MacSchedulerController.set_runtime_phys, name="mac_sched_set_phys"),
    path("MacScheduler/get_runtime_phys", MacSchedulerController.get_runtime_phys, name="mac_sched_get_phys"),
    # PRB quota — for xApp E2 control style 2 / action 6
    path("MacScheduler/set_prb_quota", MacSchedulerController.set_prb_quota, name="mac_sched_set_quota"),
    path("MacScheduler/clear_prb_quota", MacSchedulerController.clear_prb_quota, name="mac_sched_clear_quota"),
    path("MacScheduler/list_prb_quota", MacSchedulerController.list_prb_quota, name="mac_sched_list_quota"),
]
