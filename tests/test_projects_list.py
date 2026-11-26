"""Phase 4: Projects list API, archive instead of delete, per-user preferences, migrations."""
import os
import tempfile
import unittest
from pathlib import Path

from test_pnl_suite import BaseTestCase, SAMPLE_PROJECT


class TestArchive(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._auth()

    def test_archive_hides_from_list_and_keeps_versions(self):
        from pnl.utils.storage import save_project_version
        save_project_version('proj1', 'v1', SAMPLE_PROJECT)
        r = self.client.post('/api/projects/proj1/archive')
        self.assertEqual(r.get_json()['status'], 'archived')
        self.assertEqual(self.client.get('/api/projects').get_json(), [])
        archived = self.client.get('/api/projects?archived=true').get_json()
        self.assertEqual([p['id'] for p in archived], ['proj1'])
        self.assertTrue(archived[0]['archived_at'])
        self.assertEqual(archived[0]['archived_by'], 'admin')
        self.assertEqual(len(self.client.get('/api/projects/proj1/versions').get_json()), 1)
        # archiving twice is harmless
        self.assertEqual(self.client.post('/api/projects/proj1/archive').get_json()['status'], 'already archived')

    def test_unknown_project(self):
        self.assertEqual(self.client.post('/api/projects/nope/archive').status_code, 404)
        self.assertEqual(self.client.post('/api/projects/proj1/restore').status_code, 404)  # not archived

    def test_user_can_undo_own_archive_but_not_others(self):
        self.client.post('/api/projects/proj1/archive')            # archived by admin
        self._auth('viewer')
        self.assertEqual(self.client.post('/api/projects/proj1/restore').status_code, 403)
        self._auth('admin')
        self.assertEqual(self.client.post('/api/projects/proj1/restore').status_code, 200)
        self._auth('viewer')
        self.client.post('/api/projects/proj1/archive')            # archived by viewer
        self.assertEqual(self.client.post('/api/projects/proj1/restore').status_code, 200)

    def test_no_sql_delete_paths_left_for_projects(self):
        src = (Path(__file__).resolve().parents[1] / 'pnl' / 'utils' / 'storage.py').read_text()
        self.assertNotIn('DELETE FROM projects', src)
        self.assertNotIn('DELETE FROM project_versions', src)


class TestListSummary(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._auth()

    def test_summary_has_engine_figures_and_version_count(self):
        from pnl.utils.storage import save_project_version
        save_project_version('proj1', 'v1', SAMPLE_PROJECT)
        save_project_version('proj1', 'v2', SAMPLE_PROJECT)
        p = self.client.get('/api/projects?summary=true').get_json()[0]
        self.assertEqual(p['version_count'], 2)
        self.assertEqual(p['calc_mode'], 'legacy')
        for k in ('contract_value', 'cost_basis', 'list_price', 'ax_net_pct', 'c4c_pct', 'hours'):
            self.assertIn(k, p['pnl'])
        self.assertAlmostEqual(p['pnl']['contract_value'], p['costs']['sell_cost'], places=2)


class TestPrefs(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._auth()

    def test_roundtrip_per_user(self):
        self.assertEqual(self.client.get('/api/prefs/projects_list').get_json(), {})
        pref = {'cols': ['project', 'status'], 'view': 'mine', 'filters': {'status': ['Won']}}
        self.assertEqual(self.client.put('/api/prefs/projects_list', json=pref).status_code, 200)
        self.assertEqual(self.client.get('/api/prefs/projects_list').get_json(), pref)
        self._auth('viewer')
        self.assertEqual(self.client.get('/api/prefs/projects_list').get_json(), {})

    def test_validation(self):
        self.assertEqual(self.client.put('/api/prefs/other', json={}).status_code, 404)
        self.assertEqual(self.client.put('/api/prefs/projects_list', json=[1]).status_code, 400)
        self.assertEqual(self.client.put('/api/prefs/projects_list', json={'x': 'y' * 30000}).status_code, 400)


class TestMigrations(unittest.TestCase):
    def test_all_migrations_are_additive(self):
        from pnl.migrate import check_additive, migration_files
        files = migration_files()
        self.assertTrue(files)
        for f in files:
            check_additive(f)

    def test_destructive_sql_is_rejected(self):
        from pnl.migrate import MigrationError, check_additive
        for bad in ('DROP TABLE users;', 'delete from projects;', 'UPDATE projects SET name = 1;',
                    'ALTER TABLE projects RENAME COLUMN name TO n;', 'TRUNCATE projects;',
                    'ALTER TABLE projects ALTER COLUMN name TYPE int;'):
            with tempfile.NamedTemporaryFile('w', suffix='.sql', delete=False) as t:
                t.write(bad)
            with self.assertRaises(MigrationError, msg=bad):
                check_additive(Path(t.name))
            os.unlink(t.name)
        with tempfile.NamedTemporaryFile('w', suffix='.sql', delete=False) as t:
            t.write('-- we never DROP anything\nCREATE TABLE IF NOT EXISTS x (a int);')
        check_additive(Path(t.name))       # words in comments are fine
        os.unlink(t.name)

    @unittest.skipUnless(os.environ.get('PNL_TEST_PG_URL'), 'set PNL_TEST_PG_URL to a local copy to run')
    def test_dry_run_on_postgres_copy_keeps_counts(self):
        import psycopg
        from pnl.migrate import _counts, run
        with psycopg.connect(os.environ['PNL_TEST_PG_URL']) as conn:
            before = _counts(conn)
            conn.rollback()
            run(conn, dry_run=True, log=lambda *_: None)
            self.assertEqual(_counts(conn), before)
            conn.rollback()
