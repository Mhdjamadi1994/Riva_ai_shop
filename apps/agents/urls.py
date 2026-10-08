from django.urls import path

from .views import AdminReportListCreateAPIView

urlpatterns = [path("", AdminReportListCreateAPIView.as_view(), name="admin-reports")]
