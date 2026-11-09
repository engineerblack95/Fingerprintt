from django.db import models
from django.db.models import Q
from django.utils import timezone

from devices.models import Device
from members.models import Member


class EntryLog(models.Model):
    """One access attempt reported by a device (the result of edge matching)."""

    class Status(models.TextChoices):
        MEMBER = "MEMBER", "Member"
        VISITOR = "VISITOR", "Visitor"
        UNKNOWN = "UNKNOWN", "Unknown / Intruder"

    member = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entry_logs",
        help_text="Null means the fingerprint did not match any registered profile.",
    )
    device = models.ForeignKey(
        Device, on_delete=models.PROTECT, related_name="entry_logs"
    )
    status = models.CharField(max_length=10, choices=Status.choices)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    synced_from_device = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["status", "timestamp"]),
            models.Index(fields=["device", "timestamp"]),
            models.Index(fields=["member", "timestamp"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(status__in=["MEMBER", "VISITOR"], member__isnull=False)
                    | Q(status="UNKNOWN", member__isnull=True)
                ),
                name="entrylog_member_matches_status",
            )
        ]

    def __str__(self) -> str:
        who = self.member.full_name if self.member else "Unknown person"
        return f"{who} @ {self.device.location_name} ({self.status})"
