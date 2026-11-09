from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from devices.models import Device


class Command(BaseCommand):
    help = "Mark devices offline when their last heartbeat is stale."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(
            seconds=settings.DEVICE_OFFLINE_AFTER_SECONDS
        )
        updated = Device.objects.filter(is_online=True, last_seen_at__lt=cutoff).update(
            is_online=False
        )
        self.stdout.write(self.style.SUCCESS(f"Marked {updated} device(s) offline."))
