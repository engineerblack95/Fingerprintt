from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone


def is_device_online(device, now=None) -> bool:
    """A device is online when it has been seen within the configured window."""
    if device is None or device.last_seen_at is None:
        return False
    now = now or timezone.now()
    return device.last_seen_at >= now - timedelta(
        seconds=settings.DEVICE_OFFLINE_AFTER_SECONDS
    )


def online_devices_q(now=None) -> Q:
    now = now or timezone.now()
    return Q(
        last_seen_at__gte=now
        - timedelta(seconds=settings.DEVICE_OFFLINE_AFTER_SECONDS)
    )
