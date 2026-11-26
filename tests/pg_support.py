"""Postgres test support. Set PNL_TEST_PG_URL to a database prepared with
scripts/setup_test_db.py. Each test runs in one transaction that is rolled back."""
import os
import sys
import unittest
from unittest.mock import patch

from test_pnl_suite import make_data_dir, reload_app

PG_URL = os.environ.get('PNL_TEST_PG_URL', '')
needs_pg = unittest.skipUnless(PG_URL, 'set PNL_TEST_PG_URL (see scripts/setup_test_db.py) to run Postgres tests')


class _SharedConn:
    """Stands in for storage._connect(): every block is a savepoint inside the test transaction."""

    def __init__(self, conn):
        self.conn, self.depth = conn, 0

    def __call__(self):
        return self

    def __enter__(self):
        self.depth += 1
        self.conn.execute(f"SAVEPOINT sp{self.depth}")
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.conn.execute(f"ROLLBACK TO SAVEPOINT sp{self.depth}")
        self.conn.execute(f"RELEASE SAVEPOINT sp{self.depth}")
        self.depth -= 1
        return False

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        pass

    def rollback(self):
        self.conn.execute(f"ROLLBACK TO SAVEPOINT sp{self.depth}")


@needs_pg
class PgAppTestCase(unittest.TestCase):
    def setUp(self):
        import psycopg
        from psycopg.rows import dict_row
        self.data_dir = make_data_dir()
        os.environ.update(DATA_DIR=str(self.data_dir), SECRET_KEY='test-secret-key', PNL_ENV='development',
                          DATABASE_URL=PG_URL)
        self.conn = psycopg.connect(PG_URL, row_factory=dict_row)
        self.app = reload_app()
        self.app.testing = True
        self.client = self.app.test_client()
        self.storage = sys.modules['pnl.utils.storage']
        self._patch = patch.object(self.storage, '_connect', _SharedConn(self.conn))
        self._patch.start()
        self.storage._FEATURES = None
        self.storage._DB_READY = False
        self.storage._ensure_db()
        self.seed()

    def tearDown(self):
        self._patch.stop()
        self.conn.rollback()
        self.conn.close()
        os.environ.pop('DATABASE_URL', None)
        import shutil
        shutil.rmtree(self.data_dir, ignore_errors=True)
        reload_app()          # back to SQLite for the next test module

    def q(self, sql, params=()):
        return self.conn.execute(sql, params)

    def seed(self):
        """Two levels, two categories, roles, rate card v1 published, users."""
        q = self.q
        q("INSERT INTO users(username, password, role, name, created_at) VALUES ('admin','x','admin','Administrator',''),('viewer','x','user','Viewer','')")
        self.lv = {c: q("INSERT INTO level(code, name, sort_order) VALUES (%s,%s,%s) RETURNING id", (c, c, i)).fetchone()['id']
                   for i, c in enumerate(['L1', 'L2'])}
        self.cat = {n: q("INSERT INTO role_category(name, sort_order) VALUES (%s,%s) RETURNING id", (n, i)).fetchone()['id']
                    for i, n in enumerate(['Data', 'BI'])}
        q("INSERT INTO role(category_id, name, default_level_id) VALUES (%s,'Data engineer',%s),(%s,'BI developer',%s)",
          (self.cat['Data'], self.lv['L2'], self.cat['BI'], self.lv['L1']))
        self.v1 = q("INSERT INTO rate_card(version, status, effective_from) VALUES (1,'published',CURRENT_DATE) RETURNING id").fetchone()['id']
        for (c, l), r in {('Data', 'L1'): 20, ('Data', 'L2'): 30, ('BI', 'L1'): 18, ('BI', 'L2'): None}.items():
            q("INSERT INTO rate_card_rate VALUES (%s,%s,%s,%s)", (self.v1, self.cat[c], self.lv[l], r))

    def auth(self, role='admin'):
        with self.client.session_transaction() as s:
            s['user'] = role
            s['role'] = role
            s['name'] = role.title()
