"""Move a local SQLite dataset into an empty PostgreSQL database in memory."""
from io import StringIO
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.core.management.base import CommandError
from django.db import connections


EXCLUDED_MODELS = {"contenttypes.contenttype", "admin.logentry"}
PROJECT_APP_LABELS = {"agents", "chatbot", "core", "products", "recommendation"}


class Command(BaseCommand):
    help = "Copy business data from a SQLite file into an empty PostgreSQL default database."

    def add_arguments(self, parser):
        parser.add_argument("sqlite_path", help="Path to the SQLite database to migrate.")

    def handle(self, *args, **options):
        destination = connections["default"]
        if destination.vendor != "postgresql":
            raise CommandError("The default database must be PostgreSQL before migration.")
        source_path = Path(options["sqlite_path"]).expanduser().resolve()
        if not source_path.is_file():
            raise CommandError("The source SQLite database file does not exist.")

        alias = "sqlite_migration_source"
        with tempfile.TemporaryDirectory(prefix="riva-sqlite-migration-") as temporary:
            snapshot_path = Path(temporary) / "source.sqlite3"
            try:
                with sqlite3.connect(source_path) as source_db, sqlite3.connect(snapshot_path) as snapshot_db:
                    source_db.backup(snapshot_db)
            except sqlite3.Error as exc:
                raise CommandError("Could not make a consistent temporary snapshot of the SQLite source.") from exc

            source_config = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(snapshot_path),
                "OPTIONS": {"timeout": 30},
                "ATOMIC_REQUESTS": False,
                "AUTOCOMMIT": True,
                "CONN_MAX_AGE": 0,
                "CONN_HEALTH_CHECKS": False,
                "TIME_ZONE": None,
                "TEST": {},
            }
            settings.DATABASES[alias] = source_config
            connections.databases[alias] = source_config
            try:
                call_command("migrate", database=alias, interactive=False, verbosity=0)
                self._require_empty_destination()
                source_counts = self._counts(alias)
                fixture = StringIO()
                call_command(
                    "dumpdata",
                    database=alias,
                    natural_foreign=True,
                    natural_primary=True,
                    exclude=sorted(EXCLUDED_MODELS),
                    stdout=fixture,
                    verbosity=0,
                )
                payload = fixture.getvalue()
                if not payload.strip() or payload.strip() == "[]":
                    raise CommandError("The source database has no application records to migrate.")

                try:
                    with patch.object(sys, "stdin", StringIO(payload)):
                        call_command("loaddata", "-", database="default", format="json", verbosity=0)
                except Exception as exc:
                    raise CommandError("SQLite data could not be loaded into PostgreSQL; PostgreSQL was left unchanged by the fixture transaction.") from exc

                destination_counts = self._counts("default")
                mismatches = {
                    label: (count, destination_counts.get(label, 0))
                    for label, count in source_counts.items()
                    if destination_counts.get(label, 0) != count
                }
                if mismatches:
                    raise CommandError(f"Migration count verification failed for {len(mismatches)} model(s).")
                object_count = sum(source_counts.values())
                self.stdout.write(self.style.SUCCESS(
                    f"Migrated and verified {object_count} records across {len(source_counts)} models. "
                    "The temporary snapshot and in-memory fixture were discarded after verification."
                ))
            finally:
                connections[alias].close()
                connections.databases.pop(alias, None)
                settings.DATABASES.pop(alias, None)

    def _counts(self, alias):
        counts = {}
        for model in apps.get_models():
            label = model._meta.label_lower
            if model._meta.proxy or label in EXCLUDED_MODELS:
                continue
            if model._meta.app_label in PROJECT_APP_LABELS or model._meta.label_lower == settings.AUTH_USER_MODEL.lower():
                count = model._base_manager.using(alias).count()
                if count:
                    counts[label] = count
        return counts

    def _require_empty_destination(self):
        nonempty = self._counts("default")
        if nonempty:
            raise CommandError(
                "PostgreSQL already contains application data. Migrate into an empty database to avoid overwriting records."
            )
