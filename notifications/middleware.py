from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication


def _get_header(scope, name):
    header_name = name.lower().encode("latin1")
    for key, value in scope.get("headers", []):
        if key == header_name:
            return value.decode("latin1")
    return None


def _get_query_param(scope, *keys):
    query_string = scope.get("query_string", b"").decode("utf-8")
    params = parse_qs(query_string)
    for key in keys:
        values = params.get(key)
        if values:
            return values[0]
    return None


def _get_subprotocols(scope):
    protocols_header = _get_header(scope, "sec-websocket-protocol")
    if not protocols_header:
        return []
    return [item.strip() for item in protocols_header.split(",") if item.strip()]


def _get_token_from_subprotocol(scope):
    protocols = _get_subprotocols(scope)
    if len(protocols) >= 2 and protocols[0].lower() in {"bearer", "token", "jwt"}:
        return protocols[1]
    return None


def _get_token(scope):
    auth_header = _get_header(scope, "authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()

    token = _get_query_param(scope, "token", "access_token", "access")
    if token:
        return token

    return _get_token_from_subprotocol(scope)


@database_sync_to_async
def _authenticate_from_token(raw_token):
    authenticator = JWTAuthentication()
    validated_token = authenticator.get_validated_token(raw_token)
    return authenticator.get_user(validated_token)


class JWTAuthenticationMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        raw_token = _get_token(scope)

        if raw_token:
            try:
                scope["user"] = await _authenticate_from_token(raw_token)
            except Exception:
                scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
