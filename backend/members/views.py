from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import FingerprintTemplate, Member
from .serializers import (
    EnrollSerializer,
    MemberSerializer,
    MemberWriteSerializer,
)


class MemberViewSet(viewsets.ModelViewSet):
    """Owner-facing CRUD for registered members and visitors."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = Member.objects.prefetch_related("fingerprints").all()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return MemberWriteSerializer
        return MemberSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        role = params.get("role")
        if role:
            queryset = queryset.filter(role=role.upper())

        is_active = params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() in {"1", "true", "yes"})

        search = params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(phone_number__icontains=search)
            )
        return queryset

    def create(self, request, *args, **kwargs):
        write = self.get_serializer(data=request.data)
        write.is_valid(raise_exception=True)
        member = write.save()
        read = MemberSerializer(member, context={"request": request})
        return Response(read.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write = self.get_serializer(instance, data=request.data, partial=partial)
        write.is_valid(raise_exception=True)
        member = write.save()
        read = MemberSerializer(member, context={"request": request})
        return Response(read.data)

    @action(detail=True, methods=["post"], url_path="enroll")
    def enroll(self, request, pk=None):
        """Queue (or upload) a fingerprint template for the next device sync."""
        member = self.get_object()
        serializer = EnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template, created = serializer.save_for_member(member)

        detail = (
            "New fingerprint template stored and queued for device sync."
            if created
            else "Existing fingerprint templates queued for device sync."
        )
        return Response(
            {
                "detail": detail,
                "template_id": template.id if template else None,
                "member": MemberSerializer(member, context={"request": request}).data,
            }
        )

    @action(detail=True, methods=["get"], url_path="fingerprints")
    def fingerprints(self, request, pk=None):
        """Status of the member's templates (never returns template bytes)."""
        member = self.get_object()
        templates = member.fingerprints.all()
        return Response(
            {
                "count": templates.count(),
                "pending": templates.filter(
                    sync_status=FingerprintTemplate.SyncStatus.PENDING
                ).count(),
                "synced": templates.filter(
                    sync_status=FingerprintTemplate.SyncStatus.SYNCED
                ).count(),
            }
        )
