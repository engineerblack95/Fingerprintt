from rest_framework import serializers

from members.utils import absolute_photo_url

from .models import EntryLog


class MemberBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    phone_number = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    role = serializers.CharField(read_only=True)
    photo_url = serializers.SerializerMethodField()

    def get_photo_url(self, obj) -> str | None:
        return absolute_photo_url(obj)


class DeviceBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    device_id = serializers.CharField(read_only=True)
    location_name = serializers.CharField(read_only=True)


class EntryLogSerializer(serializers.ModelSerializer):
    member = MemberBriefSerializer(read_only=True)
    device = DeviceBriefSerializer(read_only=True)

    class Meta:
        model = EntryLog
        fields = (
            "id",
            "status",
            "member",
            "hardware_slot",
            "device",
            "timestamp",
            "synced_from_device",
            "created_at",
        )
        read_only_fields = fields
