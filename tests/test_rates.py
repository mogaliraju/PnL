"""Phase 5: versioned rate cards and roles (Postgres)."""
from pg_support import PgAppTestCase


class TestRateCards(PgAppTestCase):
    def setUp(self):
        super().setUp()
        self.auth()

    def matrix(self, v):
        return self.client.get(f'/api/rate-cards/{v}').get_json()

    def test_published_matrix(self):
        m = self.client.get('/api/rate-cards/published').get_json()
        self.assertEqual(m['card']['version'], 1)
        self.assertEqual(m['card']['status'], 'published')
        self.assertEqual(m['rates'][str(self.cat['Data'])][str(self.lv['L2'])], 30)
        self.assertIsNone(m['rates'][str(self.cat['BI'])][str(self.lv['L2'])])   # not offered

    def test_published_is_read_only(self):
        r = self.client.put('/api/rate-cards/1/rates', json={'rates': [
            {'category_id': self.cat['Data'], 'level_id': self.lv['L1'], 'rate_usd': 99}]})
        self.assertEqual(r.status_code, 409)
        self.assertIn('read only', r.get_json()['error'])
        self.assertEqual(self.matrix(1)['rates'][str(self.cat['Data'])][str(self.lv['L1'])], 20)

    def test_draft_edit_publish_cycle(self):
        r = self.client.post('/api/rate-cards/draft', json={})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()['card']['version'], 2)
        self.assertEqual(self.client.post('/api/rate-cards/draft', json={}).status_code, 409)   # only one draft
        r = self.client.put('/api/rate-cards/2/rates', json={'rates': [
            {'category_id': self.cat['Data'], 'level_id': self.lv['L1'], 'rate_usd': 22},
            {'category_id': self.cat['BI'], 'level_id': self.lv['L2'], 'rate_usd': 26}]})
        self.assertEqual(r.status_code, 200)
        m = r.get_json()
        self.assertEqual(m['published_rates'][str(self.cat['Data'])][str(self.lv['L1'])], 20)   # "was $20"
        r = self.client.post('/api/rate-cards/2/publish', json={'effective_from': '2027-01-01'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['changes'], 2)
        cards = {c['version']: c['status'] for c in self.client.get('/api/rate-cards').get_json()}
        self.assertEqual(cards, {1: 'archived', 2: 'published'})
        self.assertEqual(self.client.put('/api/rate-cards/1/rates', json={'rates': []}).status_code, 409)

    def test_rate_validation(self):
        self.client.post('/api/rate-cards/draft', json={})
        for bad in ({'category_id': 999999, 'level_id': self.lv['L1'], 'rate_usd': 1},
                    {'category_id': self.cat['Data'], 'level_id': self.lv['L1'], 'rate_usd': -5},
                    {'category_id': self.cat['Data'], 'level_id': self.lv['L1'], 'rate_usd': 'abc'}):
            self.assertEqual(self.client.put('/api/rate-cards/2/rates', json={'rates': [bad]}).status_code, 400, bad)

    def test_writes_need_admin(self):
        self.auth('viewer')
        self.assertEqual(self.client.get('/api/rate-cards').status_code, 200)
        self.assertEqual(self.client.post('/api/rate-cards/draft', json={}, headers={'Content-Type': 'application/json'}).status_code, 403)
        self.assertEqual(self.client.post('/api/roles', json={'category_id': self.cat['Data'], 'name': 'X'}).status_code, 403)

    def test_diff_for_project(self):
        payload = {'_meta': {'id': 'p1', 'name': 'P1'}, 'project': {'customer': 'C'},
                   'resources': [{'group': 'Data', 'role': 'Data engineer', 'level': 'L1', 'hours': 100}],
                   'rate_card': [{'level': 'L1', 'rates': {'Data': 20}}], 'cloud4c_margin': 0.4, 'ax_margin': 0.1}
        self.storage.save_project_record('p1', payload)
        self.client.post('/api/rate-cards/draft', json={})
        self.client.put('/api/rate-cards/2/rates', json={'rates': [
            {'category_id': self.cat['Data'], 'level_id': self.lv['L1'], 'rate_usd': 25}]})
        d = self.client.get('/api/rate-cards/diff?from=1&to=2&project_id=p1').get_json()
        self.assertEqual(d['cells'], [{'category': 'Data', 'level': 'L1', 'from': 20, 'to': 25}])
        self.assertEqual(d['project']['lines'][0]['cost_change'], 500)
        self.assertEqual(d['project']['cost_basis_change'], 500)
        self.assertEqual(d['project']['contract_value_change'], 1000)     # 500 / (1 - 0.5)


class TestRoles(PgAppTestCase):
    def setUp(self):
        super().setUp()
        self.auth()

    def roles(self):
        return {r['name']: r for r in self.client.get('/api/roles').get_json()['roles']}

    def test_add_role_and_duplicate(self):
        r = self.client.post('/api/roles', json={'category_id': self.cat['Data'], 'name': 'Analytics engineer'})
        self.assertEqual(r.status_code, 201)
        r = self.client.post('/api/roles', json={'category_id': self.cat['Data'], 'name': 'analytics ENGINEER'})
        self.assertEqual(r.status_code, 409)
        self.assertIn('already has', r.get_json()['error'])
        # same name in another category is fine
        self.assertEqual(self.client.post('/api/roles', json={'category_id': self.cat['BI'], 'name': 'Analytics engineer'}).status_code, 201)

    def test_switch_off_never_delete(self):
        rid = self.roles()['Data engineer']['id']
        self.assertEqual(self.client.patch(f'/api/roles/{rid}', json={'active': False}).status_code, 200)
        self.assertFalse(self.roles()['Data engineer']['active'])
        self.assertEqual(self.client.delete(f'/api/roles/{rid}').status_code, 405)
        catalog = {g['group']: g['roles'] for g in self.storage.load_global_settings()['role_catalog']}
        self.assertNotIn('Data engineer', catalog['Data'])        # hidden from pickers

    def test_rename_keeps_id(self):
        rid = self.roles()['Data engineer']['id']
        self.client.patch(f'/api/roles/{rid}', json={'name': 'Senior data engineer'})
        self.assertEqual(self.roles()['Senior data engineer']['id'], rid)

    def test_used_in_counts_open_projects(self):
        payload = {'project': {'customer': 'C'}, 'resources': [{'group': 'Data', 'role': 'Data engineer', 'level': 'L1', 'hours': 1}]}
        self.storage.save_project_record('p1', payload)
        self.storage.save_project_record('p2', payload)
        self.assertEqual(self.roles()['Data engineer']['used_in'], 2)
        self.storage.archive_project_record('p2', 'admin')
        self.assertEqual(self.roles()['Data engineer']['used_in'], 1)

    def test_categories(self):
        self.assertEqual(self.client.post('/api/role-categories', json={'name': 'Governance'}).status_code, 201)
        self.assertEqual(self.client.post('/api/role-categories', json={'name': 'governance'}).status_code, 409)


class TestSettingsIntegration(PgAppTestCase):
    """Legacy screens read the new tables; the old settings blob stays frozen."""

    def setUp(self):
        super().setUp()
        self.auth()
        self.storage._set_state(self.conn, 'global_settings',
                                {'rate_card': [{'level': 'L1', 'rate': 1}], 'role_catalog': [{'group': 'Old', 'roles': ['x']}],
                                 'business_units': ['EDM']})

    def frozen(self):
        return self.storage._get_state(self.conn, 'global_settings', {})

    def test_settings_come_from_rate_card_tables(self):
        s = self.storage.load_global_settings()
        self.assertEqual(s['rate_card_version'], 1)
        self.assertEqual(s['rate_card'][0], {'level': 'L1', 'rates': {'Data': 20.0, 'BI': 18.0}})
        self.assertEqual(s['rate_card'][1], {'level': 'L2', 'rates': {'Data': 30.0}})
        self.assertEqual({g['group'] for g in s['role_catalog']}, {'Data', 'BI'})

    def test_old_settings_blob_is_never_overwritten(self):
        before = self.frozen()
        self.client.post('/api/settings', json={'rate_card': [{'level': 'L9', 'rate': 9}], 'role_catalog': []})
        self.client.post('/api/projects', json={'project': {'customer': 'C'}, 'resources': [],
                                                'rate_card': [{'level': 'L7', 'rate': 7}], 'role_catalog': [{'group': 'Z', 'roles': []}]})
        after = self.frozen()
        self.assertEqual(after['rate_card'], before['rate_card'])
        self.assertEqual(after['role_catalog'], before['role_catalog'])

    def test_saved_project_keeps_its_own_rates(self):
        payload = {'_meta': {'id': 'p1'}, 'project': {'customer': 'C'}, 'resources': [],
                   'rate_card': [{'level': 'L1', 'rates': {'Data': 11}}]}
        self.storage.save_project_record('p1', payload)
        loaded = self.client.get('/api/projects/p1').get_json()
        self.assertEqual(loaded['rate_card'], payload['rate_card'])
        self.assertEqual(loaded['published_rate_card_version'], 1)

    def test_versions_get_numbers_and_card(self):
        self.storage.save_project_record('p1', {'project': {}, 'resources': [], 'rate_card_version': 1})
        for vid in ('a', 'b', 'c'):
            self.storage.save_project_version('p1', vid, {'project': {}, 'rate_card_version': 1})
        rows = self.q("SELECT vid, version_no, rate_card_id FROM project_versions WHERE pid='p1' ORDER BY version_no").fetchall()
        self.assertEqual([(r['vid'], r['version_no']) for r in rows], [('a', 1), ('b', 2), ('c', 3)])
        self.assertTrue(all(r['rate_card_id'] == self.v1 for r in rows))
        self.assertEqual(self.q("SELECT rate_card_id FROM projects WHERE pid='p1'").fetchone()['rate_card_id'], self.v1)
