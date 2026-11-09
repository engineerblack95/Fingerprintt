import uuid
from pathlib import Path

from django.db import models
from django.utils import timezone


def member_photo_upload_to(instance, filename: str) -> str:
    extension = Path(filename).suffix.lower() or ".jpg"
    return f"members/{instance.username}/{uuid.uuid4().hex}{extension}"


class Member(models.Model):
    """A registered member of the household/organisation or a pre-enrolled visitor."""

    class Role(models.TextChoices):
        MEMBER = "MEMBER", "Member"
        VISITOR = "VISITOR", "Visitor"

    username = models.CharField(max_length=64, unique=True)
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=32)
    email = models.EmailField()
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    photo = models.ImageField(upload_to=member_photo_upload_to)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["role", "is_active"]),
            models.Index(fields=["email"]),
            models.Index(fields=["full_name"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.username})"

    @property
    def is_visitor(self) -> bool:
        return self.role == self.Role.VISITOR


class FingerprintTemplate(models.Model):
    """Encrypted fingerprint template. Raw images are never stored."""

    class SyncStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SYNCED = "SYNCED", "Synced"

    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="fingerprints"
    )
    template_data = models.BinaryField()
    sync_status = models.CharField(
        max_length=10, choices=SyncStatus.choices, default=SyncStatus.PENDING
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["member", "sync_status"]),
            models.Index(fields=["sync_status"]),
        ]

    def __str__(self) -> str:
        return f"Template #{self.pk} for {self.member.full_name} ({self.sync_status})"

    def mark_synced(self) -> None:
        self.sync_status = self.SyncStatus.SYNCED
        self.last_synced_at = timezone.now()
        self.save(update_fields=["sync_status", "last_synced_at", "updated_at"])
