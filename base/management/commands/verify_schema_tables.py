from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
import os


class Command(BaseCommand):
    help = "Fail if any managed model table is missing in the current database."

    def handle(self, *args, **options):
        table_names = connection.introspection.table_names()
        existing_tables = set(table_names)
        expected_tables = set()

        for model in apps.get_models():
            meta = model._meta
            if meta.proxy or not meta.managed or meta.swapped:
                continue
            expected_tables.add(meta.db_table)

        missing_tables = sorted(expected_tables - existing_tables)

        if missing_tables:
            details = "\n".join(f"- {table}" for table in missing_tables)
            raise CommandError(
                "Missing database tables for installed apps:\n"
                f"{details}\n"
                "Run migrations in this environment before starting the app."
            )

        expected_count_raw = os.getenv("EXPECTED_DB_TABLE_COUNT", "382").strip()
        if expected_count_raw:
            try:
                expected_count = int(expected_count_raw)
            except ValueError as error:
                raise CommandError(
                    "EXPECTED_DB_TABLE_COUNT must be an integer."
                ) from error

            actual_count = len(table_names)
            if actual_count != expected_count:
                raise CommandError(
                    f"Database table count mismatch: expected {expected_count}, found {actual_count}."
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Schema check passed: all installed-app tables exist ({len(table_names)} tables)."
            )
        )
