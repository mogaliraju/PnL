import importlib
import json
import os
import shutil
import sys
import unittest
import uuid
from pathlib import Path


MODULES_TO_RELOAD = [
    'pnl.config',
    'pnl.utils.logger',
    'pnl.utils.storage',
]


def reload_storage_module():
    for name in MODULES_TO_RELOAD:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
    from pnl.utils import storage
    return storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[1] / 'test-runtime'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.data_dir = temp_root / f'storage-{uuid.uuid4().hex}'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / 'projects').mkdir()
        (self.data_dir / 'versions').mkdir()

        os.environ['DATA_DIR'] = str(self.data_dir)
        os.environ['SECRET_KEY'] = 'test-secret'
        os.environ['PNL_ENV'] = 'development'
        os.environ.pop('PNL_BOOTSTRAP_ADMIN_PASSWORD', None)
        os.environ.pop('PNL_BOOTSTRAP_ADMIN_USERNAME', None)
        os.environ.pop('PNL_BOOTSTRAP_ADMIN_NAME', None)

        self.storage = reload_storage_module()

    def tearDown(self):
        shutil.rmtree(self.data_dir, ignore_errors=True)

    def test_load_users_returns_empty_without_bootstrap_password(self):
        users = self.storage.load_users()

        self.assertEqual(users, {})
        self.assertFalse((self.data_dir / 'users.json').exists())

    def test_load_users_bootstraps_admin_from_environment(self):
        os.environ['PNL_BOOTSTRAP_ADMIN_PASSWORD'] = 'super-secret'
        os.environ['PNL_BOOTSTRAP_ADMIN_USERNAME'] = 'root'
        os.environ['PNL_BOOTSTRAP_ADMIN_NAME'] = 'Root Admin'
        self.storage = reload_storage_module()

        users = self.storage.load_users()

        self.assertIn('root', users)
        self.assertEqual(users['root']['role'], 'admin')
        self.assertEqual(users['root']['name'], 'Root Admin')
        self.assertTrue((self.data_dir / 'users.json').exists())

    def test_save_working_data_keeps_global_settings_in_sync(self):
        payload = {
            'project': {'customer': 'Sync Test'},
            'resources': [],
            'rate_card': [{'level': 'L1', 'rate': 42}],
            'role_catalog': [{'group': 'Delivery', 'roles': ['Architect']}],
        }

        self.storage.save_working_data(payload)

        saved_data = json.loads((self.data_dir / 'data.json').read_text(encoding='utf-8'))
        saved_settings = json.loads((self.data_dir / 'settings.json').read_text(encoding='utf-8'))
        loaded = self.storage.load_working_data()

        self.assertEqual(saved_data['project']['customer'], 'Sync Test')
        self.assertEqual(saved_settings['rate_card'][0]['rate'], 42)
        self.assertEqual(loaded['role_catalog'][0]['group'], 'Delivery')


if __name__ == '__main__':
    unittest.main()
