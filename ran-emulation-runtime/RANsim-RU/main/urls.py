"""Top-level URL router — backend_rule §2-2：只做路由聚合，不寫業務邏輯。

URL 格式（§7-1）：/api/{version}/{System}/{Module}/{Component}/{Element}
本專案 {System} = RU。{Module} 由各 app 的 api/urls.py 自帶。
"""
from django.urls import include, path

from main.services_logs.log_actor import LogActor

urlpatterns = [
    path("api/v0.1/RU/Config/",   include("main.apps.antenna.api.urls")),
    path("api/v0.1/RU/Beamform/", include("main.apps.beamforming.api.urls")),
    path("api/v0.1/RU/Physics/",  include("main.apps.physics_client.api.urls")),
    path("api/v0.1/RU/FAPI/",     include("main.apps.fapi_south.api.urls")),
    path("api/v0.1/RU/State/",    include("main.apps.phy_low.api.urls")),
    path("api/v0.1/RU/Logs/Ring/read", LogActor.read_ring, name="ru_logs_ring"),
]
