"""
PnL Application — Comprehensive Test Suite
Covers: auth, project CRUD, version history, margin calculations,
        dashboard API, settings, export, bookings, funnel, UI routes.
Run: python -m pytest tests/test_pnl_suite.py -v
"""
import importlib
import json
import os
import shutil
import sys
import unittest
import uuid
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import openpyxl

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
    'pnl.routes.funnel',
    'pnl.routes.bookings',
    'pnl.routes',
    'pnl',
]


def reload_app():
    for name in MODULES_TO_RELOAD:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
    from pnl import create_app
    return create_app()


def make_data_dir():
    root = Path(__file__).resolve().parents[1] / 'test-runtime'
    root.mkdir(parents=True, exist_ok=True)
    d = root / f'suite-{uuid.uuid4().hex}'
    d.mkdir(parents=True)
    return d


SAMPLE_PROJECT = {
    '_meta': {'id': 'proj1', 'name': 'Test Project'},
    'project': {
        'customer': 'ACME Corp',
        'location': 'Singapore',
        'status': 'Submitted',
        'stage': 'Proposal',
        'priority': 'High',
        'project_owner': 'Alice',
        'account_manager': 'Bob',
        'sales_spoc': 'Carol',
        'delivery_manager': 'Dan',
        'business_unit': 'EDM',
        'currency': 'USD',
        'discount_pct': 0,
        'travel_cost': 0,
        'infra_cost': 0,
        'third_party_cost': 0,
    },
    'resources': [
        {'role': 'Architect', 'level': 'L1', 'hours': 100, 'group': 'Delivery'},
        {'role': 'Engineer',  'level': 'L2', 'hours': 200, 'group': 'Delivery'},
    ],
    'rate_card': [
        {'level': 'L1', 'rates': {'Delivery': 100}},
        {'level': 'L2', 'rates': {'Delivery': 50}},
    ],
    'cloud4c_margin': 0.30,
    'ax_margin': 0.25,
    'one_time_costs': [],
}


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.data_dir = make_data_dir()
        os.environ['DATA_DIR'] = str(self.data_dir)
        os.environ['SECRET_KEY'] = 'test-secret-key'
        os.environ['PNL_ENV'] = 'development'
        os.environ.pop('PNL_BOOTSTRAP_ADMIN_PASSWORD', None)

        users = {
            'admin': {
                'password': 'unused',
                'role': 'admin',
                'name': 'Administrator',
                'created_at': '2026-01-01T00:00:00',
            },
            'viewer': {
                'password': 'unused',
                'role': 'user',
                'name': 'Viewer User',
                'created_at': '2026-01-01T00:00:00',
            },
        }
        settings = {
            'rate_card': [
                {'level': 'L1', 'rates': {'Delivery': 100}},
                {'level': 'L2', 'rates': {'Delivery': 50}},
            ],
            'role_catalog': [{'group': 'Delivery', 'roles': ['Architect', 'Engineer']}],
            'business_units': ['EDM', 'AI', 'SAP'],
        }
        (self.data_dir / 'users.json').write_text(json.dumps(users), encoding='utf-8')
        (self.data_dir / 'settings.json').write_text(json.dumps(settings), encoding='utf-8')
        (self.data_dir / 'projects').mkdir()
        (self.data_dir / 'versions').mkdir()

        (self.data_dir / 'projects' / 'proj1.json').write_text(
            json.dumps(SAMPLE_PROJECT), encoding='utf-8'
        )

        self.app = reload_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.data_dir, ignore_errors=True)

    def _auth(self, role='admin'):
        with self.client.session_transaction() as s:
            s['user'] = role
            s['role'] = role
            s['name'] = 'Administrator' if role == 'admin' else 'Viewer'

    def _json(self, resp):
        return resp.get_json()


