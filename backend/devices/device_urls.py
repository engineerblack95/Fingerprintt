from django.urls import path

from .views import DeviceEventView, DeviceHeartbeatView, DeviceTemplateSyncView

app_name = "device_api"

urlpatterns = [
    path("event/", DeviceEventView.as_view(), name="event"),
    path("templates/sync/", DeviceTemplateSyncView.as_view(), name="templates-sync"),
    path("heartbeat/", DeviceHeartbeatView.as_view(), name="heartbeat"),
]
