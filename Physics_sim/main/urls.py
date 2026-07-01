"""Top-level URL router — 鐵則 2-2：只做路由聚合，不寫業務邏輯。"""
from django.urls import include, path

urlpatterns = [
    path("api/v0.1/", include("main.apps.ran_signal.api.urls")),
    # scenario_store：physics_db 上的劇本/場景倉庫(鏡像 Omniverse RAN 端點)
    path("api/v0.1/", include("main.apps.scenario_store.api.urls")),
]
