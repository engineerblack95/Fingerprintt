import base64
import logging

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from logs.models import EntryLog
from logs.serializers import EntryLogSerializer
from logs.services import record_entry
from members.crypto import InvalidToken, decrypt_template
from members.models import FingerprintTemplate

from .authentication import DeviceAPIKeyAuthentication, IsDeviceAuthenticated
from .models import Device
from .serializers import (
    DeviceEventSerializer,
    DeviceSerializer,
    HeartbeatSerializer,
    TemplateSyncQuerySerializer,
)

logger = logging.getLogger(__name__)


class DeviceEventView(APIView):
    """POST /api/device/event/ - device reports a local match result."""

    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = [IsDeviceAuthenticated]

    def post(self, request):
        serializer = DeviceEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        log = record_entry(
            device=data["device"],
            status=data["status"],
            member=data["member"],
            timestamp=data["timestamp"],
            synced_from_device=data["synced_from_device"],
        )

        return Response(
            EntryLogSerializer(log).data, status=status.HTTP_201_CREATED
        )


class DeviceHeartbeatView(APIView):
    """POST /api/device/heartbeat/ - device reports that it is alive."""

    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = [IsDeviceAuthenticated]

    def post(self, request):
        serializer = HeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = Device.objects.filter(
            device_id=serializer.validated_data["device_id"]
        ).first()
        if device is None:
            return Response(
                {"detail": "Unknown device_id. Register the device first."},
                status=status.HTTP_404_NOT_FOUND,
            )
        device.mark_seen()
        return Response(
            {
                "status": "ok",
                "device_id": device.device_id,
                "server_time": timezone.now().isoformat(),
            }
        )


class DeviceTemplateSyncView(APIView):
    """GET /api/device/templates/sync/ - fetch latest templates for local matching.

    Templates are decrypted only in memory and sent over the authenticated
    channel. They are base64-encoded binary templates - never images.
    """

    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = [IsDeviceAuthenticated]

    def get(self, request):
        query = TemplateSyncQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        device = Device.objects.filter(device_id=data["device_id"]).first()
        if device is None:
            return Response(
                {"detail": "Unknown device_id. Register the device first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        queryset = FingerprintTemplate.objects.select_related("member").filter(
            member__is_active=True
        )
        since = data.get("since")
        if since:
            queryset = queryset.filter(updated_at__gt=since)

        templates = []
        synced_ids = []
        failed = 0
        for template in queryset:
            try:
                raw = decrypt_template(template.template_data)
            except (InvalidToken, ValueError):
                failed += 1
                logger.error(
                    "Could not decrypt fingerprint template %s for member %s",
                    template.pk,
                    template.member_id,
                )
                continue

            templates.append(
                {
                    "template_id": template.pk,
                    "member_id": template.member_id,
                    "username": template.member.username,
                    "full_name": template.member.full_name,
                    "role": template.member.role,
                    "template_data": base64.b64encode(raw).decode("ascii"),
                    "updated_at": template.updated_at.isoformat(),
                }
            )
            synced_ids.append(template.pk)

        now = timezone.now()
        if synced_ids:
            FingerprintTemplate.objects.filter(pk__in=synced_ids).update(
                sync_status=FingerprintTemplate.SyncStatus.SYNCED,
                last_synced_at=now,
                updated_at=now,
            )

        device.mark_seen()

        return Response(
            {
                "count": len(templates),
                "failed": failed,
                "server_time": now.isoformat(),
                "templates": templates,
            }
        )


class DeviceViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/devices/ - dashboard list of installed devices."""

    permission_classes = [IsAuthenticated]
    serializer_class = DeviceSerializer
    queryset = Device.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(location_name__icontains=search) | Q(device_id__icontains=search)
            )
        return queryset
