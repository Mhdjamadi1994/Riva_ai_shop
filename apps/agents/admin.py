from django.contrib import admin

from .models import AdminReport, AgentRun, DatabaseBackupArtifact


@admin.register(AdminReport)
class AdminReportAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "created_by", "created_at", "completed_at")
    list_filter = ("status", "created_at")
    readonly_fields = ("status", "findings", "summary", "error", "created_at", "started_at", "completed_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("agent_name", "status", "attempts", "duration_ms", "created_at", "finished_at")
    list_filter = ("agent_name", "status", "created_at")
    search_fields = ("run_key", "task_id", "error")
    readonly_fields = tuple(field.name for field in AgentRun._meta.fields)
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DatabaseBackupArtifact)
class DatabaseBackupArtifactAdmin(admin.ModelAdmin):
    list_display = ("filename", "compressed_bytes", "offsite_verified", "restore_verified_at", "created_at")
    list_filter = ("offsite_verified", "created_at", "restore_verified_at")
    search_fields = ("filename", "sha256", "s3_key")
    readonly_fields = tuple(field.name for field in DatabaseBackupArtifact._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
