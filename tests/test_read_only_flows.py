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
    'pnl.utils.auth',
    'pnl.utils.validators',
    'pnl.services.pnl_service',
    'pnl.services.excel_service',
    'pnl.routes.auth',
    'pnl.routes.main',
    'pnl.routes.projects',
    'pnl.routes.export',
    'pnl.routes.import_excel',
    'pnl.routes',
    'pnl',
]


def reload_app():
    for name in MODULES_TO_RELOAD:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
    from pnl import create_app
    return create_app()


class ReadOnlyFlowTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[1] / 'test-runtime'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.data_dir = temp_root / f'test-{uuid.uuid4().hex}'
        self.data_dir.mkdir(parents=True, exist_ok=True)

        os.environ['DATA_DIR'] = str(self.data_dir)
        os.environ['SECRET_KEY'] = 'test-secret'
        os.environ['PNL_ENV'] = 'development'
        os.environ.pop('PNL_BOOTSTRAP_ADMIN_PASSWORD', None)

        (self.data_dir / 'projects').mkdir()
        (self.data_dir / 'versions').mkdir()

        self.baseline_data = {
            'project': {'customer': 'Working Copy'},
            'resources': [],
            'rate_card': [{'level': 'L1', 'rate': 10}],
            'role_catalog': [{'group': 'Default', 'roles': ['Engineer']}],
        }
        (self.data_dir / 'data.json').write_text(json.dumps(self.baseline_data, indent=2), encoding='utf-8')
        (self.data_dir / 'settings.json').write_text(json.dumps({
            'rate_card': [{'level': 'L1', 'rate': 25}],
            'role_catalog': [{'group': 'Delivery', 'roles': ['Architect']}],
        }, indent=2), encoding='utf-8')
        (self.data_dir / 'users.json').write_text(json.dumps({
            'admin': {
                'password': 'unused-in-session-tests',
                'role': 'admin',
                'name': 'Administrator',
                'created_at': '2026-01-01T00:00:00',
            }
        }, indent=2), encoding='utf-8')
        (self.data_dir / 'projects' / 'sample.json').write_text(json.dumps({
            '_meta': {'id': 'sample', 'name': 'Sample'},
            'project': {'customer': 'Saved Project'},
            'resources': [{'role': 'Architect', 'level': 'L1', 'hours': 8}],
            'rate_card': [{'level': 'L1', 'rate': 5}],
            'role_catalog': [{'group': 'Old', 'roles': ['Old Role']}],
        }, indent=2), encoding='utf-8')

        self.app = reload_app()
        self.app.testing = True
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['user'] = 'admin'
            session['role'] = 'admin'
            session['name'] = 'Administrator'

    def tearDown(self):
        shutil.rmtree(self.data_dir, ignore_errors=True)

    def test_loading_project_does_not_overwrite_working_data(self):
        before = (self.data_dir / 'data.json').read_text(encoding='utf-8')

        response = self.client.get('/api/projects/sample')

        self.assertEqual(response.status_code, 200)
        self.assertEqual((self.data_dir / 'data.json').read_text(encoding='utf-8'), before)

        payload = response.get_json()
        self.assertEqual(payload['project']['customer'], 'Saved Project')
        self.assertEqual(payload['rate_card'][0]['rate'], 25)

    def test_export_does_not_overwrite_working_data(self):
        before = (self.data_dir / 'data.json').read_text(encoding='utf-8')

        response = self.client.post('/api/export', json={
            'project': {'customer': 'Export Project'},
            'resources': [{'role': 'Architect', 'level': 'L1', 'hours': 8}],
            'rate_card': [{'level': 'L1', 'rate': 25}],
            'target_margin': 0.40,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual((self.data_dir / 'data.json').read_text(encoding='utf-8'), before)
        self.assertIn(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            response.headers.get('Content-Type', ''),
        )


if __name__ == '__main__':
    unittest.main()
