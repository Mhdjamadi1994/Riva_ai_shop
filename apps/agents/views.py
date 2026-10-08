from celery.exceptions import OperationalError
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .models import AdminReport
from .serializers import AdminReportSerializer
from .tasks import generate_admin_report


class AdminReportListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = AdminReportSerializer
    permission_classes = [IsAdminUser]
    queryset = AdminReport.objects.select_related("created_by").all()

    def create(self, request, *args, **kwargs):
        report = AdminReport.objects.create(created_by=request.user)
        try:
            generate_admin_report.delay(report.pk)
        except OperationalError:
            report.status = AdminReport.Status.FAILED
            report.error = "Background queue is unavailable. Start Redis and retry."
            report.save(update_fields=["status", "error"])
            return Response(AdminReportSerializer(report).data, status=status.HTTP_SERVICE_UNAVAILABLE)
        return Response(AdminReportSerializer(report).data, status=status.HTTP_ACCEPTED)
