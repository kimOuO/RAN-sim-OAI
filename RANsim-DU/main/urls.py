"""路由聚合 — 嚴禁業務邏輯 (rule §3-2-2)。

URL 格式: /api/v0.1/DU/{Module}/{Component}/{Element}
"""
from django.urls import include, path

from main.services_logs.log_actor import LogActor

urlpatterns = [
    path("api/v0.1/DU/MAC/", include("main.apps.mac.api.urls")),
    path("api/v0.1/DU/RLC/", include("main.apps.rlc.api.urls")),
    path("api/v0.1/DU/PHY/", include("main.apps.phy_high.api.urls")),
    path("api/v0.1/DU/F1AP/", include("main.apps.f1ap_du.api.urls")),
    path("api/v0.1/DU/FAPI/", include("main.apps.fapi_north.api.urls")),
    path("api/v0.1/DU/Tick/", include("main.apps.tick.api.urls")),
    path("api/v0.1/DU/Logs/Ring/read", LogActor.read_ring, name="du_logs_ring"),
]
