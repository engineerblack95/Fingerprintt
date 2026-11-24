"""Root URL configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.cache import never_cache

from notifications.views import EmailStatusView, EmailTestView

admin.site.site_header = "Fingerprint Access Control"
admin.site.site_title = "Fingerprint Access Control"
admin.site.index_title = "Administration"


@never_cache
def health(request):
    """Unauthenticated liveness probe with the deployed build identifier.

    Render injects ``RENDER_GIT_COMMIT``/``RENDER_GIT_BRANCH``. Exposing only
    the short commit hash and whether email can send makes it possible to
    confirm *which* code is live without revealing any secret.
    """
    commit = (settings.GIT_COMMIT or "")[:7] or "dev"
    backend = settings.EMAIL_BACKEND or ""
    if "brevo_api" in backend:
        email_configured = bool(settings.BREVO_API_KEY)
    else:
        email_configured = not backend.endswith("console.EmailBackend")
    return JsonResponse(
        {
            "status": "ok",
            "commit": commit,
            "branch": settings.GIT_BRANCH or "local",
            "email_backend": backend.rsplit(".", 1)[-1],
            "email_configured": email_configured,
            "frontend_url": settings.FRONTEND_URL,
        }
    )


urlpatterns = [
    path("api/health/", health, name="health"),
    path(
        "api/notifications/status/",
        EmailStatusView.as_view(),
        name="email-status",
    ),
    path(
        "api/notifications/test/",
        EmailTestView.as_view(),
        name="email-test",
    ),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("members.urls")),
    path("api/", include("devices.urls")),
    path("api/", include("logs.urls")),
    path("api/device/", include("devices.device_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
