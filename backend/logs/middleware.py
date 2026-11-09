import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)


@database_sync_to_async
def _get_user(user_id):
    from accounts.models import User

    try:
        return User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Authenticate WebSocket connections with a JWT passed as ?token=... .

    Browsers cannot set custom headers on a WebSocket handshake, so the access
    token is supplied as a query parameter. Always use wss:// in production.
    """

    async def __call__(self, scope, receive, send):
        token = None
        query = parse_qs(scope.get("query_string", b"").decode())
        if query.get("token"):
            token = query["token"][0]

        scope["user"] = AnonymousUser()
        if token:
            try:
                validated = AccessToken(token)
                user_id = validated[api_settings.USER_ID_CLAIM]
                scope["user"] = await _get_user(user_id)
            except (TokenError, KeyError):
                logger.info("Rejected WebSocket connection with invalid JWT.")

        return await super().__call__(scope, receive, send)
