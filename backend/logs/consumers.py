from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from .realtime import DASHBOARD_GROUP


class DashboardConsumer(AsyncJsonWebsocketConsumer):
    """Authenticated WebSocket feed for the owner dashboard."""

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        await self.channel_layer.group_add(DASHBOARD_GROUP, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "type": "connection_established",
                "user": {"username": user.username},
                "timestamp": timezone.now().isoformat(),
            }
        )

    async def disconnect(self, code):
        await self.channel_layer.group_discard(DASHBOARD_GROUP, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if isinstance(content, dict) and content.get("type") == "ping":
            await self.send_json(
                {"type": "pong", "timestamp": timezone.now().isoformat()}
            )

    async def entry_event(self, event):
        await self.send_json(event["payload"])
