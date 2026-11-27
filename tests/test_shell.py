"""Phase 2: AX shell, tokens, routes and components."""
import json
import subprocess
import sys
from pathlib import Path

from test_pnl_suite import BaseTestCase

ROOT = Path(__file__).resolve().parents[1]


class TestTokens(BaseTestCase):
    def test_token_css_matches_figma_tokens(self):
        r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_tokens.py'), '--check'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_margin_thresholds_match_tokens(self):
        from pnl import config
        tokens = json.loads((ROOT / 'design' / 'figma-tokens.json').read_text(encoding='utf-8'))
        self.assertEqual(config.AX_MARGIN_GOOD, tokens['threshold']['ax-margin-good']['$value'])
        self.assertEqual(config.AX_MARGIN_WARN, tokens['threshold']['ax-margin-warn']['$value'])

    def test_health_classes(self):
        from pnl.ui import health_class
        self.assertEqual([health_class(v) for v in (25, 20, 19.9, 10, 9.99, None)],
                         ['good', 'good', 'warn', 'warn', 'bad', 'bad'])


class TestShellRoutes(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._auth()

    def test_home_pages_render_in_shell(self):
        from pnl import config
        config.FEATURE_BOOKINGS_FUNNEL = True
        self.addCleanup(setattr, config, 'FEATURE_BOOKINGS_FUNNEL', False)
        for path, nav, tab in (('/', 'projects', 'projects'), ('/dashboard', 'dashboard', 'dashboard'),
                               ('/rates', 'rates', 'rates'), ('/rates/roles', 'rates', 'roles'),
                               ('/bookings', 'bookings', 'bookings'), ('/funnel', 'funnel', 'funnel')):
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
                html = r.data.decode()
                self.assertIn('class="ax-rail"', html)
                self.assertIn(f'data-ax-route="{nav}" class="is-active"', html)
                self.assertIn(f'data-initial-tab="{tab}"', html)
                self.assertIn('ax-legacy-tabs', html)          # rail drives the old tabs

    def test_project_pages_render_the_workspace(self):
        html = self.client.get('/projects/proj1').data.decode()
        self.assertIn('id="ax-ws" data-pid="proj1"', html)
        self.assertIn('js/workspace.js', html)
        self.assertNotIn('id="mainTabs"', html)           # the legacy editor is gone
        self.assertIn('data-ax-route="projects" class="is-active"', html)
        self.assertIn('id="ax-ws" data-pid=""', self.client.get('/projects/new').data.decode())

    def test_admin_sees_users_and_user_does_not(self):
        self.assertIn('href="/admin/users"', self.client.get('/').data.decode())
        self.assertEqual(self.client.get('/admin/users').status_code, 200)
        self._auth('viewer')
        html = self.client.get('/').data.decode()
        self.assertIn('id="nav_admin_link" class="d-none"', html)
        self.assertEqual(self.client.get('/admin/users').status_code, 302)

    def test_account_menu_shows_signed_in_user(self):
        html = self.client.get('/').data.decode()
        self.assertIn('<b id="nav_username">Administrator</b>', html)
        self.assertIn('<span class="ax-avatar">A</span>', html)

    def test_bookings_and_funnel_hidden_by_default(self):
        # DESIGN.md 2.4: hidden from the UI; tables and API unchanged
        from pnl import config
        self.assertFalse(config.FEATURE_BOOKINGS_FUNNEL)
        self.assertEqual(self.client.get('/bookings').status_code, 404)
        self.assertEqual(self.client.get('/funnel').status_code, 404)
        html = self.client.get('/').data.decode()
        for hidden in ('data-ax-route="bookings"', 'id="tab-bookings"', 'id="tab-funnel"', 'bookingsColumnModal'):
            self.assertNotIn(hidden, html)
        # the data API still answers, so nothing is lost
        self.assertEqual(self.client.get('/api/bookings').status_code, 200)
        self.assertEqual(self.client.get('/api/funnel').status_code, 200)

    def test_pages_require_sign_in(self):
        self.client = self.app.test_client()
        for path in ('/', '/dashboard', '/rates', '/projects/proj1', '/design/components'):
            self.assertEqual(self.client.get(path).status_code, 302, path)

    def test_component_gallery(self):
        html = self.client.get('/design/components').data.decode()
        self.assertIn('ax-pill--on-hold', html)
        self.assertIn('ax-health--warn', html)
        self.assertIn('aria-invalid="true"', html)

    def test_legacy_screen_ids_still_present(self):
        # app.js depends on these; they must survive the shell move
        html = self.client.get('/').data.decode()
        for el in ('nav_username', 'nav_role_label', 'nav_admin_link', 'current_project_badge',
                   'active_project_pill', 'usersModal', 'changePasswordModal', 'exportModal', 'export_filename'):
            self.assertIn(f'id="{el}"', html, el)


class TestLoginPage(BaseTestCase):
    def test_login_page_copy(self):
        html = self.client.get('/login').data.decode()
        self.assertIn('Sign in', html)
        self.assertIn('Forgot your password? Ask an admin to reset it from Users.', html)
        self.assertNotIn('bootstrap', html)


class TestExportDialog(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._auth()

    def _payload(self, **extra):
        from test_pnl_suite import SAMPLE_PROJECT
        return {**SAMPLE_PROJECT, **extra}

    def test_export_screen_replaced_by_dialog(self):
        html = self.client.get('/').data.decode()
        self.assertNotIn('id="tab-export"', html)
        self.assertNotIn('Export settings', html)

    def test_download_name_from_dialog(self):
        r = self.client.post('/api/export', json=self._payload(download_name='ACME PnL v3'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('ACME PnL v3.xlsx', r.headers['Content-Disposition'])

    def test_download_name_is_sanitised(self):
        r = self.client.post('/api/export', json=self._payload(download_name='../../etc/pass:wd*'))
        cd = r.headers['Content-Disposition']
        self.assertNotIn('/', cd.split('filename', 1)[1])
        self.assertIn('filename="etc pass wd.xlsx"', cd)

    def test_without_name_keeps_old_timestamped_name(self):
        r = self.client.post('/api/export', json=self._payload())
        self.assertRegex(r.headers['Content-Disposition'], r'ACME_Corp_PnL_\d{8}_\d{6}\.xlsx')

    def test_server_error_has_reference_not_traceback(self):
        from unittest.mock import patch
        with patch('pnl.routes.export.build_workbook', side_effect=RuntimeError('boom secret detail')):
            r = self.client.post('/api/export', json=self._payload())
        self.assertEqual(r.status_code, 500)
        body = r.get_json()
        self.assertIn('reference', body)
        self.assertNotIn('boom', body['error'])
        self.assertNotIn('detail', body)


class TestHiddenRule(BaseTestCase):
    def test_hidden_attribute_always_hides(self):
        # The sign-in page has two forms toggled with `hidden`; without this rule both showed.
        css = (ROOT / 'static' / 'css' / 'ax.css').read_text()
        self.assertIn('[hidden] { display: none !important; }', css)
