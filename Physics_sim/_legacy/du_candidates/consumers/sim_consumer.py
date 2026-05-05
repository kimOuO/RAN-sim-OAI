from channels.generic.websocket import AsyncWebsocketConsumer


class SimConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("sim_live", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("sim_live", self.channel_name)

    async def sim_update(self, event):
        await self.send(text_data=event["text"])
