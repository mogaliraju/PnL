"""Phase 7: users are switched off, never deleted; temporary passwords; own password change."""
from werkzeug.security import generate_password_hash

from test_pnl_suite import BaseTestCase


class TestUsers(BaseTestCase):
    def setUp(self):
        super().setUp()
        from pnl.utils.storage import set_user_password
        set_user_password('admin', generate_password_hash('admin-pass-1'))
        set_user_password('viewer', generate_password_hash('viewer-pass-1'))
        self._auth()

    def login(self, user, pw):
        self.client = self.app.test_client()
        return self.client.post('/login', json={'username': user, 'password': pw})

    def users(self):
        return {u['username']: u for u in self.client.get('/api/users').get_json()}

    def test_create_user_is_temporary_and_validated(self):
        self.assertEqual(self.client.post('/api/users', json={'username': 'Bad Name', 'password': 'longenough'}).status_code, 400)
        self.assertEqual(self.client.post('/api/users', json={'username': 'ravi', 'password': 'short'}).status_code, 400)
        self.assertEqual(self.client.post('/api/users', json={'username': 'ravi', 'password': 'temp-pass-1', 'role': 'owner'}).status_code, 400)
        self.assertEqual(self.client.post('/api/users', json={'username': 'ravi', 'password': 'temp-pass-1', 'name': 'Ravi K'}).status_code, 200)
        self.assertEqual(self.client.post('/api/users', json={'username': 'ravi', 'password': 'temp-pass-1'}).status_code, 409)
        self.assertTrue(self.users()['ravi']['must_change_password'])

    def test_remove_switches_off_and_keeps_row(self):
        r = self.client.delete('/api/users/viewer')
        self.assertEqual(r.get_json()['status'], 'removed')
        u = self.users()['viewer']
        self.assertFalse(u['active'])
        self.assertTrue(u['deactivated_at'])
        r = self.login('viewer', 'viewer-pass-1')
        self.assertEqual(r.status_code, 403)
        self.assertIn('switched off', r.get_json()['error'])
        self.login('admin', 'admin-pass-1')
        self.client.post('/api/users/viewer/active', json={'active': True})
        self.assertEqual(self.login('viewer', 'viewer-pass-1').status_code, 200)

    def test_cannot_remove_self_or_last_admin(self):
        self.assertEqual(self.client.delete('/api/users/admin').status_code, 400)          # yourself
        self.client.post('/api/users', json={'username': 'boss', 'password': 'temp-pass-1', 'role': 'admin'})
        self._auth('viewer')                                    # a non-admin can't do any of this
        self.assertEqual(self.client.delete('/api/users/boss').status_code, 403)

    def test_last_active_admin_guard(self):
        from pnl.utils.storage import create_user
        create_user('other', generate_password_hash('x' * 10), 'admin', 'Other admin')
        with self.client.session_transaction() as s:
            s['user'] = 'other'; s['role'] = 'admin'; s['name'] = 'Other'
        self.assertEqual(self.client.delete('/api/users/admin').status_code, 200)     # two admins: fine
        self.assertEqual(self.client.post('/api/users/admin/active', json={'active': True}).status_code, 200)
        self.client.delete('/api/users/admin')
        with self.client.session_transaction() as s:
            s['user'] = 'nobody-admin'; s['role'] = 'admin'
        r = self.client.delete('/api/users/other')
        self.assertEqual(r.status_code, 400)
        self.assertIn('last active admin', r.get_json()['error'])

    def test_admin_reset_forces_change_at_next_sign_in(self):
        self.assertEqual(self.client.post('/api/users/viewer/password', json={'password': 'reset-pass-1'}).status_code, 200)
        r = self.login('viewer', 'reset-pass-1')
        self.assertTrue(r.get_json()['must_change_password'])
        self.assertEqual(self.client.get('/api/projects').status_code, 403)              # blocked until changed
        self.assertEqual(self.client.get('/').status_code, 302)
        bad = self.client.post('/api/users/viewer/password', json={'current_password': 'wrong', 'password': 'my-own-pass'})
        self.assertEqual(bad.status_code, 400)
        same = self.client.post('/api/users/viewer/password', json={'current_password': 'reset-pass-1', 'password': 'reset-pass-1'})
        self.assertEqual(same.status_code, 400)
        ok = self.client.post('/api/users/viewer/password', json={'current_password': 'reset-pass-1', 'password': 'my-own-pass'})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.client.get('/api/projects').status_code, 200)
        self.assertFalse(self.login('viewer', 'my-own-pass').get_json()['must_change_password'])

    def test_own_change_needs_current_password(self):
        r = self.client.post('/api/users/admin/password', json={'password': 'new-pass-123'})
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/users/admin/password', json={'current_password': 'admin-pass-1', 'password': 'new-pass-123'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.login('admin', 'new-pass-123').status_code, 200)

    def test_no_delete_sql_for_users(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] / 'pnl' / 'utils' / 'storage.py').read_text()
        self.assertNotIn('DELETE FROM users', src)

    def test_pages(self):
        html = self.client.get('/admin/users').data.decode()
        self.assertIn('js/users.js', html)
        self.assertIn('data-ax-action="change-password"', html)
        self.assertIn('id="ax-dash-root"', self.client.get('/dashboard').data.decode())
