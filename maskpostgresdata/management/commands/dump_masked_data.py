import subprocess
import sys

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections, transaction

from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE


class Command(BaseCommand):
    help = (
        "Prints a (sort of) pg_dump of the db with sensitive data masked."
    )

    requires_system_checks = False

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            action="store",
            dest="database",
            default=DEFAULT_DB_ALIAS,
        )

    def filter_auth_user(self, queryset):
        return queryset.update(password="blah")

    def handle(self, **options):
        connection = connections[options["database"]]

        args = ["pg_dump"]

        conn_params = connection.get_connection_params()
        host = conn_params.get("host", "")
        port = conn_params.get("port", "")
        dbname = conn_params.get("database", "")
        user = conn_params.get("user", "")

        if user:
            args += ["-U", user]
        if host:
            args += ["-h", host]
        if port:
            args += ["-p", str(port)]
        args += [dbname]

        connection.ensure_connection()
        connection.set_autocommit(False)

        if connection.isolation_level != ISOLATION_LEVEL_SERIALIZABLE:
            connection.connection.set_session(isolation_level=ISOLATION_LEVEL_SERIALIZABLE)
            connection.isolation_level = ISOLATION_LEVEL_SERIALIZABLE
            connection.connection.isolation_level = ISOLATION_LEVEL_SERIALIZABLE

        cursor = connection.cursor()
        cursor.execute("SELECT pg_export_snapshot();")
        snapshot_id = cursor.fetchone()[0]

        args += ["--snapshot={}".format(snapshot_id)]

        header_dump = args + ["--section=pre-data"]
        subprocess.run(header_dump, stdout=self.stdout._out)

        fields_to_mask = settings.MASKER_FIELDS

        altered_tables = []

        for app in fields_to_mask.keys():
            for model, fields in fields_to_mask[app].items():
                model_class = ContentType.objects.get(
                    app_label=app.lower(), model=model.lower()
                ).model_class()

                model_class.objects.update(**fields)
                table_name = model_class.objects.model._meta.db_table

                altered_tables.append(table_name)
                print("COPY public.{} FROM stdin;".format(table_name), file=self.stdout._out)                
                cursor.copy_to(self.stdout._out, table_name)
                print("\\.\n", file=self.stdout._out)

        for content_type in ContentType.objects.all():
            if content_type.model_class():
                table_name = content_type.model_class().objects.model._meta.db_table
                if table_name not in altered_tables:
                    print("COPY public.{} FROM stdin;".format(table_name), file=self.stdout._out)                
                    cursor.copy_to(self.stdout._out, table_name)
                    print("\\.\n", file=self.stdout._out)

        post_data_dump = args + ["--section=post-data"]
        subprocess.run(header_dump, stdout=self.stdout._out)

        transaction.rollback()