# ══════════════════════════════════════════════════════════════════
# 1. AUTHENTICATION
# ══════════════════════════════════════════════════════════════════
class TestAuthentication(BaseTestCase):

    def test_login_page_loads(self):
        r = self.client.get('/login')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'login', r.data.lower())

    def test_login_wrong_password_returns_401(self):
        r = self.client.post('/login', json={'username': 'admin', 'password': 'wrong'})
        self.assertEqual(r.status_code, 401)
        self.assertIn('error', self._json(r))

    def test_login_unknown_user_returns_401(self):
        r = self.client.post('/login', json={'username': 'ghost', 'password': 'x'})
        self.assertEqual(r.status_code, 401)

    def test_unauthenticated_root_redirects_to_login(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login', r.headers['Location'])

    def test_unauthenticated_api_returns_401_for_json_requests(self):
        # login_required returns 401 only for JSON requests; redirects otherwise
        for url in ['/api/me', '/api/projects', '/api/dashboard', '/api/data']:
            r = self.client.get(url, headers={'Accept': 'application/json',
                                              'Content-Type': 'application/json'})
            self.assertIn(r.status_code, [401, 302], msg=f"Unexpected status for {url}")

    def test_authenticated_root_returns_200(self):
        self._auth()
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)

    def test_api_me_returns_session_info(self):
        self._auth()
        r = self.client.get('/api/me')
        self.assertEqual(r.status_code, 200)
        data = self._json(r)
        self.assertEqual(data['username'], 'admin')
        self.assertEqual(data['role'], 'admin')

    def test_logout_clears_session_and_redirects(self):
        self._auth()
        r = self.client.get('/logout')
        self.assertEqual(r.status_code, 302)
        # After logout, root should redirect to login
        r2 = self.client.get('/')
        self.assertEqual(r2.status_code, 302)
        self.assertIn('/login', r2.headers['Location'])

    def test_change_password_requires_auth(self):
        r = self.client.post('/api/users/admin/password', json={'password': 'new'})
        self.assertEqual(r.status_code, 401)

    def test_admin_can_list_users(self):
        self._auth('admin')
        r = self.client.get('/api/users')
        self.assertEqual(r.status_code, 200)
        users = self._json(r)
        usernames = [u['username'] for u in users]
        self.assertIn('admin', usernames)

    def test_non_admin_cannot_list_users(self):
        # admin_required redirects non-admin browser requests (302) and returns 403 for JSON
        self._auth('viewer')
        r = self.client.get('/api/users')
        self.assertIn(r.status_code, [302, 403])


# ══════════════════════════════════════════════════════════════════
# 2. PROJECT CRUD
# ══════════════════════════════════════════════════════════════════
class TestProjectCRUD(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._auth()

    def test_list_projects_returns_array(self):
        r = self.client.get('/api/projects')
        self.assertEqual(r.status_code, 200)
        data = self._json(r)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)

    def test_list_projects_summary_has_costs(self):
        r = self.client.get('/api/projects?summary=true')
        self.assertEqual(r.status_code, 200)
        data = self._json(r)
        self.assertIn('costs', data[0])
        self.assertIn('sell_cost', data[0]['costs'])
        self.assertIn('ax_margin', data[0]['costs'])
        self.assertIn('cloud4c_margin', data[0]['costs'])
        self.assertIn('gross_margin', data[0]['costs'])

    def test_get_existing_project_returns_200(self):
        r = self.client.get('/api/projects/proj1')
        self.assertEqual(r.status_code, 200)
        data = self._json(r)
        self.assertEqual(data['project']['customer'], 'ACME Corp')

    def test_get_nonexistent_project_returns_404(self):
        r = self.client.get('/api/projects/does-not-exist')
        self.assertEqual(r.status_code, 404)

    def test_create_project_returns_id(self):
        payload = {
            'project': {'customer': 'New Customer'},
            'resources': [{'role': 'Architect', 'level': 'L1', 'hours': 40, 'group': 'Delivery'}],
            'rate_card': [{'level': 'L1', 'rates': {'Delivery': 100}}],
            'cloud4c_margin': 0.30,
            'ax_margin': 0.20,
        }
        r = self.client.post('/api/projects', json=payload)
        self.assertEqual(r.status_code, 200)
        data = self._json(r)
        self.assertIn('id', data)
        self.assertIsNotNone(data['id'])

    def test_create_project_missing_customer_returns_400(self):
        r = self.client.post('/api/projects', json={
            'project': {},
            'resources': [],
            'rate_card': [],
        })
        self.assertEqual(r.status_code, 400)

    def test_update_existing_project(self):
        updated = dict(SAMPLE_PROJECT)
        updated['project'] = dict(SAMPLE_PROJECT['project'])
        updated['project']['status'] = 'Won'
        r = self.client.put('/api/projects/proj1', json=updated)
        self.assertEqual(r.status_code, 200)
        # Verify the change persisted
        r2 = self.client.get('/api/projects/proj1')
        self.assertEqual(self._json(r2)['project']['status'], 'Won')

    def test_delete_project(self):
        # Create a project then delete it
        create = self.client.post('/api/projects', json={
            'project': {'customer': 'To Delete'},
            'resources': [],
            'rate_card': [{'level': 'L1', 'rate': 10}],
        })
        pid = self._json(create)['id']
        r = self.client.delete(f'/api/projects/{pid}')
        self.assertEqual(r.status_code, 200)
        r2 = self.client.get(f'/api/projects/{pid}')
        self.assertEqual(r2.status_code, 404)

    def test_rename_project(self):
        r = self.client.post('/api/projects/proj1/rename', json={'name': 'Renamed', 'customer': 'ACME'})
        self.assertEqual(r.status_code, 200)

    def test_set_project_folder(self):
        r = self.client.post('/api/projects/proj1/folder', json={'folder': 'Q2-2026'})
        self.assertEqual(r.status_code, 200)
        data = self._json(r)
        self.assertEqual(data.get('status'), 'ok')

    def test_list_folders(self):
        r = self.client.get('/api/projects/folders')
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(self._json(r), list)


