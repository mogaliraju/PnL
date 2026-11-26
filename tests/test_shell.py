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

    def test_editor_shows_workspace_tabs(self):
        html = self.client.get('/projects/proj1').data.decode()
        self.assertIn('data-editor-pid="proj1"', html)
        self.assertNotIn('ax-legacy-tabs', html)
        self.assertIn('data-ax-route="projects" class="is-active"', html)

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

    def test_bookings_and_funnel_follow_feature_flag(self):
        from pnl import config
        config.FEATURE_BOOKINGS_FUNNEL = False
        try:
            self.assertEqual(self.client.get('/bookings').status_code, 404)
            self.assertEqual(self.client.get('/funnel').status_code, 404)
            self.assertNotIn('data-ax-route="bookings"', self.client.get('/').data.decode())
        finally:
            config.FEATURE_BOOKINGS_FUNNEL = True

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
                   'active_project_pill', 'usersModal', 'changePasswordModal', 'tab-export'):
            self.assertIn(f'id="{el}"', html, el)


class TestLoginPage(BaseTestCase):
    def test_login_page_copy(self):
        html = self.client.get('/login').data.decode()
        self.assertIn('Sign in', html)
        self.assertIn('Forgot your password? Ask an admin to reset it from Users.', html)
        self.assertNotIn('bootstrap', html)
