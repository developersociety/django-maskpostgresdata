from io import StringIO

from django.core.management import call_command
from django.test import TransactionTestCase


class TestCommandLockCommand(TransactionTestCase):
    def test_command(self):
        out = StringIO()

        result = call_command("dump_masked_data", stdout=out)

        self.assertIsNone(result)
