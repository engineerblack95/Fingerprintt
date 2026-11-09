from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DashboardStatsView, EntryLogViewSet

router = DefaultRouter()
router.register("logs", EntryLogViewSet, basename="entrylog")

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
]
