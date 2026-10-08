import gzip
import hashlib
import json
import os
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.utils import timezone
from django.core.management.base import CommandError

from apps.agents.models import DatabaseBackupArtifact


class Command(BaseCommand):
    help = "Create a compressed, restorable database export and retain the latest 14 backups."

    def handle(self, *args, **options):
        backup_dir = Path(settings.BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            backup_dir.chmod(0o700)
        stamp = timezone.now().astimezone(datetime_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stem = f"riva-db-{stamp}"
        raw_path = backup_dir / f"{stem}.json"
        partial_path = backup_dir / f"{stem}.json.gz.partial"
        final_path = backup_dir / f"{stem}.json.gz"
        checksum_path = backup_dir / f"{stem}.json.gz.sha256"
        checksum_partial = backup_dir / f"{stem}.json.gz.sha256.partial"
        try:
            call_command(
                "dumpdata",
                "--natural-foreign",
                "--natural-primary",
                "--exclude=contenttypes",
                "--exclude=admin.logentry",
                output=str(raw_path),
                verbosity=0,
            )
            digest = hashlib.sha256()
            with raw_path.open("rb") as source, partial_path.open("wb") as compressed:
                with gzip.GzipFile(fileobj=compressed, mode="wb", mtime=0) as target:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        target.write(chunk)
            os.replace(partial_path, final_path)
            checksum_partial.write_text(f"{digest.hexdigest()}  {final_path.name}\n", encoding="ascii")
            os.replace(checksum_partial, checksum_path)
        finally:
            raw_path.unlink(missing_ok=True)
            partial_path.unlink(missing_ok=True)
            checksum_partial.unlink(missing_ok=True)

        remote_bucket = ""
        remote_key = ""
        if settings.BACKUP_S3_BUCKET:
            try:
                import boto3
                client_options = {"region_name": settings.BACKUP_S3_REGION}
                if settings.BACKUP_S3_ENDPOINT_URL:
                    client_options["endpoint_url"] = settings.BACKUP_S3_ENDPOINT_URL
                client = boto3.client("s3", **client_options)
                remote_bucket = settings.BACKUP_S3_BUCKET
                remote_key = f"{settings.BACKUP_S3_PREFIX}/{final_path.name}" if settings.BACKUP_S3_PREFIX else final_path.name
                encryption = {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": settings.BACKUP_S3_KMS_KEY_ID} if settings.BACKUP_S3_KMS_KEY_ID else {"ServerSideEncryption": "AES256"}
                client.upload_file(
                    str(final_path), remote_bucket, remote_key,
                    ExtraArgs={**encryption, "Metadata": {"sha256": digest.hexdigest()}},
                )
                remote_head = client.head_object(Bucket=remote_bucket, Key=remote_key)
                expected_sse = "aws:kms" if settings.BACKUP_S3_KMS_KEY_ID else "AES256"
                if (remote_head.get("ContentLength") != final_path.stat().st_size
                        or remote_head.get("Metadata", {}).get("sha256") != digest.hexdigest()
                        or remote_head.get("ServerSideEncryption") != expected_sse):
                    raise CommandError("Remote backup verification failed.")
            except Exception as exc:
                raise CommandError("The local backup succeeded, but encrypted offsite upload or verification failed.") from exc

        DatabaseBackupArtifact.objects.update_or_create(
            filename=final_path.name,
            defaults={
                "sha256": digest.hexdigest(),
                "compressed_bytes": final_path.stat().st_size,
                "s3_bucket": remote_bucket,
                "s3_key": remote_key,
                "offsite_verified": bool(remote_bucket and remote_key),
            },
        )

        backups = sorted(backup_dir.glob("riva-db-*.json.gz"), reverse=True)
        for old_backup in backups[14:]:
            old_backup.unlink(missing_ok=True)
            old_backup.with_name(old_backup.name + ".sha256").unlink(missing_ok=True)
            DatabaseBackupArtifact.objects.filter(filename=old_backup.name).delete()
        result = {
            "file": final_path.name,
            "sha256": digest.hexdigest(),
            "compressed_bytes": final_path.stat().st_size,
            "created_at": timezone.now().isoformat(),
            "retained_backups": min(len(backups), 14),
            "offsite_bucket": remote_bucket or None,
            "offsite_object": remote_key or None,
            "offsite_verified": bool(remote_bucket and remote_key),
            "restore_command": f"python manage.py loaddata {final_path.name}",
        }
        self.stdout.write(self.style.SUCCESS(str(result)))
