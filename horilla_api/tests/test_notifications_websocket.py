import asyncio
import json
from urllib.parse import urlsplit

from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.db import connections
from django.test import TransactionTestCase, override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from horilla.asgi import application
from notifications.realtime import notification_group_name


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    },
)
class NotificationWebsocketTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="socket-user",
            password="password",
            email="socket@example.com",
        )
        self.access_token = str(RefreshToken.for_user(self.user).access_token)

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def _build_communicator(self, raw_path, headers=None):
        parsed = urlsplit(raw_path)
        return ApplicationCommunicator(
            application,
            {
                "type": "websocket",
                "path": parsed.path,
                "query_string": parsed.query.encode("utf-8"),
                "headers": headers or [],
                "subprotocols": [],
                "client": ("127.0.0.1", 12345),
                "server": ("testserver", 80),
            },
        )

    def test_api_websocket_route_accepts_bearer_authorization_header(self):
        async def runner():
            communicator = self._build_communicator(
                "/api/ws/notifications/",
                headers=[
                    (b"host", b"testserver"),
                    (b"authorization", f"Bearer {self.access_token}".encode("utf-8")),
                ],
            )

            await communicator.send_input({"type": "websocket.connect"})
            response = await asyncio.wait_for(communicator.receive_output(), timeout=2)
            self.assertEqual(response["type"], "websocket.accept")

            snapshot_response = await asyncio.wait_for(
                communicator.receive_output(), timeout=2
            )
            snapshot = json.loads(snapshot_response["text"])
            self.assertEqual(snapshot["type"], "notification_snapshot")
            self.assertEqual(snapshot["unread_count"], 0)
            self.assertEqual(snapshot["all_count"], 0)

            confirmation_response = await asyncio.wait_for(
                communicator.receive_output(), timeout=2
            )
            confirmation = json.loads(confirmation_response["text"])
            self.assertEqual(confirmation["type"], "connection_established")
            self.assertEqual(confirmation["user_id"], self.user.id)

            await communicator.send_input({"type": "websocket.disconnect", "code": 1000})
            await communicator.wait()

        async_to_sync(runner)()

    def test_api_websocket_route_accepts_query_token_and_pushes_group_updates(self):
        async def runner():
            communicator = self._build_communicator(
                f"/api/ws/notifications/?token={self.access_token}",
                headers=[(b"host", b"testserver")],
            )

            await communicator.send_input({"type": "websocket.connect"})
            response = await asyncio.wait_for(communicator.receive_output(), timeout=2)
            self.assertEqual(response["type"], "websocket.accept")

            await asyncio.wait_for(communicator.receive_output(), timeout=2)
            await asyncio.wait_for(communicator.receive_output(), timeout=2)

            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                notification_group_name(self.user.id),
                {
                    "type": "notification.snapshot",
                    "payload": {
                        "type": "notification_snapshot",
                        "event": {"type": "notification_created"},
                        "unread_count": 1,
                        "all_count": 1,
                        "unread_list": [{"id": 99, "verb": "created"}],
                        "all_list": [{"id": 99, "verb": "created"}],
                    },
                },
            )
            pushed_response = await asyncio.wait_for(
                communicator.receive_output(), timeout=2
            )
            pushed = json.loads(pushed_response["text"])
            self.assertEqual(pushed["event"]["type"], "notification_created")
            self.assertEqual(pushed["unread_count"], 1)
            self.assertEqual(pushed["all_count"], 1)
            self.assertEqual(pushed["unread_list"][0]["id"], 99)

            await communicator.send_input({"type": "websocket.disconnect", "code": 1000})
            await communicator.wait()

        async_to_sync(runner)()

    def test_api_websocket_route_rejects_missing_authentication(self):
        async def runner():
            communicator = self._build_communicator(
                "/api/ws/notifications/",
                headers=[(b"host", b"testserver")],
            )

            await communicator.send_input({"type": "websocket.connect"})
            response = await asyncio.wait_for(communicator.receive_output(), timeout=2)
            self.assertEqual(response["type"], "websocket.close")
            self.assertEqual(response["code"], 4401)
            await communicator.wait()

        async_to_sync(runner)()
