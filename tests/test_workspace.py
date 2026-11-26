"""Phase 6: workspace API (options, live calculation, compare) and mode-aware export."""
from test_pnl_suite import BaseTestCase, SAMPLE_PROJECT


class TestWorkspaceApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._auth()

    def test_options(self):
        o = self.client.get('/api/workspace/options').get_json()
        self.assertEqual(o['statuses'], ['Draft', 'Submitted', 'Won', 'Lost', 'On hold'])
        self.assertIn('Commercial review', o['stages'])
        self.assertIn('India', o['countries'])
        self.assertEqual({p['username'] for p in o['people']}, {'admin', 'viewer'})
        self.assertEqual(o['thresholds'], {'good': 20.0, 'warn': 10.0})

    def test_calculate_unsaved_snapshot(self):
        snap = {**SAMPLE_PROJECT, 'calc_mode': 'v2', 'cloud4c_margin': 0.30, 'ax_margin': 0.20}
        r = self.client.post('/api/pnl/calculate', json={'snapshot': snap})
        self.assertEqual(r.status_code, 200)
        res = r.get_json()['result']
        self.assertEqual(res['mode'], 'v2')
        self.assertEqual(res['cost_basis'], 20000.0)          # 100 x 100 + 200 x 50
        self.assertEqual(res['list_price'], 40000.0)
        self.assertEqual(len(res['lines']), 2)

    def test_calculate_reports_lever_errors(self):
        snap = {**SAMPLE_PROJECT, 'calc_mode': 'v2', 'cloud4c_margin': 0.6, 'ax_margin': 0.4}
        r = self.client.post('/api/pnl/calculate', json={'snapshot': snap})
        self.assertEqual(r.status_code, 422)
        self.assertIn('ax_margin', r.get_json()['errors'])

    def test_calculate_compare_modes(self):
        snap = {**SAMPLE_PROJECT, 'project': {**SAMPLE_PROJECT['project'], 'travel_cost': 1000, 'discount_pct': 10}}
        out = self.client.post('/api/pnl/calculate', json={'snapshot': snap, 'mode': 'legacy', 'compare_mode': 'v2'}).get_json()
        self.assertEqual(out['result']['mode'], 'legacy')
        self.assertEqual(out['compare']['mode'], 'v2')
        self.assertEqual(out['compare']['addons_pass'], 1000.0)        # travel passes through by default
        self.assertGreater(out['compare']['discount'], 0)
        self.assertEqual(out['result']['discount'], 0)                  # legacy ignores it

    def test_compare_versions(self):
        from pnl.utils.storage import save_project_version
        a = {**SAMPLE_PROJECT}
        b = {**SAMPLE_PROJECT, 'resources': [{'role': 'Architect', 'level': 'L1', 'hours': 150, 'group': 'Delivery'}]}
        save_project_version('proj1', 'va', a)
        save_project_version('proj1', 'vb', b)
        d = self.client.get('/api/projects/proj1/compare?a=va&b=vb').get_json()
        self.assertEqual(d['b']['hours'], 150.0)
        statuses = {(c['role'], c['status']) for c in d['resource_changes']}
        self.assertEqual(statuses, {('Architect', 'changed'), ('Engineer', 'removed')})
        self.assertEqual(self.client.get('/api/projects/proj1/compare?a=va&b=nope').status_code, 404)

    def test_versions_have_numbers_and_figures(self):
        from pnl.utils.storage import save_project_version
        save_project_version('proj1', '20260101_000000', SAMPLE_PROJECT)
        save_project_version('proj1', '20260102_000000', SAMPLE_PROJECT)
        vs = self.client.get('/api/projects/proj1/versions').get_json()
        self.assertEqual([v['version_no'] for v in vs], [2, 1])
        self.assertIn('contract_value', vs[0]['pnl'])

    def test_save_returns_version_and_keeps_name(self):
        r = self.client.put('/api/projects/proj1', json={**SAMPLE_PROJECT, '_meta': {'name': 'Renamed'}}).get_json()
        self.assertTrue(r['vid'])
        self.assertEqual(r['name'], 'Renamed')

    def test_export_uses_projects_calculation(self):
        import io
        import openpyxl
        legacy = self.client.post('/api/export', json={**SAMPLE_PROJECT, 'download_name': 'a'})
        v2 = self.client.post('/api/export', json={**SAMPLE_PROJECT, 'calc_mode': 'v2', 'download_name': 'b',
                                                    'project': {**SAMPLE_PROJECT['project'], 'third_party_cost': 5000}})
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(v2.status_code, 200)
        cells = lambda r: {c.value for ws in openpyxl.load_workbook(io.BytesIO(r.data)).worksheets for row in ws.iter_rows() for c in row}
        self.assertNotEqual(cells(legacy), cells(v2))     # third-party cost counted only in v2
        bad = self.client.post('/api/export', json={**SAMPLE_PROJECT, 'calc_mode': 'v2', 'ax_margin': 0.9, 'cloud4c_margin': 0.3})
        self.assertEqual(bad.status_code, 400)