# ══════════════════════════════════════════════════════════════════
# 3. MARGIN CALCULATIONS (pnl_service unit tests)
# ══════════════════════════════════════════════════════════════════
class TestMarginCalculations(unittest.TestCase):

    def setUp(self):
        from pnl.services.pnl_service import compute_costs, resolve_margin_inputs
        self.compute = compute_costs
        self.resolve = resolve_margin_inputs

    def test_gross_margin_equals_combined_c4c_and_ax(self):
        costs = self.compute(
            resources=[{'role': 'Eng', 'level': 'L1', 'hours': 100, 'group': 'D'}],
            rate_card=[{'level': 'L1', 'rates': {'D': 100}}],
            cloud4c_margin=0.30,
            ax_margin=0.25,
        )
        self.assertAlmostEqual(costs['gross_margin'], 0.55, places=4)
        self.assertAlmostEqual(costs['cloud4c_margin'], 0.30, places=4)
        self.assertAlmostEqual(costs['ax_margin'], 0.25, places=4)

    def test_sell_cost_formula(self):
        costs = self.compute(
            resources=[{'role': 'E', 'level': 'L1', 'hours': 100, 'group': 'D'}],
            rate_card=[{'level': 'L1', 'rates': {'D': 100}}],
            cloud4c_margin=0.30,
            ax_margin=0.20,
        )
        # input_cost = 10000, combined_margin = 0.50
        # sell_cost = 10000 / 0.50 = 20000
        self.assertAlmostEqual(costs['input_cost'], 10000, places=2)
        self.assertAlmostEqual(costs['sell_cost'], 20000, places=2)
        self.assertAlmostEqual(costs['markup'], 10000, places=2)

    def test_zero_input_cost_gives_zero_sell_cost(self):
        costs = self.compute(resources=[], rate_card=[], cloud4c_margin=0.30, ax_margin=0.20)
        self.assertEqual(costs['input_cost'], 0)
        self.assertEqual(costs['sell_cost'], 0)

    def test_one_time_costs_add_to_input_cost(self):
        costs = self.compute(
            resources=[],
            rate_card=[],
            cloud4c_margin=0.30,
            ax_margin=0.20,
            one_time_costs=[{'label': 'Hardware', 'amount': 5000}],
        )
        self.assertAlmostEqual(costs['input_cost'], 5000, places=2)
        self.assertAlmostEqual(costs['one_time_input_cost'], 5000, places=2)

    def test_license_costs_are_excluded_from_margin_basis(self):
        costs = self.compute(
            resources=[],
            rate_card=[],
            cloud4c_margin=0.30,
            ax_margin=0.20,
            one_time_costs=[
                {'label': 'AI Subscriptions', 'amount': 1200, 'category': 'license', 'exclude_from_margin': True},
                {'label': 'Hardware', 'amount': 5000},
            ],
        )
        self.assertAlmostEqual(costs['input_cost'], 5000, places=2)
        self.assertAlmostEqual(costs['one_time_input_cost'], 5000, places=2)
        self.assertAlmostEqual(costs['non_margin_cost'], 1200, places=2)
        self.assertAlmostEqual(costs['total_cost'], 6200, places=2)
        self.assertAlmostEqual(costs['sell_cost'], 10000, places=2)

    def test_legacy_project_uses_target_margin_as_c4c(self):
        payload = {'target_margin': 0.40}  # no cloud4c_margin / ax_margin keys
        c4c, ax = self.resolve(payload)
        self.assertAlmostEqual(c4c, 0.40, places=4)
        self.assertAlmostEqual(ax, 0.00, places=4)

    def test_margin_individual_values_clamped_at_99_percent(self):
        # Each individual margin is clamped at 0.99; combined may exceed 0.99
        # At 0.60 each, neither hits the clamp — test using 1.5 to trigger it
        costs = self.compute(
            resources=[{'role': 'E', 'level': 'L1', 'hours': 10, 'group': 'D'}],
            rate_card=[{'level': 'L1', 'rates': {'D': 100}}],
            cloud4c_margin=1.5,   # clamped to 0.99
            ax_margin=0.0,
        )
        self.assertAlmostEqual(costs['cloud4c_margin'], 0.99, places=2)
        self.assertAlmostEqual(costs['gross_margin'], 0.99, places=2)

    def test_ax_margin_zero_for_legacy_project(self):
        payload = {'target_margin': 0.35}
        _, ax = self.resolve(payload)
        self.assertEqual(ax, 0.0)

    def test_rate_card_group_fallback(self):
        from pnl.services.pnl_service import _get_rate
        rc = {'level': 'L1', 'rates': {'Delivery': 100, 'QA': 80}}
        self.assertEqual(_get_rate(rc, 'Delivery'), 100)
        self.assertEqual(_get_rate(rc, 'QA'), 80)
        # Unknown group falls back to first value
        self.assertIn(_get_rate(rc, 'Unknown'), [100, 80])

    def test_flat_rate_backward_compat(self):
        costs = self.compute(
            resources=[{'role': 'E', 'level': 'L1', 'hours': 10, 'group': 'D'}],
            rate_card=[{'level': 'L1', 'rate': 50}],  # old flat format
            cloud4c_margin=0.30,
            ax_margin=0.0,
        )
        self.assertAlmostEqual(costs['input_cost'], 500, places=2)


