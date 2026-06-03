from django.urls import path

from notifications.consumers import NotificationConsumer

websocket_urlpatterns = [
    path("ws/notifications", NotificationConsumer.as_asgi()),
    path("ws/notifications/", NotificationConsumer.as_asgi()),
    path("api/ws/notifications", NotificationConsumer.as_asgi()),
    path("api/ws/notifications/", NotificationConsumer.as_asgi()),
]
