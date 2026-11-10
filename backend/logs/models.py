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
        ENROLLED = "ENROLLED", "Hardware enrolled"

    member = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entry_logs",
        help_text=(
            "Null means the fingerprint did not match any registered profile, "
            "or the member was deleted after this event was recorded."
        ),
    )
    # Snapshots keep the audit trail readable after a member is deleted. The
    # foreign key above is SET_NULL, so these fields are the durable record of
    # who the event belonged to at the time it happened.
    member_name = models.CharField(max_length=150, blank=True, default="")
    member_username = models.CharField(max_length=64, blank=True, default="")
    member_role = models.CharField(max_length=10, blank=True, default="")
    device = models.ForeignKey(
        Device, on_delete=models.PROTECT, related_name="entry_logs"
    )
    status = models.CharField(max_length=10, choices=Status.choices)
    hardware_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text=(
            "AS608 fingerprint sensor slot (1-127) reported by the device for "
            "hardware enrollment events."
        ),
    )
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
                    # Unknown / enrollment events never reference a Member.
                    Q(status__in=["UNKNOWN", "ENROLLED"], member__isnull=True)
                    # Access events normally reference a Member...
                    | Q(status__in=["MEMBER", "VISITOR"], member__isnull=False)
                    # ...but the FK is SET_NULL, so after a member is deleted
                    # the snapshot fields keep the row valid and readable.
                    | Q(
                        status__in=["MEMBER", "VISITOR"],
                        member__isnull=True,
                        member_name__gt="",
                    )
                ),
                name="entrylog_member_matches_status",
            )
        ]

    @property
    def display_member_name(self) -> str:
        """Name to show in the UI, even after the linked member is deleted."""
        if self.member_id and self.member:
            return self.member.full_name
        return self.member_name or "Unknown person"

    def __str__(self) -> str:
        if self.status == self.Status.ENROLLED:
            return (
                f"Fingerprint enrolled (slot {self.hardware_slot}) "
                f"@ {self.device.location_name}"
            )
        who = self.display_member_name
        return f"{who} @ {self.device.location_name} ({self.status})"