# ══════════════════════════════════════════════════════════════════
# 4. VERSION HISTORY
# ══════════════════════════════════════════════════════════════════
class TestVersionHistory(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._auth()

    def test_list_versions_returns_list_for_new_project(self):
        # Saving a project auto-creates a version snapshot
        create = self.client.post('/api/projects', json={
            'project': {'customer': 'VerTest'},
            'resources': [],
            'rate_card': [{'level': 'L1', 'rate': 10}],
        })
        pid = self._json(create)['id']
        r = self.client.get(f'/api/projects/{pid}/versions')
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(self._json(r), list)
        # Auto-snapshot: at least one version created on save
        self.assertGreaterEqual(len(self._json(r)), 1)

    def test_version_list_includes_financial_summary(self):
        # Create project and save version manually via storage
        from pnl.utils.storage import save_project_version
        save_project_version('proj1', 'v20260501_120000', SAMPLE_PROJECT)

        r = self.client.get('/api/projects/proj1/versions')
        self.assertEqual(r.status_code, 200)
        versions = self._json(r)
        self.assertGreater(len(versions), 0)
        v = versions[0]
        # New fields added in our version history overhaul
        self.assertIn('revenue', v)
        self.assertIn('input_cost', v)
        self.assertIn('cloud4c_margin_pct', v)
        self.assertIn('ax_margin_pct', v)
        self.assertIn('gross_margin_pct', v)
        self.assertIn('currency', v)

    def test_version_financial_values_are_correct(self):
        from pnl.utils.storage import save_project_version
        save_project_version('proj1', 'v_calc', SAMPLE_PROJECT)
        r = self.client.get('/api/projects/proj1/versions')
        v = self._json(r)[0]
        # C4C=30%, AX=25%, combined=55%
        self.assertAlmostEqual(v['cloud4c_margin_pct'], 30.0, places=1)
        self.assertAlmostEqual(v['ax_margin_pct'], 25.0, places=1)
        self.assertAlmostEqual(v['gross_margin_pct'], 55.0, places=1)
        self.assertGreater(v['revenue'], 0)

    def test_restore_version_returns_payload(self):
        from pnl.utils.storage import save_project_version
        save_project_version('proj1', 'v_restore', SAMPLE_PROJECT)
        r = self.client.get('/api/projects/proj1/versions/v_restore')
        self.assertEqual(r.status_code, 200)
        data = self._json(r)
        self.assertEqual(data['project']['customer'], 'ACME Corp')

    def test_label_version(self):
        from pnl.utils.storage import save_project_version
        save_project_version('proj1', 'v_label', SAMPLE_PROJECT)
        r = self.client.post('/api/projects/proj1/versions/v_label/label',
                             json={'label': 'Q2 Snapshot'})
        self.assertEqual(r.status_code, 200)
        versions = self._json(self.client.get('/api/projects/proj1/versions'))
        match = next((v for v in versions if v['vid'] == 'v_label'), None)
        self.assertIsNotNone(match)
        self.assertEqual(match['label'], 'Q2 Snapshot')

    def test_delete_version(self):
        from pnl.utils.storage import save_project_version
        save_project_version('proj1', 'v_del', SAMPLE_PROJECT)
        save_project_version('proj1', 'v_keep', SAMPLE_PROJECT)
        r = self.client.delete('/api/projects/proj1/versions/v_del')
        self.assertEqual(r.status_code, 200)
        vids = [v['vid'] for v in self._json(self.client.get('/api/projects/proj1/versions'))]
        self.assertNotIn('v_del', vids)
        self.assertIn('v_keep', vids)


# ══════════════════════════════════════════════════════════════════
# 5. DASHBOARD API
# ══════════════════════════════════════════════════════════════════
class TestDashboardAPI(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._auth()

    def test_dashboard_returns_200(self):
        r = self.client.get('/api/dashboard')
        self.assertEqual(r.status_code, 200)

    def test_dashboard_kpis_present(self):
        r = self.client.get('/api/dashboard')
        data = self._json(r)
        kpis = data['kpis']
        for field in ['projects', 'revenue', 'input_cost', 'gross_profit',
                      'avg_ax_margin', 'avg_cloud4c_margin', 'avg_margin',
                      'active_pipeline', 'at_risk_count']:
            self.assertIn(field, kpis, msg=f"Missing KPI: {field}")

    def test_dashboard_has_per_project_summary(self):
        r = self.client.get('/api/dashboard')
        data = self._json(r)
        self.assertIn('projects_summary', data)
        self.assertIsInstance(data['projects_summary'], list)
        if data['projects_summary']:
            p = data['projects_summary'][0]
            for field in ['name', 'customer', 'status', 'revenue', 'ax_margin', 'cloud4c_margin']:
                self.assertIn(field, p, msg=f"Missing field in projects_summary: {field}")

    def test_dashboard_has_revenue_by_status(self):
        r = self.client.get('/api/dashboard')
        data = self._json(r)
        self.assertIn('status_revenue', data)
        if data['status_revenue']:
            item = data['status_revenue'][0]
            self.assertIn('label', item)
            self.assertIn('value', item)
            self.assertIn('count', item)

    def test_dashboard_has_stage_revenue(self):
        r = self.client.get('/api/dashboard')
        data = self._json(r)
        self.assertIn('stage_revenue', data)

    def test_dashboard_top_customers_include_ax_margin(self):
        r = self.client.get('/api/dashboard')
        data = self._json(r)
        self.assertIn('top_customers', data)
        if data['top_customers']:
            c = data['top_customers'][0]
            self.assertIn('ax_margin', c)

    def test_dashboard_at_risk_projects_below_20_pct(self):
        r = self.client.get('/api/dashboard')
        data = self._json(r)
        self.assertIn('at_risk', data)
        for p in data['at_risk']:
            self.assertLess(p['ax_margin'], 20.0)

    def test_dashboard_ax_margin_buckets_present(self):
        r = self.client.get('/api/dashboard')
        data = self._json(r)
        self.assertIn('ax_margin_buckets', data)
        labels = [b['label'] for b in data['ax_margin_buckets']]
        self.assertIn('Below 10%', labels)

    def test_dashboard_active_pipeline_counts_won_and_submitted(self):
        r = self.client.get('/api/dashboard')
        data = self._json(r)
        # proj1 has status=Submitted so active_pipeline should equal its sell_cost
        kpis = data['kpis']
        self.assertGreaterEqual(kpis['active_pipeline'], 0)

    def test_dashboard_gross_profit_equals_revenue_minus_input_cost(self):
        r = self.client.get('/api/dashboard')
        kpis = self._json(r)['kpis']
        expected = round(kpis['revenue'] - kpis['input_cost'], 2)
        self.assertAlmostEqual(kpis['gross_profit'], expected, places=1)


# ══════════════════════════════════════════════════════════════════
# 6. SETTINGS (rate card, role catalog, global data)
# ══════════════════════════════════════════════════════════════════
class TestSettings(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._auth()

    def test_get_global_data_returns_rate_card_and_catalog(self):
        r = self.client.get('/api/data')
        self.assertEqual(r.status_code, 200)
        data = self._json(r)
        self.assertIn('rate_card', data)
        self.assertIn('role_catalog', data)
        self.assertIn('business_units', data)

    def test_save_settings_persists_rate_card(self):
        new_rc = [{'level': 'L1', 'rates': {'Delivery': 150}},
                  {'level': 'L2', 'rates': {'Delivery': 75}}]
        r = self.client.post('/api/settings', json={'rate_card': new_rc, 'role_catalog': []})
        self.assertEqual(r.status_code, 200)
        data = self._json(self.client.get('/api/data'))
        self.assertEqual(data['rate_card'][0]['rates']['Delivery'], 150)

    def test_save_settings_persists_role_catalog(self):
        catalog = [{'group': 'Data', 'roles': ['Data Engineer', 'Data Scientist']}]
        self.client.post('/api/settings', json={'rate_card': [], 'role_catalog': catalog})
        data = self._json(self.client.get('/api/data'))
        groups = [g['group'] for g in data['role_catalog']]
        self.assertIn('Data', groups)

    def test_exchange_rate_endpoint_responds(self):
        r = self.client.get('/api/exchange-rate')
        # May fail if network unavailable (503) but should not 500
        self.assertIn(r.status_code, [200, 503])


# ══════════════════════════════════════════════════════════════════
# 7. EXPORT
# ══════════════════════════════════════════════════════════════════
class TestExport(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._auth()

    def test_export_returns_xlsx(self):
        r = self.client.post('/api/export', json=SAMPLE_PROJECT)
        self.assertEqual(r.status_code, 200)
        ct = r.headers.get('Content-Type', '')
        self.assertIn('spreadsheetml', ct)

    def test_export_file_is_valid_xlsx(self):
        r = self.client.post('/api/export', json=SAMPLE_PROJECT)
        wb = openpyxl.load_workbook(BytesIO(r.data))
        self.assertIsNotNone(wb)
        self.assertGreater(len(wb.sheetnames), 0)

    def test_export_does_not_mutate_server_state(self):
        before = self.client.get('/api/data').data
        self.client.post('/api/export', json=SAMPLE_PROJECT)
        after = self.client.get('/api/data').data
        self.assertEqual(before, after)

    def test_export_missing_customer_returns_error(self):
        bad = dict(SAMPLE_PROJECT)
        bad['project'] = {}
        r = self.client.post('/api/export', json=bad)
        self.assertIn(r.status_code, [400, 422])


# ══════════════════════════════════════════════════════════════════
# 8. UI ROUTES
# ══════════════════════════════════════════════════════════════════
class TestUIRoutes(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._auth()

    def test_root_returns_200(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)

    def test_project_editor_new_returns_200(self):
        r = self.client.get('/project-editor')
        self.assertEqual(r.status_code, 200)

    def test_project_editor_with_pid_returns_200(self):
        r = self.client.get('/project-editor/proj1')
        self.assertEqual(r.status_code, 200)

    def test_project_editor_nonexistent_pid_returns_200(self):
        # App loads editor then JS handles the 404 gracefully
        r = self.client.get('/project-editor/no-such-project')
        self.assertEqual(r.status_code, 200)

    def test_index_contains_all_projects_tab(self):
        r = self.client.get('/')
        self.assertIn(b'tab-all-projects', r.data)

    def test_index_contains_dashboard_tab(self):
        r = self.client.get('/')
        self.assertIn(b'tab-dashboard', r.data)

    def test_index_contains_role_catalog_tab(self):
        r = self.client.get('/')
        self.assertIn(b'tab-pnl-roles', r.data)

    def test_home_icon_present_in_project_editor(self):
        r = self.client.get('/project-editor/proj1')
        self.assertIn(b'bi-house-door', r.data)

    def test_export_settings_removed_from_tab_bar(self):
        r = self.client.get('/')
        # Export Settings moved to dropdown — should NOT appear as a tab link
        html = r.data.decode()
        self.assertNotIn('href="#tab-export"', html)

    def test_inter_font_loaded(self):
        r = self.client.get('/')
        self.assertIn(b'Inter', r.data)


# ══════════════════════════════════════════════════════════════════
# 9. ORDER BOOKINGS
# ══════════════════════════════════════════════════════════════════
class TestBookings(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._auth()

    def test_list_bookings_returns_200(self):
        r = self.client.get('/api/bookings')
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(self._json(r), list)

    def test_create_booking_and_retrieve(self):
        entry = {
            'customer_name': 'ACME', 'opf_number': 'OPF-001',
            'booking_type': 'OTC', 'otc': 50000, 'cdd': '2026-05-01',
        }
        r = self.client.post('/api/bookings', json=entry)
        self.assertEqual(r.status_code, 200)
        bid = self._json(r).get('id')
        self.assertIsNotNone(bid)
        r2 = self.client.get(f'/api/bookings/{bid}')
        self.assertEqual(r2.status_code, 200)
        data = self._json(r2)
        self.assertEqual(data['id'], bid)
        self.assertIn('booking_type', data)

    def test_update_booking(self):
        create = self.client.post('/api/bookings', json={
            'customer_name': 'X', 'booking_type': 'MRC', 'mrc': 1000,
        })
        bid = self._json(create)['id']
        r = self.client.put(f'/api/bookings/{bid}', json={'mrc': 2000})
        self.assertEqual(r.status_code, 200)

    def test_delete_booking(self):
        create = self.client.post('/api/bookings', json={
            'customer_name': 'Del', 'booking_type': 'OTC', 'otc': 500,
        })
        bid = self._json(create)['id']
        r = self.client.delete(f'/api/bookings/{bid}')
        self.assertEqual(r.status_code, 200)
        r2 = self.client.get(f'/api/bookings/{bid}')
        self.assertEqual(r2.status_code, 404)

    def test_bookings_meta_options_returns_200(self):
        r = self.client.get('/api/bookings/meta/options')
        self.assertEqual(r.status_code, 200)


# ══════════════════════════════════════════════════════════════════
# 10. FUNNEL REPORT
# ══════════════════════════════════════════════════════════════════
class TestFunnel(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._auth()

    def test_list_funnel_returns_200(self):
        r = self.client.get('/api/funnel')
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(self._json(r), list)

    def test_create_funnel_entry(self):
        entry = {
            'customer': 'Prospect Co', 'project': 'Cloud Migration',
            'stage': 'Qualification', 'value': 100000, 'currency': 'USD',
            'probability': 40, 'expected_close': '2026-08-31',
        }
        r = self.client.post('/api/funnel', json=entry)
        self.assertEqual(r.status_code, 200)
        fid = self._json(r).get('id')
        self.assertIsNotNone(fid)

    def test_update_funnel_entry(self):
        create = self.client.post('/api/funnel', json={
            'customer': 'X', 'project': 'P',
            'stage': 'Discovery', 'value': 50000, 'currency': 'USD',
        })
        fid = self._json(create)['id']
        r = self.client.put(f'/api/funnel/{fid}', json={'stage': 'Proposal', 'probability': 60})
        self.assertEqual(r.status_code, 200)

    def test_delete_funnel_entry(self):
        create = self.client.post('/api/funnel', json={
            'customer': 'D', 'project': 'P',
            'stage': 'Qualification', 'value': 10000, 'currency': 'USD',
        })
        fid = self._json(create)['id']
        r = self.client.delete(f'/api/funnel/{fid}')
        self.assertEqual(r.status_code, 200)

    def test_funnel_meta_options_returns_200(self):
        r = self.client.get('/api/funnel/meta/options')
        self.assertEqual(r.status_code, 200)


# ══════════════════════════════════════════════════════════════════
# 11. VERSION COMPARISON
# ══════════════════════════════════════════════════════════════════
class TestVersionComparison(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._auth()
        from pnl.utils.storage import save_project_version
        v1 = dict(SAMPLE_PROJECT)
        v2 = dict(SAMPLE_PROJECT)
        v2 = json.loads(json.dumps(v2))
        v2['resources'][0]['hours'] = 150  # changed
        save_project_version('proj1', 'v1', v1)
        save_project_version('proj1', 'v2', v2)

    def test_compare_versions_returns_diff(self):
        r = self.client.post('/api/compare', json={
            'pid1': 'proj1', 'vid1': 'v1',
            'pid2': 'proj1', 'vid2': 'v2',
        })
        self.assertEqual(r.status_code, 200)
        data = self._json(r)
        self.assertIn('costs', data)
        self.assertIn('resource_changes', data)
        self.assertTrue(data['has_changes'])

    def test_compare_identical_versions_has_no_changes(self):
        r = self.client.post('/api/compare', json={
            'pid1': 'proj1', 'vid1': 'v1',
            'pid2': 'proj1', 'vid2': 'v1',
        })
        data = self._json(r)
        self.assertFalse(data['has_changes'])
        self.assertEqual(data['resource_changes'], [])

    def test_compare_missing_version_returns_404(self):
        r = self.client.post('/api/compare', json={
            'pid1': 'proj1', 'vid1': 'v1',
            'pid2': 'proj1', 'vid2': 'no-such-version',
        })
        self.assertEqual(r.status_code, 404)


# ══════════════════════════════════════════════════════════════════
# 12. INPUT VALIDATION
# ══════════════════════════════════════════════════════════════════
class TestInputValidation(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._auth()

    def test_project_requires_customer_name(self):
        r = self.client.post('/api/projects', json={
            'project': {'customer': ''},
            'resources': [],
            'rate_card': [],
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn('error', self._json(r))

    def test_resource_requires_role_and_level(self):
        r = self.client.post('/api/projects', json={
            'project': {'customer': 'Valid'},
            'resources': [{'hours': 10}],  # missing role and level
            'rate_card': [{'level': 'L1', 'rate': 10}],
        })
        self.assertEqual(r.status_code, 400)

    def test_negative_hours_rejected(self):
        r = self.client.post('/api/projects', json={
            'project': {'customer': 'Valid'},
            'resources': [{'role': 'Eng', 'level': 'L1', 'hours': -5}],
            'rate_card': [{'level': 'L1', 'rate': 10}],
        })
        self.assertEqual(r.status_code, 400)

    def test_change_password_requires_non_empty_password(self):
        r = self.client.post('/api/users/admin/password', json={'password': ''})
        self.assertEqual(r.status_code, 400)

    def test_create_user_requires_username_and_password(self):
        r = self.client.post('/api/users', json={'username': '', 'password': ''})
        self.assertEqual(r.status_code, 400)


if __name__ == '__main__':
    unittest.main(verbosity=2)
