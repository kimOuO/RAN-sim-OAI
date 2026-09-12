"""WebSocket consumers — E2 Indication push channel。

對齊 OAI E2AP RIC Indication（OAI 用 SCTP，我們用 WebSocket 取代）。

xApp 流程：
  1. POST /api/v0.1/CU/E2/Subscription/create  → 拿到 subscription_id
  2. ws.connect(/ws/v0.1/CU/E2/indication)
  3. ws.send({"subscribe": subscription_id})
  4. 收 server 持續推來的 indication 訊息
  5. ws.close 時 server 自動 unbind

OAI ref:
  - openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_kpm.c (indication 產生)
  - 真機是 SCTP push；我們用 WS 對應「server-pushed message」語意
"""
from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from main.apps.cu_cp.services.optional.e2.subscription_registry import get_store
from main.utils.logger import get_logger


logger = get_logger(__name__)


class E2IndicationConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for E2 Indication push.

    State 機器：
      [connected] → 等 client 送 {"subscribe": sub_id}
                    → register 進 store → [subscribed]
      [subscribed] → background producer 透過 self.send_json(indication) 推
                     收到 client {"unsubscribe"} 或 disconnect → unbind
    """

    async def connect(self):
        await self.accept()
        self._sub_id: str | None = None

    async def disconnect(self, code):
        get_store().remove_ws_consumer(self)
        if self._sub_id:
            logger.info("E2 WS disconnected sub=%s code=%s", self._sub_id, code)

    async def receive_json(self, content, **kwargs):
        # client → server 的訊息
        if "subscribe" in content:
            sub_id = content["subscribe"]
            ok = get_store().add_ws_consumer(sub_id, self)
            if not ok:
                await self.send_json({
                    "type": "error",
                    "message": f"unknown subscription_id {sub_id}. Create via POST /E2/Subscription/create first.",
                })
                await self.close(code=4404)
                return
            self._sub_id = sub_id
            await self.send_json({
                "type": "subscribed",
                "subscription_id": sub_id,
            })
            logger.info("E2 WS bound to sub=%s", sub_id)
        elif content.get("unsubscribe"):
            get_store().remove_ws_consumer(self)
            await self.send_json({"type": "unsubscribed"})
            await self.close()

    async def push_indication(self, indication: dict) -> None:
        """Producer task 呼這個。直接送 indication frame 給 client。"""
        try:
            await self.send_json({
                "type": "indication",
                **indication,
            })
        except Exception as e:
            logger.warning("E2 WS push failed sub=%s: %s", self._sub_id, e)
