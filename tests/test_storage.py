import importlib
import json
import os
import shutil
import sqlite3
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
        self.assertTrue((self.data_dir / 'pnl.sqlite3').exists())

    def test_save_working_data_keeps_global_settings_in_sync(self):
        payload = {
            'project': {'customer': 'Sync Test'},
            'resources': [],
            'rate_card': [{'level': 'L1', 'rate': 42}],
            'role_catalog': [{'group': 'Delivery', 'roles': ['Architect']}],
            'business_units': ['EDM', 'AI'],
        }

        self.storage.save_working_data(payload)

        loaded = self.storage.load_working_data()
        settings = self.storage.load_global_settings()
        db_path = self.data_dir / 'pnl.sqlite3'

        self.assertEqual(loaded['project']['customer'], 'Sync Test')
        self.assertEqual(settings['rate_card'][0]['rate'], 42)
        self.assertEqual(loaded['role_catalog'][0]['group'], 'Delivery')
        self.assertEqual(settings['business_units'], ['EDM', 'AI'])
        self.assertTrue(db_path.exists())

    def test_json_seed_files_are_migrated_into_sqlite(self):
        (self.data_dir / 'data.json').write_text(json.dumps({
            'project': {'customer': 'Migrated Working Copy'},
            'resources': [],
        }, indent=2), encoding='utf-8')
        (self.data_dir / 'settings.json').write_text(json.dumps({
            'rate_card': [{'level': 'L1', 'rate': 99}],
            'role_catalog': [{'group': 'Migrated', 'roles': ['Engineer']}],
        }, indent=2), encoding='utf-8')
        (self.data_dir / 'users.json').write_text(json.dumps({
            'admin': {
                'password': 'hash',
                'role': 'admin',
                'name': 'Administrator',
                'created_at': '2026-01-01T00:00:00',
            }
        }, indent=2), encoding='utf-8')
        (self.data_dir / 'projects' / 'sample.json').write_text(json.dumps({
            '_meta': {'id': 'sample', 'name': 'Sample'},
            'project': {'customer': 'Migrated Project'},
            'resources': [],
        }, indent=2), encoding='utf-8')
        (self.data_dir / 'versions' / 'sample').mkdir()
        (self.data_dir / 'versions' / 'sample' / 'v1.json').write_text(json.dumps({
            '_meta': {'saved_at': '2026-01-01T00:00:00', 'saved_by': 'admin'},
            'project': {'customer': 'Versioned'},
            'resources': [],
        }, indent=2), encoding='utf-8')

        self.storage = reload_storage_module()

        working = self.storage.load_working_data()
        projects = self.storage.list_projects()
        versions = self.storage.list_project_versions('sample')

        self.assertEqual(working['project']['customer'], 'Migrated Working Copy')
        self.assertEqual(working['rate_card'][0]['rate'], 99)
        self.assertEqual(projects[0]['customer'], 'Migrated Project')
        self.assertEqual(versions[0]['vid'], 'v1')

        db_path = self.data_dir / 'pnl.sqlite3'
        self.assertTrue(db_path.exists())
        with sqlite3.connect(db_path) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM projects').fetchone()[0], 1)

    def test_list_projects_summary_includes_metadata_and_resource_rollups(self):
        payload = {
            '_meta': {
                'id': 'portfolio_project',
                'name': 'Portfolio Project',
                'saved_at': '2026-04-08T10:00:00',
                'saved_by': 'tester',
            },
            'project': {
                'customer': 'ACME',
                'location': 'India',
                'proposal_date': '2026-04-10',
                'reference': 'REF-101',
                'status': 'Submitted',
                'stage': 'Proposal',
                'priority': 'High',
                'project_owner': 'Owner One',
                'business_unit': 'SAP',
                'partner': 'AutomatonsX',
                'expected_start_date': '2026-05-01',
                'expected_end_date': '2026-08-31',
                'opportunity_id': 'OPP-9',
                'project_type': 'Implementation',
                'industry': 'Retail',
                'delivery_model': 'Hybrid',
                'billing_type': 'Fixed Bid',
                'currency': 'USD',
                'discount_pct': 7.5,
                'travel_cost': 1500,
                'infra_cost': 800,
                'third_party_cost': 200,
                'next_follow_up_date': '2026-04-15',
            },
            'resources': [
                {'role': 'Architect', 'level': 'L1', 'hours': 10},
                {'role': 'Engineer', 'level': 'L2', 'hours': 30},
            ],
            'rate_card': [
                {'level': 'L1', 'rate': 100},
                {'level': 'L2', 'rate': 50},
            ],
            'fx_rate': 83.25,
            'target_margin': 0.4,
        }

        self.storage.save_project_record('portfolio_project', payload)

        summary = self.storage.list_projects(summary=True)

        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]['reference'], 'REF-101')
        self.assertEqual(summary[0]['status'], 'Submitted')
        self.assertEqual(summary[0]['business_unit'], 'SAP')
        self.assertEqual(summary[0]['resource_count'], 2)
        self.assertEqual(summary[0]['total_hours'], 40.0)
        self.assertEqual(summary[0]['avg_rate'], 62.5)
        self.assertEqual(summary[0]['add_on_cost'], 2500.0)
        self.assertEqual(summary[0]['discount_pct'], 7.5)
        self.assertEqual(summary[0]['fx_rate'], 83.25)
        self.assertEqual(summary[0]['costs']['input_cost'], 2500.0)


if __name__ == '__main__':
    unittest.main()
