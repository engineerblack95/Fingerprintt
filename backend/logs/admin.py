from django.contrib import admin

from .models import EntryLog


@admin.register(EntryLog)
class EntryLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "status",
        "member",
        "member_name",
        "hardware_slot",
        "device",
        "synced_from_device",
    )
    list_filter = ("status", "synced_from_device", "device")
    search_fields = (
        "member__full_name",
        "member__username",
        "member_name",
        "member_username",
        "device__location_name",
    )
    date_hierarchy = "timestamp"
    readonly_fields = ("created_at",)
    ordering = ("-timestamp",)
