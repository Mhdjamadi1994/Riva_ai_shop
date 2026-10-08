from django.conf import settings
from django.db import models
import uuid


class AdminReport(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="admin_reports",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    findings = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    scheduled_key = models.CharField(max_length=80, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report {self.pk} ({self.status})"


class AgentRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_name = models.CharField(max_length=80)
    run_key = models.CharField(max_length=160, unique=True)
    task_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    attempts = models.PositiveSmallIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=400, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("agent_name", "status", "-created_at"))]

    def __str__(self):
        return f"{self.agent_name} ({self.status})"


class DatabaseBackupArtifact(models.Model):
    filename = models.CharField(max_length=180, unique=True)
    sha256 = models.CharField(max_length=64)
    compressed_bytes = models.PositiveBigIntegerField()
    s3_bucket = models.CharField(max_length=180, blank=True)
    s3_key = models.CharField(max_length=500, blank=True)
    offsite_verified = models.BooleanField(default=False)
    restore_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.filename
