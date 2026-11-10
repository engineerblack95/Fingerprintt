import base64
import binascii
import logging
import urllib.error

import cloudinary.exceptions
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.db import transaction
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from .crypto import encrypt_template
from .models import FingerprintTemplate, Member
from .utils import absolute_photo_url

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class FingerprintSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = FingerprintTemplate
        fields = ("id", "sync_status", "last_synced_at", "created_at", "updated_at")
        read_only_fields = fields


class MemberSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    fingerprints = FingerprintSummarySerializer(many=True, read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    fingerprint_count = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = (
            "id",
            "username",
            "full_name",
            "phone_number",
            "email",
            "role",
            "role_display",
            "photo",
            "photo_url",
            "is_active",
            "fingerprint_count",
            "fingerprints",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "photo_url",
            "fingerprint_count",
            "fingerprints",
            "created_at",
            "updated_at",
        )

    def get_photo_url(self, obj: Member) -> str | None:
        return absolute_photo_url(obj)

    def get_fingerprint_count(self, obj: Member) -> int:
        return obj.fingerprints.count()


class MemberWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = (
            "username",
            "full_name",
            "phone_number",
            "email",
            "role",
            "photo",
            "is_active",
        )
        extra_kwargs = {
            "photo": {"required": True, "allow_null": False},
            # HTML multipart forms omit unchecked booleans, which DRF would
            # otherwise coerce to False. New people must be active by default.
            "is_active": {"required": False, "default": True},
        }

    # -- field validation -------------------------------------------------
    def validate_username(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Username is required.")
        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters.")
        if not all(char.isalnum() or char in "._-" for char in value):
            raise serializers.ValidationError(
                "Username may only contain letters, numbers, dots, underscores and hyphens."
            )
        qs = Member.objects.filter(username__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_full_name(self, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise serializers.ValidationError("Full name is too short.")
        if any(ord(char) < 32 for char in value):
            raise serializers.ValidationError("Full name contains invalid characters.")
        return value

    def validate_phone_number(self, value: str) -> str:
        value = value.strip()
        allowed = set("0123456789+ ()-")
        if len(value) < 7 or len(value) > 32 or any(char not in allowed for char in value):
            raise serializers.ValidationError(
                "Enter a valid phone number (7-32 digits, may include +, spaces, - or parentheses)."
            )
        return value

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def save(self, **kwargs):
        """Wrap storage/network failures of the photo upload as a clean 400.

        Django persists the file to storage before the database row, so a
        failed Cloudinary upload leaves no partial data behind.
        """
        try:
            return super().save(**kwargs)
        except (
            cloudinary.exceptions.Error,
            SuspiciousFileOperation,
            OSError,
            urllib.error.URLError,
        ) as exc:
            logger.exception("Photo upload failed while saving a member.")
            raise serializers.ValidationError(
                {
                    "photo": (
                        "The photo could not be uploaded to storage. "
                        "Please try again with a JPEG, PNG or WEBP image."
                    )
                }
            ) from exc

    def validate_photo(self, photo):
        if photo is None:
            return photo
        if photo.size > settings.MAX_PHOTO_BYTES:
            raise serializers.ValidationError(
                f"Photo must be smaller than {settings.MAX_PHOTO_BYTES // (1024 * 1024)} MB."
            )
        content_type = getattr(photo, "content_type", "")
        if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise serializers.ValidationError("Photo must be a JPEG, PNG or WEBP image.")
        try:
            image = Image.open(photo)
            image.verify()
            image_format = image.format
        except (UnidentifiedImageError, OSError, ValueError):
            raise serializers.ValidationError("The uploaded file is not a valid image.")
        finally:
            photo.seek(0)
        if image_format not in ALLOWED_IMAGE_FORMATS:
            raise serializers.ValidationError("Photo must be a JPEG, PNG or WEBP image.")
        return photo


class EnrollSerializer(serializers.Serializer):
    """Optional raw template supplied by the enrollment station.

    When ``template_data`` is omitted the existing templates are simply queued
    for the next device sync. ``template_data`` must be base64 of the *template*
    (never a fingerprint image); it is encrypted before it touches the database.
    """

    template_data = serializers.CharField(required=False, allow_blank=False)

    def validate_template_data(self, value: str) -> str:
        try:
            raw = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise serializers.ValidationError("template_data must be valid base64.")
        if not raw:
            raise serializers.ValidationError("template_data is empty.")
        if len(raw) > settings.MAX_TEMPLATE_BYTES:
            raise serializers.ValidationError(
                f"Template is too large (limit {settings.MAX_TEMPLATE_BYTES} bytes)."
            )
        return value

    def save_for_member(self, member: Member):
        template_data = self.validated_data.get("template_data")
        with transaction.atomic():
            if template_data:
                raw = base64.b64decode(template_data, validate=True)
                template = FingerprintTemplate.objects.create(
                    member=member,
                    template_data=encrypt_template(raw),
                    sync_status=FingerprintTemplate.SyncStatus.PENDING,
                )
                return template, True

            templates = member.fingerprints.all()
            if not templates.exists():
                raise serializers.ValidationError(
                    {
                        "template_data": (
                            "This member has no fingerprint template yet. Capture one on "
                            "the device and send it as base64 template_data, or enroll the "
                            "member directly on the device first."
                        )
                    }
                )
            templates.update(
                sync_status=FingerprintTemplate.SyncStatus.PENDING,
                last_synced_at=None,
            )
            return None, False
