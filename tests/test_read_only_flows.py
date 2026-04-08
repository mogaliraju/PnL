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

    def test_dashboard_endpoint_returns_project_and_resource_analytics(self):
        response = self.client.get('/api/dashboard')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['kpis']['projects'], 1)
        self.assertEqual(payload['kpis']['resources'], 1)
        self.assertGreaterEqual(payload['kpis']['hours'], 8)
        self.assertEqual(payload['top_customers'][0]['label'], 'Saved Project')
        self.assertEqual(payload['top_roles_by_hours'][0]['label'], 'Architect')

    def test_all_projects_summary_includes_new_metadata_columns(self):
        response = self.client.get('/api/projects?summary=true')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['resource_count'], 1)
        self.assertEqual(payload[0]['total_hours'], 8.0)
        self.assertEqual(payload[0]['reference'], '')
        self.assertEqual(payload[0]['status'], '')
        self.assertEqual(payload[0]['currency'], 'USD')
        self.assertIn('costs', payload[0])

    def test_project_metadata_round_trips_through_save_and_load(self):
        new_project = {
            'project': {
                'customer': 'Round Trip Co',
                'location': 'India',
                'reference': 'REF-500',
                'proposal_date': '2026-04-08',
                'customer_first_touch_point': 'Referral',
                'project_description': 'Large transformation',
                'partner': 'AutomatonsX',
                'payment_terms': 'Net 30',
                'duration_months': 6,
                'status': 'Submitted',
                'stage': 'Proposal',
                'priority': 'High',
                'project_owner': 'Alice',
                'account_manager': 'Bob',
                'sales_spoc': 'Carol',
                'delivery_manager': 'Dan',
                'technical_lead': 'Eve',
                'expected_start_date': '2026-05-01',
                'expected_end_date': '2026-10-31',
                'opportunity_id': 'OPP-500',
                'project_type': 'Implementation',
                'industry': 'Healthcare',
                'delivery_model': 'Hybrid',
                'billing_type': 'Fixed Bid',
                'currency': 'USD',
                'discount_pct': 5,
                'travel_cost': 1000,
                'infra_cost': 500,
                'third_party_cost': 250,
                'internal_notes': 'Internal note',
                'risks': 'Schedule risk',
                'dependencies': 'Client data',
                'next_action': 'Review commercials',
                'next_follow_up_date': '2026-04-15',
            },
            'resources': [{'role': 'Architect', 'level': 'L1', 'hours': 16}],
            'rate_card': [{'level': 'L1', 'rate': 25}],
            'role_catalog': [{'group': 'Delivery', 'roles': ['Architect']}],
            'target_margin': 0.4,
            'fx_rate': 83.5,
        }

        create = self.client.post('/api/projects', json=new_project)
        self.assertEqual(create.status_code, 200)
        created = create.get_json()

        load = self.client.get(f"/api/projects/{created['id']}")
        self.assertEqual(load.status_code, 200)
        payload = load.get_json()

        self.assertEqual(payload['project']['reference'], 'REF-500')
        self.assertEqual(payload['project']['status'], 'Submitted')
        self.assertEqual(payload['project']['project_owner'], 'Alice')
        self.assertEqual(payload['project']['currency'], 'USD')
        self.assertEqual(payload['project']['discount_pct'], 5)
        self.assertEqual(payload['project']['travel_cost'], 1000)
        self.assertEqual(payload['project']['next_follow_up_date'], '2026-04-15')
        self.assertEqual(payload['fx_rate'], 83.5)

        summary = self.client.get('/api/projects?summary=true').get_json()
        saved = next(item for item in summary if item['id'] == created['id'])
        self.assertEqual(saved['reference'], 'REF-500')
        self.assertEqual(saved['status'], 'Submitted')
        self.assertEqual(saved['project_owner'], 'Alice')
        self.assertEqual(saved['resource_count'], 1)
        self.assertEqual(saved['add_on_cost'], 1750.0)
        self.assertEqual(saved['fx_rate'], 83.5)

    def test_index_renders_new_project_fields(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('id="proj_status"', html)
        self.assertIn('id="proj_owner"', html)
        self.assertIn('id="proj_start_date"', html)
        self.assertIn('id="proj_discount_pct"', html)
        self.assertIn('id="proj_internal_notes"', html)


if __name__ == '__main__':
    unittest.main()
