import secrets

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission


class DevicePrincipal:
    """Lightweight authenticated principal for a hardware device.

    Devices are not Django users; they authenticate with a shared API key and
    identify themselves with ``device_id`` in each request.
    """

    is_authenticated = True
    is_anonymous = False
    is_active = True

    def __str__(self) -> str:
        return "device"


class DeviceAPIKeyAuthentication(BaseAuthentication):
    """Authenticate hardware requests via the X-Device-API-Key header."""

    def authenticate(self, request):
        provided = request.headers.get("X-Device-API-Key")
        if not provided:
            return None
        expected = settings.DEVICE_API_KEY
        if not expected or not secrets.compare_digest(provided, expected):
            raise AuthenticationFailed("Invalid device API key.")
        return (DevicePrincipal(), None)

    def authenticate_header(self, request):
        return "X-Device-API-Key"


class IsDeviceAuthenticated(BasePermission):
    message = "A valid X-Device-API-Key header is required."

    def has_permission(self, request, view):
        return isinstance(request.user, DevicePrincipal)
