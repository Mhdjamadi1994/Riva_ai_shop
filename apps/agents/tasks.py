import logging
from io import StringIO
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.management import call_command
from django.db import OperationalError, transaction
from django.utils import timezone

from .models import AdminReport, AgentRun
from .services import SupportDraftAgent, run_report_agents

logger = logging.getLogger(__name__)


def _claim_agent_run(run_key, agent_name, task_id, *, lease_minutes=15):
    now = timezone.now()
    with transaction.atomic():
        AgentRun.objects.get_or_create(
            run_key=run_key,
            defaults={"agent_name": agent_name, "status": AgentRun.Status.QUEUED},
        )
        run = AgentRun.objects.select_for_update().get(run_key=run_key)
        if run.status == AgentRun.Status.SUCCEEDED:
            return run, False
        if (run.status == AgentRun.Status.RUNNING and run.started_at
                and run.started_at > now - timedelta(minutes=lease_minutes)):
            return run, False
        run.agent_name = agent_name
        run.task_id = task_id or run.task_id
        run.status = AgentRun.Status.RUNNING
        run.attempts += 1
        run.started_at = now
        run.error = ""
        run.save(update_fields=("agent_name", "task_id", "status", "attempts", "started_at", "error"))
        return run, True


@shared_task(bind=True, autoretry_for=(OperationalError,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def process_support_ticket(self, ticket_id):
    run_key = f"support-ticket:{ticket_id}"
    run, claimed = _claim_agent_run(run_key, "support_draft", self.request.id or "")
    if not claimed:
        return run.result.get("ticket_id", ticket_id)
    started = timezone.now()
    try:
        ticket = SupportDraftAgent().process(ticket_id)
    except Exception as exc:
        run.status = AgentRun.Status.FAILED
        run.error = f"{type(exc).__name__}: {str(exc)[:340]}"
        run.finished_at = timezone.now()
        run.duration_ms = max(0, int((run.finished_at - started).total_seconds() * 1000))
        run.save(update_fields=("status", "error", "finished_at", "duration_ms"))
        raise
    run.status = AgentRun.Status.SUCCEEDED
    run.result = {"ticket_id": ticket.pk, "department": ticket.department, "draft_created": bool(ticket.agent_draft)}
    run.finished_at = timezone.now()
    run.duration_ms = max(0, int((run.finished_at - started).total_seconds() * 1000))
    run.save(update_fields=("status", "result", "finished_at", "duration_ms"))
    return ticket.pk


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=300, retry_kwargs={"max_retries": 5})
def create_scheduled_admin_report():
    key = f"daily-report:{timezone.localdate().isoformat()}"
    report, _ = AdminReport.objects.get_or_create(
        scheduled_key=key,
        defaults={"status": AdminReport.Status.QUEUED},
    )
    if report.status != AdminReport.Status.COMPLETED:
        generate_admin_report.delay(report.pk)
    return report.pk


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=600, retry_kwargs={"max_retries": 3})
def create_scheduled_backup(self):
    run_key = f"scheduled-backup:{timezone.localdate().isoformat()}"
    run, claimed = _claim_agent_run(run_key, "database_backup", self.request.id or "", lease_minutes=60)
    if not claimed:
        if run.status != AgentRun.Status.SUCCEEDED:
            return {"status": "already_running", "agent_run_id": str(run.pk)}
        backup = run.result
        report_key = f"daily-backup-report:{timezone.localdate().isoformat()}"
        report, _ = AdminReport.objects.get_or_create(
            scheduled_key=report_key,
            defaults={
                "status": AdminReport.Status.COMPLETED,
                "findings": {"database_backup": backup},
                "summary": (f"Database backup {'completed' if backup.get('healthy') else 'needs attention'}: "
                            f"{backup.get('latest_backup') or 'no backup file found'}; "
                            f"{backup.get('backup_count', 0)} retained backup files."),
                "started_at": timezone.now(),
                "completed_at": timezone.now(),
            },
        )
        return {"report_id": report.pk, **backup}
    started = timezone.now()
    try:
        call_command("backup_shop_database", stdout=StringIO())
    except Exception as exc:
        run.status = AgentRun.Status.FAILED
        run.error = f"{type(exc).__name__}: {str(exc)[:340]}"
        run.finished_at = timezone.now()
        run.duration_ms = max(0, int((run.finished_at - started).total_seconds() * 1000))
        run.save(update_fields=("status", "error", "finished_at", "duration_ms"))
        raise
    from .services import DatabaseBackupAgent
    backup = DatabaseBackupAgent().run()
    run.status = AgentRun.Status.SUCCEEDED
    run.result = backup
    run.finished_at = timezone.now()
    run.duration_ms = max(0, int((run.finished_at - started).total_seconds() * 1000))
    run.save(update_fields=("status", "result", "finished_at", "duration_ms"))
    now = timezone.now()
    report_key = f"daily-backup-report:{timezone.localdate().isoformat()}"
    report = AdminReport.objects.create(
        status=AdminReport.Status.COMPLETED,
        scheduled_key=report_key,
        findings={"database_backup": backup},
        summary=(f"Database backup {'completed' if backup['healthy'] else 'needs attention'}: "
                 f"{backup['latest_backup'] or 'no backup file found'}; "
                 f"{backup['backup_count']} retained backup files."),
        started_at=now,
        completed_at=now,
    )
    return {"report_id": report.pk, **backup}


