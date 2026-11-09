import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from members.utils import absolute_photo_url

logger = logging.getLogger(__name__)

DASHBOARD_GROUP = "dashboard"


def build_entry_payload(log) -> dict:
    """The exact event shape consumed by the React dashboard."""
    member = None
    if log.member_id and log.member:
        member = {
            "full_name": log.member.full_name,
            "phone_number": log.member.phone_number,
            "email": log.member.email,
            "photo_url": absolute_photo_url(log.member),
        }
    return {
        "type": "entry_event",
        "id": log.pk,
        "status": log.status,
        "member": member,
        "hardware_slot": log.hardware_slot,
        "device": {"location_name": log.device.location_name},
        "timestamp": log.timestamp.isoformat(),
    }


def broadcast_entry(log) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("No channel layer configured; entry event was not broadcast.")
        return
    async_to_sync(channel_layer.group_send)(
        DASHBOARD_GROUP,
        {"type": "entry_event", "payload": build_entry_payload(log)},
    )
