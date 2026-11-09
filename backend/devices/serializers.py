from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from logs.models import EntryLog
from members.models import Member

from .models import Device
from .utils import is_device_online


class DeviceSerializer(serializers.ModelSerializer):
    is_online = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = (
            "id",
            "device_id",
            "location_name",
            "is_online",
            "last_seen_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_is_online(self, obj: Device) -> bool:
        return is_device_online(obj)


class DeviceEventSerializer(serializers.Serializer):
    """Validates the result payload posted by the edge device.

    The device performs matching locally. It only ever sends the *result* -
    never a fingerprint image or template.
    """

    device_id = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(choices=EntryLog.Status.choices)
    member_id = serializers.IntegerField(required=False, allow_null=True)
    timestamp = serializers.DateTimeField(required=False, allow_null=True)
    synced_from_device = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        now = timezone.now()
        status = attrs["status"]
        member_id = attrs.get("member_id")

        if status == EntryLog.Status.UNKNOWN:
            if member_id is not None:
                raise serializers.ValidationError(
                    {"member_id": "member_id must be null when status is UNKNOWN."}
                )
            member = None
        else:
            if member_id is None:
                raise serializers.ValidationError(
                    {"member_id": "member_id is required for MEMBER and VISITOR events."}
                )
            member = Member.objects.filter(pk=member_id).first()
            if member is None:
                raise serializers.ValidationError(
                    {"member_id": f"No member with id {member_id} exists."}
                )
            if not member.is_active:
                raise serializers.ValidationError(
                    {"member_id": "This member is deactivated and cannot enter."}
                )
            if member.role != status:
                raise serializers.ValidationError(
                    {
                        "status": (
                            f"Member #{member.id} is registered as {member.role}; "
                            f"the event status must be {member.role}."
                        )
                    }
                )

        device = Device.objects.filter(device_id=attrs["device_id"]).first()
        if device is None:
            raise serializers.ValidationError(
                {
                    "device_id": (
                        "Unknown device_id. Register the device in the admin "
                        "before sending events."
                    )
                }
            )

        timestamp = attrs.get("timestamp") or now
        if timestamp > now + timedelta(minutes=5):
            raise serializers.ValidationError(
                {"timestamp": "Event timestamp cannot be more than 5 minutes in the future."}
            )

        # Anything older than two minutes is treated as a buffered event that
        # the device is replaying after a network outage.
        buffered = (now - timestamp) > timedelta(minutes=2)
        attrs["synced_from_device"] = bool(
            attrs.get("synced_from_device") or buffered
        )
        attrs["timestamp"] = timestamp
        attrs["member"] = member
        attrs["device"] = device
        return attrs


class HeartbeatSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=100)


class TemplateSyncQuerySerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=100)
    since = serializers.DateTimeField(required=False, allow_null=True)
