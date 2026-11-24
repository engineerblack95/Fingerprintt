"""ASGI entry point: HTTP through Django, WebSockets through Channels."""

import os
from urllib.parse import urlparse

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialise Django before importing anything that touches models.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import OriginValidator  # noqa: E402
from django.conf import settings  # noqa: E402

from logs.middleware import JWTAuthMiddleware  # noqa: E402
from logs.routing import websocket_urlpatterns  # noqa: E402


def _origin(url: str) -> str:
    parsed = urlparse(url or "")
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _allowed_ws_origins() -> list[str]:
    """Origins allowed to open the dashboard WebSocket.

    ``AllowedHostsOriginValidator`` compares against ALLOWED_HOSTS without the
    scheme, which rejects the Vercel dashboard (its host is not the API host).
    An explicit origin list accepts both the deployed frontend and local Vite
    development servers, and keeps the endpoint closed to everything else.
    """
    origins = {
        _origin(getattr(settings, "FRONTEND_URL", "")),
        _origin(getattr(settings, "PUBLIC_BASE_URL", "")),
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        # Known production deployments, kept as a safety net if an environment
        # variable is missing or still points at localhost.
        "https://fingerprintt.vercel.app",
        "https://fingerprint-backend-7032.onrender.com",
    }
    origins.update(
        _origin(url) for url in getattr(settings, "CORS_ALLOWED_ORIGINS", [])
    )
    origins.discard("")
    return sorted(origins)


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": OriginValidator(
            JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
            _allowed_ws_origins(),
        ),
    }
)
