from django.test import TestCase

from main.apps.preset_catalog.services.business.sqldb_operations import SqlDbBusinessService


class SqlDbBusinessServiceTest(TestCase):
    def test_generic_methods_exist(self):
        for m in ("create_entity", "get_entity", "get_or_none", "list_entities", "update_entity", "delete_entity"):
            self.assertTrue(callable(getattr(SqlDbBusinessService, m)))
