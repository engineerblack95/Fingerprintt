from django.contrib import admin

from .models import Device


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("device_id", "location_name", "is_online", "last_seen_at", "created_at")
    list_filter = ("is_online",)
    search_fields = ("device_id", "location_name")
    readonly_fields = ("created_at", "updated_at")
