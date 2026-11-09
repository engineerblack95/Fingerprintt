from django.contrib import admin

from .models import FingerprintTemplate, Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("username", "full_name", "role", "email", "phone_number", "is_active", "created_at")
    list_filter = ("role", "is_active", "created_at")
    search_fields = ("username", "full_name", "email", "phone_number")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(FingerprintTemplate)
class FingerprintTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "member", "sync_status", "last_synced_at", "created_at")
    list_filter = ("sync_status",)
    search_fields = ("member__full_name", "member__username")
    readonly_fields = ("template_data", "created_at", "updated_at", "last_synced_at")

    def has_add_permission(self, request):
        # Templates are only created through the enrollment API.
        return False
