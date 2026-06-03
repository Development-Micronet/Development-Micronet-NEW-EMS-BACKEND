"""
ASGI config for horilla project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/asgi/
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")

from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from notifications.middleware import JWTAuthenticationMiddleware
from notifications.routing import websocket_urlpatterns


def NotificationAuthMiddlewareStack(inner):
    return AuthMiddlewareStack(JWTAuthenticationMiddleware(inner))


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            NotificationAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
