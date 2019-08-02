=========================
Django Mask Postgres Data
=========================

Adds a management command to your Django project which allows you to create a (sort of) pg_dump
of your data, with sepcific fields masked by given values.

To configure, add a dictionary called `MASKER_FIELDS` to your settings using the following format::

MASKER_FIELDS = {
    "{ APP_NAME }": {"{ MODEL_NAME }": {"{ FIELD_NAME }": { VALUE},}},
}

You can then run `manage.py dump_masked_data` and it will dump your data to `stdout`.
