import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from notifications.realtime import (
    get_notification_snapshot,
    notification_group_name,
)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return

        self.user = user
        self.group_name = notification_group_name(user.id)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._send_snapshot()
        await self.send_json({"type": "connection_established", "user_id": user.id})

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if text_data is None:
            return

        if text_data == "ping":
            await self.send_json({"type": "pong"})
            return

        if text_data == "refresh":
            await self._send_snapshot()
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = payload.get("type") or payload.get("action")
        if action == "ping":
            await self.send_json({"type": "pong"})
        elif action == "refresh":
            await self._send_snapshot()

    async def notification_snapshot(self, event):
        await self.send_json(event["payload"])

    async def _send_snapshot(self):
        snapshot = await database_sync_to_async(get_notification_snapshot)(self.user)
        await self.send_json(snapshot)
