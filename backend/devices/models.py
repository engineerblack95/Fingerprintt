from django.db import models
from django.utils import timezone


class Device(models.Model):
    """A physical fingerprint terminal installed at a location."""

    device_id = models.CharField(max_length=100, unique=True)
    location_name = models.CharField(max_length=150)
    is_online = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["location_name", "device_id"]
        indexes = [
            models.Index(fields=["is_online"]),
            models.Index(fields=["last_seen_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.location_name} ({self.device_id})"

    def mark_seen(self) -> None:
        self.is_online = True
        self.last_seen_at = timezone.now()
        self.save(update_fields=["is_online", "last_seen_at", "updated_at"])
