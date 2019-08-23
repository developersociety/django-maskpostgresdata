Django Mask Postgres Data
=========================

Adds a management command to your Django project which allows you to create a (sort of) pg_dump
of your data with sensitive data masked.

Installation
------------

Install with pip:

`pip install django-maskpostgresdata`

And add `maskpostgresdata` to your `INSTALLED_APPS`:

```
INSTALLED_APPS = [
    ...
    'maskpostgresdata',
    ...
]
```

Usage
-----

By default, `django-maskpostgresdata` will replace the `password` column for each row in the Django `User` model with "password". Just run `manage.py dump_masked_data` and you'll get a pg_dump with the password field changed to "password" for all users.

There are 2 ways to customise the behaviour of `django-maskpostgresdata`.

To override individual fields of a model with a given value, add a dictionary called `MASKER_FIELDS` to your settings using the following format:

```
MASKER_FIELDS = {
    "{ APP_NAME }": {"{ MODEL_NAME }": {"{ FIELD_NAME }": { VALUE },}},
}
```

Alternatively, you can define exactly how the data is updated by subclassing `BasePostgresDataMaskingCommand` in a management command of your own. For example:

```
from django.contrib.auth.hashers import make_password

from maskpostgresdata import BasePostgresDataMaskingCommand


class Command(BasePostgresDataMaskingCommand):

    def update_auth_user(self, queryset):
        queryset.update(password=make_password("a_different_password"))

```

Just create a method called `update_{ db_table_name }` taking a `queryset` as the parameter. You can then perform `update` operations on this queryset. `{ db_table_name }` is of the format `{app_label}_{model_name}` by default, but could technically be different.

You can then run `manage.py dump_masked_data` and it will dump your data to `stdout`.
