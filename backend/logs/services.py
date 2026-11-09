import logging

from django.db import transaction
from django.utils import timezone

from devices.models import Device

from .models import EntryLog
from .realtime import broadcast_entry

logger = logging.getLogger(__name__)


def record_entry(
    *,
    device,
    status,
    member,
    timestamp,
    synced_from_device=False,
    hardware_slot=None,
) -> EntryLog:
    """Create the authoritative log row, then notify after the DB commit.

    WebSocket broadcast and email are side effects: failures are logged and
    never roll back the access record.
    """
    with transaction.atomic():
        log = EntryLog.objects.create(
            device=device,
            status=status,
            member=member,
            hardware_slot=hardware_slot,
            timestamp=timestamp,
            synced_from_device=synced_from_device,
        )
        Device.objects.filter(pk=device.pk).update(
            is_online=True,
            last_seen_at=timezone.now(),
            updated_at=timezone.now(),
        )

    transaction.on_commit(lambda: _dispatch(log.pk))
    return log


def _dispatch(log_id: int) -> None:
    log = (
        EntryLog.objects.select_related("member", "device")
        .filter(pk=log_id)
        .first()
    )
    if log is None:
        return

    try:
        broadcast_entry(log)
    except Exception:  # pragma: no cover - side-effect guard
        logger.exception("Failed to broadcast entry event %s", log_id)

    if log.status == EntryLog.Status.ENROLLED:
        logger.info(
            "New fingerprint enrolled on hardware for Member ID: %s",
            log.hardware_slot,
        )
        return

    try:
        from notifications.emails import send_entry_notification

        send_entry_notification(log)
    except Exception:  # pragma: no cover - side-effect guard
        logger.exception("Failed to send entry notification for log %s", log_id)
