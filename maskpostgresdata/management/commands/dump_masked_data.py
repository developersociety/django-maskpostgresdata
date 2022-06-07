import os
import subprocess
import sys

from django.apps import apps
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections, transaction

from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE


class Command(BaseCommand):
    help = "Prints a (sort of) pg_dump of the db with sensitive data masked."

    requires_system_checks = False

    def add_arguments(self, parser):
        parser.add_argument(
            "--database", action="store", dest="database", default=DEFAULT_DB_ALIAS,
        )

    def update_auth_user(self, queryset):
        queryset.update(password=make_password("password"))

    def reset_sequences(self, cursor):
        """
        Get all the sequences from the database and the last values for it
        """
        # Get all sequences
        cursor.execute("SELECT sequence_name FROM information_schema.sequences;")
        rows = cursor.fetchall()
        for row in rows:
            sequence_name = row[0]

            # Get the last value for the sequence
            cursor.execute(
                "SELECT last_value FROM {sequence_name}".format(
                    sequence_name=sequence_name
                )
            )
            last_value = cursor.fetchone()[0]

            print(
                "SELECT pg_catalog.setval('public.{sequence_name}', {last_value});".format(
                    sequence_name=sequence_name, last_value=last_value
                ),
                flush=True,
            )

    def handle(self, **options):
        try:
            self.process_data(**options)
        except KeyboardInterrupt:
            print("\n", file=self.stdout._out, flush=True)
            print("Keyboard interaction detected", file=self.stdout._out, flush=True)
            sys.exit(0)
        except BrokenPipeError:
            # Usually the result of a connection drop during the command - there's no point in
            # printing any response, as that's the cause of the problem!
            sys.exit(0)

    def process_data(self, **options):
        connection = connections[options["database"]]
        args = ["pg_dump"]

        conn_params = connection.get_connection_params()
        host = conn_params.get("host", "")
        port = conn_params.get("port", "")
        dbname = conn_params.get("database", "")
        user = conn_params.get("user", "")
        passwd = conn_params.get("password", "")

        if user:
            args += ["-U", user]
        if host:
            args += ["-h", host]
        if port:
            args += ["-p", str(port)]
        args += [dbname]

        subprocess_env = os.environ.copy()
        if passwd:
            subprocess_env["PGPASSWORD"] = str(passwd)

        masker_args = getattr(
            settings, "MASKER_ARGS", ["--no-owner", "--no-privileges"]
        )
        if masker_args:
            args += masker_args

        connection.ensure_connection()
        connection.set_autocommit(False)

        if connection.isolation_level != ISOLATION_LEVEL_SERIALIZABLE:
            connection.connection.set_session(
                isolation_level=ISOLATION_LEVEL_SERIALIZABLE
            )
            connection.isolation_level = ISOLATION_LEVEL_SERIALIZABLE
            connection.connection.isolation_level = ISOLATION_LEVEL_SERIALIZABLE

        cursor = connection.cursor()
        cursor.execute("SELECT pg_export_snapshot();")
        snapshot_id = cursor.fetchone()[0]

        args += ["--snapshot={}".format(snapshot_id)]

        header_dump = args + ["--section=pre-data"]
        subprocess.run(header_dump, stdout=self.stdout._out, env=subprocess_env)

        fields_to_mask = getattr(settings, "MASKER_FIELDS", None)
        altered_tables = []

        for app in apps.get_app_configs():
            for model in app.get_models():
                table_name = model._default_manager.model._meta.db_table
                if hasattr(self, "update_{}".format(table_name)):
                    getattr(self, "update_{}".format(table_name))(
                        model._default_manager.all()
                    )

        if fields_to_mask:
            for app in fields_to_mask.keys():
                for model, fields in fields_to_mask[app].items():
                    model_class = apps.get_model(app.lower(), model_name=model.lower())
                    model_class._default_manager.update(**fields)
                    table_name = model_class._default_manager.model._meta.db_table

                    altered_tables.append(table_name)
                    print("COPY public.{} FROM stdin;".format(table_name), flush=True)
                    cursor.copy_to(self.stdout._out, table_name)
                    print("\\.\n", file=self.stdout._out, flush=True)

        copied_tables = []
        for app in apps.get_app_configs():
            # GeoDjango tables are automatically created by postgis, and we can't use COPY on them
            if app.name == "django.contrib.gis":
                continue

            for model in app.get_models():
                if model._meta.proxy:
                    # Proxy models have another underlying model/table - so skip
                    continue

                table_name = model._default_manager.model._meta.db_table

                if table_name not in altered_tables:
                    print("COPY public.{} FROM stdin;".format(table_name), flush=True)
                    cursor.copy_to(self.stdout._out, table_name)
                    print("\\.\n", file=self.stdout._out, flush=True)

                    copied_tables.append(table_name)

                for field in model._meta.local_many_to_many:
                    m2m_table_name = field.m2m_db_table()

                    if (
                        m2m_table_name not in altered_tables
                        and m2m_table_name not in copied_tables # noqa
                    ):
                        print(
                            "COPY public.{} FROM stdin;".format(m2m_table_name),
                            flush=True,
                        )
                        cursor.copy_to(self.stdout._out, m2m_table_name)
                        print("\\.\n", file=self.stdout._out, flush=True)

                        copied_tables.append(m2m_table_name)

        print(
            "COPY public.django_migrations FROM stdin;".format(table_name), flush=True
        )
        cursor.copy_to(self.stdout._out, "django_migrations")
        print("\\.\n", file=self.stdout._out, flush=True)

        # Sets a new values for sequences.
        self.reset_sequences(cursor)

        post_data_dump = args + ["--section=post-data"]
        subprocess.run(post_data_dump, stdout=self.stdout._out, env=subprocess_env)

        transaction.rollback()
