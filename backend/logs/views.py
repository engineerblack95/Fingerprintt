from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate, ExtractHour
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from devices.models import Device
from devices.utils import online_devices_q
from members.models import Member

from .models import EntryLog
from .serializers import EntryLogSerializer


def _parse_date_filter(value: str, field: str, end_of_day: bool = False):
    """Accept ISO dates or ISO datetimes and return a (kind, value) tuple."""
    dt = parse_datetime(value)
    if dt is not None:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return "datetime", dt
    d = parse_date(value)
    if d is not None:
        return "date", d
    raise ValidationError(
        {field: "Use an ISO date (YYYY-MM-DD) or ISO datetime (2026-11-07T14:30:00)."}
    )


class EntryLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/logs/ - paginated history with status/date/device filters."""

    permission_classes = [IsAuthenticated]
    serializer_class = EntryLogSerializer
    queryset = EntryLog.objects.select_related("member", "device").all()

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        status_param = params.get("status", "").strip()
        if status_param:
            statuses = [item.strip().upper() for item in status_param.split(",") if item.strip()]
            valid = {choice for choice, _ in EntryLog.Status.choices}
            invalid = [item for item in statuses if item not in valid]
            if invalid:
                raise ValidationError(
                    {"status": f"Invalid status value(s): {', '.join(invalid)}."}
                )
            queryset = queryset.filter(status__in=statuses)

        date_from = params.get("date_from", "").strip()
        if date_from:
            kind, value = _parse_date_filter(date_from, "date_from")
            if kind == "date":
                queryset = queryset.filter(timestamp__date__gte=value)
            else:
                queryset = queryset.filter(timestamp__gte=value)

        date_to = params.get("date_to", "").strip()
        if date_to:
            kind, value = _parse_date_filter(date_to, "date_to", end_of_day=True)
            if kind == "date":
                queryset = queryset.filter(timestamp__date__lte=value)
            else:
                queryset = queryset.filter(timestamp__lte=value)

        device_id = params.get("device", "").strip()
        if device_id:
            if not device_id.isdigit():
                raise ValidationError({"device": "device must be a numeric device id."})
            queryset = queryset.filter(device_id=int(device_id))

        member_id = params.get("member", "").strip()
        if member_id:
            if not member_id.isdigit():
                raise ValidationError({"member": "member must be a numeric member id."})
            queryset = queryset.filter(member_id=int(member_id))

        synced = params.get("synced", "").strip().lower()
        if synced in {"true", "false"}:
            queryset = queryset.filter(synced_from_device=synced == "true")

        search = params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(member__full_name__icontains=search)
                | Q(member__username__icontains=search)
                | Q(device__location_name__icontains=search)
            )

        return queryset


class DashboardStatsView(APIView):
    """GET /api/dashboard/stats/ - counters plus chart-ready series."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tz = timezone.get_current_timezone()
        now = timezone.now()
        today = timezone.localdate(now)
        day_start = timezone.make_aware(datetime.combine(today, time.min), tz)
        day_end = day_start + timedelta(days=1)

        today_logs = EntryLog.objects.filter(
            timestamp__gte=day_start, timestamp__lt=day_end
        )

        status_counts = {choice: 0 for choice, _ in EntryLog.Status.choices}
        for row in today_logs.values("status").annotate(count=Count("id")):
            status_counts[row["status"]] = row["count"]

        trend_start_date = today - timedelta(days=6)
        trend_start = timezone.make_aware(
            datetime.combine(trend_start_date, time.min), tz
        )
        trend_rows = (
            EntryLog.objects.filter(
                timestamp__gte=trend_start, timestamp__lt=day_end
            )
            .annotate(day=TruncDate("timestamp", tzinfo=tz))
            .values("day", "status")
            .annotate(count=Count("id"))
        )
        buckets = {
            (trend_start_date + timedelta(days=offset)): {
                "date": (trend_start_date + timedelta(days=offset)).isoformat(),
                "members": 0,
                "visitors": 0,
                "unknowns": 0,
                "total": 0,
            }
            for offset in range(7)
        }
        for row in trend_rows:
            bucket = buckets.get(row["day"])
            if bucket is None:
                continue
            key = {
                EntryLog.Status.MEMBER: "members",
                EntryLog.Status.VISITOR: "visitors",
                EntryLog.Status.UNKNOWN: "unknowns",
            }[row["status"]]
            bucket[key] += row["count"]
            bucket["total"] += row["count"]

        hourly_counts = {hour: 0 for hour in range(24)}
        for row in (
            today_logs.annotate(hour=ExtractHour("timestamp", tzinfo=tz))
            .values("hour")
            .annotate(count=Count("id"))
        ):
            hourly_counts[int(row["hour"])] = row["count"]

        devices_total = Device.objects.count()
        devices_online = Device.objects.filter(online_devices_q(now)).count()

        return Response(
            {
                "date": today.isoformat(),
                "today": {
                    "total": sum(status_counts.values()),
                    "members": status_counts[EntryLog.Status.MEMBER],
                    "visitors": status_counts[EntryLog.Status.VISITOR],
                    "unknowns": status_counts[EntryLog.Status.UNKNOWN],
                },
                "totals": {
                    "members": Member.objects.filter(
                        role=Member.Role.MEMBER, is_active=True
                    ).count(),
                    "visitors": Member.objects.filter(
                        role=Member.Role.VISITOR, is_active=True
                    ).count(),
                    "registered": Member.objects.filter(is_active=True).count(),
                },
                "devices": {"total": devices_total, "online": devices_online},
                "status_distribution": [
                    {"status": choice, "count": status_counts[choice]}
                    for choice, _ in EntryLog.Status.choices
                ],
                "trend": list(buckets.values()),
                "hourly": [
                    {"hour": hour, "count": count}
                    for hour, count in hourly_counts.items()
                ],
                "server_time": now.isoformat(),
            }
        )
