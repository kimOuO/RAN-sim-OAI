import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.local")

# NOTE (restructure/4-system-split):
#   ws/sim/live/ WebSocket consumer 已搬到 _legacy/du_candidates/consumers/
#   原因：DU 才是 tick driver / KPI broadcaster。Physics 不需要 WebSocket。
#   此 asgi.py 只保留 HTTP，未來若 Physics 需要 push 通知（例如場景變更）再加。

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
})
