import os
import subprocess
import sys

from django.apps import apps
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections, transaction

from psycopg import IsolationLevel


class Command(BaseCommand):
    help = "Prints a (sort of) pg_dump of the db with sensitive data masked."

    requires_system_checks = []

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
        cursor.execute(
            "SELECT schemaname, sequencename, start_value, last_value FROM pg_sequences;"
        )
        rows = cursor.fetchall()
        for schema_name, sequence_name, start_value, last_value in rows:
            current_value = last_value or start_value
            is_called = last_value is not None

            self.stdout.write(
                "SELECT pg_catalog.setval('{}.{}', {}, {});".format(
                    schema_name, sequence_name, current_value, str(is_called).lower(),
                ),
            )

    def handle(self, **options):
        try:
            self.process_data(**options)
        except KeyboardInterrupt:
            self.stdout.write("\n")
            self.stdout.write("-- Keyboard interaction detected")
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
        dbname = conn_params.get("dbname", "")
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

        if connection.isolation_level != IsolationLevel.SERIALIZABLE:
            connection.isolation_level = IsolationLevel.SERIALIZABLE
            connection.connection.isolation_level = IsolationLevel.SERIALIZABLE

        cursor = connection.cursor()
        cursor.execute("SELECT pg_export_snapshot();")
        snapshot_id = cursor.fetchone()[0]

        args += ["--snapshot={}".format(snapshot_id)]

        header_dump = args + ["--section=pre-data"]
        subprocess.run(header_dump, env=subprocess_env)

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
                    self.stdout.write("COPY public.{} FROM stdin;".format(table_name))
                    self.stdout.flush()
                    with cursor.copy("COPY public.{} TO STDOUT".format(table_name)) as copy:
                        while data := copy.read():
                            sys.stdout.buffer.write(data)
                    self.stdout.write("\\.\n")

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

                if table_name not in altered_tables and table_name not in copied_tables:
                    self.stdout.write("COPY public.{} FROM stdin;".format(table_name))
                    self.stdout.flush()
                    with cursor.copy("COPY public.{} TO STDOUT".format(table_name)) as copy:
                        while data := copy.read():
                            sys.stdout.buffer.write(data)
                    self.stdout.write("\\.\n")

                    copied_tables.append(table_name)

                for field in model._meta.local_many_to_many:
                    m2m_table_name = field.m2m_db_table()

                    if (
                        m2m_table_name not in altered_tables
                        and m2m_table_name not in copied_tables # noqa
                    ):
                        self.stdout.write("COPY public.{} FROM stdin;".format(m2m_table_name))
                        self.stdout.flush()
                        with cursor.copy("COPY public.{} TO STDOUT".format(m2m_table_name)) as copy:
                            while data := copy.read():
                                sys.stdout.buffer.write(data)
                        self.stdout.write("\\.\n")

                        copied_tables.append(m2m_table_name)

        self.stdout.write("COPY public.django_migrations FROM stdin;".format(table_name))
        self.stdout.flush()
        with cursor.copy("COPY public.django_migrations TO STDOUT") as copy:
            while data := copy.read():
                sys.stdout.buffer.write(data)
        self.stdout.write("\\.\n")

        # Sets a new values for sequences.
        self.reset_sequences(cursor)

        post_data_dump = args + ["--section=post-data"]
        self.stdout.flush()
        subprocess.run(post_data_dump, env=subprocess_env)

        transaction.rollback()
