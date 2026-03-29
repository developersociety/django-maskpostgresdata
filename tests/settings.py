import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "maskpostgresdata_{}".format(os.environ.get("TOX_ENV_NAME", "default")),
    }
}

USE_TZ = True

SECRET_KEY = "maskpostgresdata"  # noqa:S105

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "maskpostgresdata",
    "tests",
]
