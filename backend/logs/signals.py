from django.db.models.signals import post_save
from django.dispatch import receiver

from logs.models import EntryLog
from notifications.dispatch import queue_entry_notification


@receiver(post_save, sender=EntryLog)
def notify_owner_of_new_entry(sender, instance: EntryLog, created: bool, raw: bool = False, **kwargs):
    """Alert the owner for every newly created access event.

    This covers all creation paths - the device API (``record_entry``), the
    Django admin, management commands and the shell - so a log can never be
    recorded without the matching email being queued.
    """
    if not created or raw:
        return
    queue_entry_notification(instance.pk)