@shared_task(bind=True, autoretry_for=(OperationalError,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def generate_admin_report(self, report_id):
    with transaction.atomic():
        report = AdminReport.objects.select_for_update().get(pk=report_id)
        if report.status == AdminReport.Status.COMPLETED:
            return report.pk
        if report.status == AdminReport.Status.RUNNING and report.started_at and report.started_at > timezone.now() - timedelta(minutes=15):
            return report.pk
        report.status = AdminReport.Status.RUNNING
        report.started_at = timezone.now()
        report.error = ""
        report.save(update_fields=["status", "started_at", "error"])
    try:
        findings, summary = run_report_agents(report_id=report.pk, task_id=self.request.id or "")
        report.findings = findings
        report.summary = summary
        report.status = AdminReport.Status.COMPLETED
        report.completed_at = timezone.now()
        report.save(update_fields=["findings", "summary", "status", "completed_at"])
    except Exception:
        logger.exception("Admin report generation failed for report %s", report_id)
        report.status = AdminReport.Status.FAILED
        report.error = "Report generation failed. Check application logs."
        report.completed_at = timezone.now()
        report.save(update_fields=["status", "error", "completed_at"])
        raise


@shared_task(bind=True, autoretry_for=(OperationalError,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def verify_latest_backup(self):
    from pathlib import Path
    backups = sorted(Path(settings.BACKUP_DIR).glob("riva-db-*.json.gz"), reverse=True)
    if not backups:
        raise FileNotFoundError("No database backup exists to verify.")
    backup_name = backups[0].name
    run_key = f"backup-restore-drill:{backup_name}"
    run, claimed = _claim_agent_run(run_key, "backup_restore_drill", self.request.id or "", lease_minutes=60)
    if not claimed:
        return run.result if run.status == AgentRun.Status.SUCCEEDED else {"status": "already_running", "agent_run_id": str(run.pk)}
    started = timezone.now()
    output = StringIO()
    try:
        call_command("verify_shop_backup", filename=backup_name, stdout=output, verbosity=0)
        import json
        result = json.loads(output.getvalue().splitlines()[-1])
    except Exception as exc:
        run.status = AgentRun.Status.FAILED
        run.error = f"{type(exc).__name__}: {str(exc)[:340]}"
        run.finished_at = timezone.now()
        run.duration_ms = max(0, int((run.finished_at - started).total_seconds() * 1000))
        run.save(update_fields=("status", "error", "finished_at", "duration_ms"))
        raise
    run.status = AgentRun.Status.SUCCEEDED
    run.result = result
    run.finished_at = timezone.now()
    run.duration_ms = max(0, int((run.finished_at - started).total_seconds() * 1000))
    run.save(update_fields=("status", "result", "finished_at", "duration_ms"))
    return result
