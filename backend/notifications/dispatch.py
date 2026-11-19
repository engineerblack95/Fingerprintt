"""
Single entry point for entry-log email alerts.

Every code path that creates an ``EntryLog`` (the device API, the Django admin,
management commands or a shell) must produce an owner alert. Rather than
repeating the call in each path, ``logs.signals`` hands new rows to
``queue_entry_notification`` which:

* waits for the surrounding transaction to commit (never emails about a row
  that was rolled back),
* delivers in a short-lived daemon thread so the hardware request returns
  instantly and a slow Brevo call cannot break or delay the device,
* records ``notification_sent_at`` so a row is never emailed twice,
* ignores hardware-enrollment events and back-filled history.
"""

import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_MAX_EVENT_AGE_MINUTES = 15


def _max_event_age() -> timedelta:
    minutes = int(
        getattr(
            settings,
            "EMAIL_MAX_EVENT_AGE_MINUTES",
            DEFAULT_MAX_EVENT_AGE_MINUTES,
        )
    )
    return timedelta(minutes=max(minutes, 1))


def queue_entry_notification(log_id: int) -> None:
    """Schedule an alert for ``log_id`` once the current transaction commits."""
    transaction.on_commit(lambda: _start_delivery_thread(log_id))


def _start_delivery_thread(log_id: int) -> None:
    thread = threading.Thread(
        target=_deliver,
        args=(log_id,),
        name=f"entry-email-{log_id}",
        daemon=True,
    )
    thread.start()


def _deliver(log_id: int) -> None:
    """Send the alert for one log row; safe to run in a worker thread."""
    from logs.models import EntryLog

    close_old_connections()
    claimed = False
    try:
        log = (
            EntryLog.objects.select_related("member", "device")
            .filter(pk=log_id)
            .first()
        )
        if log is None or log.notification_sent_at is not None:
            return

        if log.status == EntryLog.Status.ENROLLED:
            logger.info(
                "Skipping email for hardware enrollment log %s", log_id
            )
            return

        if log.timestamp < timezone.now() - _max_event_age():
            logger.info(
                "Skipping email for log %s: event is older than %s minutes "
                "(back-filled history, not a live alert).",
                log_id,
                _max_event_age().total_seconds() // 60,
            )
            return

        # Atomically claim the row before sending: the conditional UPDATE is
        # the only writer that can win, so concurrent deliveries (signal,
        # retries, multiple workers) can never send the same alert twice.
        claimed = (
            EntryLog.objects.filter(
                pk=log_id, notification_sent_at__isnull=True
            ).update(notification_sent_at=timezone.now())
            == 1
        )
        if not claimed:
            return

        from notifications.emails import send_entry_notification

        if not send_entry_notification(log):
            # Nothing was delivered (e.g. configuration missing); release the
            # claim so the alert can be retried once the issue is fixed.
            EntryLog.objects.filter(pk=log_id).update(notification_sent_at=None)
            claimed = False
    except Exception:  # pragma: no cover - alerting must never crash callers
        if claimed:
            EntryLog.objects.filter(pk=log_id).update(notification_sent_at=None)
        logger.exception("Failed to send entry notification for log %s", log_id)
    finally:
        close_old_connections()
