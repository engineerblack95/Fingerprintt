from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DashboardStatsView, EntryLogExportView, EntryLogViewSet

router = DefaultRouter()
router.register("logs", EntryLogViewSet, basename="entrylog")

urlpatterns = [
    # Declared before the router so "export" is not captured as a log pk.
    path("logs/export/", EntryLogExportView.as_view(), name="logs-export"),
    path("", include(router.urls)),
    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
]
