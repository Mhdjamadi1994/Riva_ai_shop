import gzip
import hashlib
import json
import tempfile
import uuid
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.core.management.base import CommandError
from django.db import connections
from django.utils import timezone

from apps.agents.models import DatabaseBackupArtifact


class Command(BaseCommand):
    help = "Verify a backup checksum and restore it into a temporary isolated SQLite database."

    def add_arguments(self, parser):
        parser.add_argument("--filename", default="", help="Backup filename; defaults to newest local backup")

    def handle(self, *args, **options):
        backup_dir = Path(settings.BACKUP_DIR)
        filename = options["filename"]
        if not filename:
            backups = sorted(backup_dir.glob("riva-db-*.json.gz"), reverse=True)
            if not backups:
                raise CommandError("No database backup exists to verify.")
            path = backups[0]
        else:
            path = backup_dir / Path(filename).name
        if not path.is_file() or path.parent.resolve() != backup_dir.resolve():
            raise CommandError("Backup file was not found in the configured backup directory.")

        sidecar = path.with_name(path.name + ".sha256")
        if not sidecar.is_file():
            raise CommandError("Backup checksum sidecar is missing.")
        expected = sidecar.read_text(encoding="ascii").split()[0]
        digest = hashlib.sha256()
        try:
            with gzip.open(path, "rb") as compressed:
                while chunk := compressed.read(1024 * 1024):
                    digest.update(chunk)
        except (OSError, EOFError) as exc:
            raise CommandError("Backup gzip stream is corrupt.") from exc
        if digest.hexdigest() != expected:
            raise CommandError("Backup checksum does not match its sidecar.")
        try:
            with gzip.open(path, "rt", encoding="utf-8") as compressed:
                fixture = json.load(compressed)
        except (OSError, EOFError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommandError("Backup does not contain valid UTF-8 Django fixture JSON.") from exc
        if not isinstance(fixture, list) or any(not isinstance(item, dict) or "model" not in item for item in fixture):
            raise CommandError("Backup fixture structure is invalid.")

        expected_counts = {}
        for row in fixture:
            label = row["model"].lower()
            expected_counts[label] = expected_counts.get(label, 0) + 1

        alias = f"backup_verify_{uuid.uuid4().hex[:10]}"
        with tempfile.TemporaryDirectory(prefix="restore-drill-", dir=backup_dir) as temporary:
            database_config = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(Path(temporary) / "restored.sqlite3"),
                "OPTIONS": {"timeout": 20},
                "ATOMIC_REQUESTS": False,
                "AUTOCOMMIT": True,
                "CONN_MAX_AGE": 0,
                "CONN_HEALTH_CHECKS": False,
                "TIME_ZONE": None,
                "TEST": {},
            }
            settings.DATABASES[alias] = database_config
            connections.databases[alias] = database_config
            try:
                call_command("migrate", database=alias, interactive=False, verbosity=0)
                call_command("loaddata", str(path), database=alias, verbosity=0)
                restored_counts = {}
                for label, expected_count in expected_counts.items():
                    try:
                        model = apps.get_model(label)
                    except LookupError as exc:
                        raise CommandError(f"Backup references unknown model {label}.") from exc
                    actual_count = model.objects.using(alias).count()
                    if actual_count < expected_count:
                        raise CommandError(f"Restore verification failed for {label}: expected at least {expected_count}, found {actual_count}.")
                    restored_counts[label] = actual_count
            finally:
                connections[alias].close()
                connections.databases.pop(alias, None)
                settings.DATABASES.pop(alias, None)

        artifact = DatabaseBackupArtifact.objects.filter(filename=path.name).first()
        if artifact:
            artifact.restore_verified_at = timezone.now()
            artifact.save(update_fields=("restore_verified_at",))
        result = {
            "filename": path.name,
            "sha256_verified": True,
            "fixture_records": len(fixture),
            "models_verified": len(restored_counts),
            "restored_to_temporary_database": True,
            "verified_at": timezone.now().isoformat(),
        }
        self.stdout.write(json.dumps(result, sort_keys=True))
