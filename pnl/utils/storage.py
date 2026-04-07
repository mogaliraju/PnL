import json
import os
import re
import sqlite3
from datetime import datetime

from werkzeug.security import generate_password_hash

from pnl.config import DATA_FILE, DB_FILE, PROJECTS_DIR, SETTINGS_FILE, USERS_FILE, VERSIONS_DIR
from pnl.utils.logger import get_logger

log = get_logger(__name__)

_DB_READY = False


def safe_filename(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name.strip())


def _read_json_file(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _json_dumps(value) -> str:
    return json.dumps(value, indent=2)


def _json_loads(value: str | None, default):
    if not value:
        return default
    return json.loads(value)


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _set_state(conn: sqlite3.Connection, key: str, payload) -> None:
    conn.execute(
        """
        INSERT INTO app_state(key, json_value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            json_value=excluded.json_value,
            updated_at=excluded.updated_at
        """,
        (key, _json_dumps(payload), datetime.now().isoformat(timespec='seconds')),
    )


def _get_state(conn: sqlite3.Connection, key: str, default):
    row = conn.execute("SELECT json_value FROM app_state WHERE key = ?", (key,)).fetchone()
    return _json_loads(row['json_value'], default) if row else default


def _merge_global_settings(data: dict, settings: dict) -> dict:
    merged = dict(data)
    if settings.get('rate_card'):
        merged['rate_card'] = settings['rate_card']
    if settings.get('role_catalog'):
        merged['role_catalog'] = settings['role_catalog']
    return merged


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            json_value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projects (
            pid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            customer TEXT,
            location TEXT,
            duration TEXT,
            proposal_date TEXT,
            saved_at TEXT,
            saved_by TEXT,
            payload TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS project_versions (
            pid TEXT NOT NULL,
            vid TEXT NOT NULL,
            saved_at TEXT,
            saved_by TEXT,
            payload TEXT NOT NULL,
            PRIMARY KEY (pid, vid)
        );
        """
    )
    conn.commit()


def _migrate_json_files(conn: sqlite3.Connection) -> None:
    has_state = conn.execute("SELECT COUNT(*) AS c FROM app_state").fetchone()['c'] > 0
    has_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()['c'] > 0
    has_projects = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()['c'] > 0
    has_versions = conn.execute("SELECT COUNT(*) AS c FROM project_versions").fetchone()['c'] > 0

    if not has_state:
        settings = _read_json_file(SETTINGS_FILE, {})
        working_data = _read_json_file(DATA_FILE, {})
        if settings:
            _set_state(conn, 'global_settings', settings)
        else:
            _set_state(conn, 'global_settings', {})
        if working_data:
            _set_state(conn, 'working_data', working_data)
        else:
            _set_state(conn, 'working_data', {})

    if not has_users:
        users = _read_json_file(USERS_FILE, {})
        for username, user in users.items():
            conn.execute(
                """
                INSERT OR REPLACE INTO users(username, password, role, name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    username,
                    user.get('password', ''),
                    user.get('role', 'user'),
                    user.get('name', username),
                    user.get('created_at', ''),
                ),
            )

    if not has_projects and os.path.exists(PROJECTS_DIR):
        for fname in sorted(os.listdir(PROJECTS_DIR)):
            if not fname.endswith('.json'):
                continue
            payload = _read_json_file(os.path.join(PROJECTS_DIR, fname), {})
            meta = payload.get('_meta', {})
            project = payload.get('project', {})
            pid = meta.get('id') or fname[:-5]
            conn.execute(
                """
                INSERT OR REPLACE INTO projects(
                    pid, name, customer, location, duration, proposal_date, saved_at, saved_by, payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pid,
                    meta.get('name', pid),
                    project.get('customer', ''),
                    project.get('location', ''),
                    str(project.get('duration_months', '')),
                    project.get('proposal_date', ''),
                    meta.get('saved_at', ''),
                    meta.get('saved_by', ''),
                    _json_dumps(payload),
                ),
            )

    if not has_versions and os.path.exists(VERSIONS_DIR):
        for pid in os.listdir(VERSIONS_DIR):
            vdir = os.path.join(VERSIONS_DIR, pid)
            if not os.path.isdir(vdir):
                continue
            for fname in sorted(os.listdir(vdir)):
                if not fname.endswith('.json'):
                    continue
                payload = _read_json_file(os.path.join(vdir, fname), {})
                meta = payload.get('_meta', {})
                vid = fname[:-5]
                conn.execute(
                    """
                    INSERT OR REPLACE INTO project_versions(pid, vid, saved_at, saved_by, payload)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        vid,
                        meta.get('saved_at', ''),
                        meta.get('saved_by', ''),
                        _json_dumps(payload),
                    ),
                )

    conn.commit()


def _ensure_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        _create_schema(conn)
        _migrate_json_files(conn)
    _DB_READY = True


def load_global_settings() -> dict:
    _ensure_db()
    with _connect() as conn:
        return _get_state(conn, 'global_settings', {})


def save_global_settings(settings: dict):
    _ensure_db()
    with _connect() as conn:
        _set_state(conn, 'global_settings', settings)
        conn.commit()
    log.info("Settings saved")


def load_working_data() -> dict:
    _ensure_db()
    with _connect() as conn:
        data = _get_state(conn, 'working_data', {})
        settings = _get_state(conn, 'global_settings', {})
    return _merge_global_settings(data, settings)


def save_working_data(data: dict):
    _ensure_db()
    with _connect() as conn:
        _set_state(conn, 'working_data', data)
        settings = _get_state(conn, 'global_settings', {})
        if data.get('rate_card'):
            settings['rate_card'] = data['rate_card']
        if data.get('role_catalog'):
            settings['role_catalog'] = data['role_catalog']
        _set_state(conn, 'global_settings', settings)
        conn.commit()
    log.info("Working data saved")


def merge_settings(data: dict) -> dict:
    """Inject current global rate card + catalog into a project dict."""
    return _merge_global_settings(data, load_global_settings())


def load_users() -> dict:
    _ensure_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT username, password, role, name, created_at FROM users ORDER BY username"
        ).fetchall()
        if rows:
            return {
                row['username']: {
                    'password': row['password'],
                    'role': row['role'],
                    'name': row['name'],
                    'created_at': row['created_at'],
                }
                for row in rows
            }

        bootstrap_password = os.environ.get('PNL_BOOTSTRAP_ADMIN_PASSWORD', '').strip()
        bootstrap_username = os.environ.get('PNL_BOOTSTRAP_ADMIN_USERNAME', 'admin').strip() or 'admin'
        bootstrap_name = os.environ.get('PNL_BOOTSTRAP_ADMIN_NAME', 'Administrator').strip() or 'Administrator'

        if bootstrap_password:
            admin = {
                bootstrap_username.lower(): {
                    'password': generate_password_hash(bootstrap_password),
                    'role': 'admin',
                    'name': bootstrap_name,
                    'created_at': datetime.now().isoformat(timespec='seconds')
                }
            }
            save_users(admin)
            log.warning("Bootstrapped admin user from environment because no users existed in SQLite")
            return admin

    log.warning("No users exist and no bootstrap admin password was provided")
    return {}


def save_users(users: dict):
    _ensure_db()
    with _connect() as conn:
        conn.execute("DELETE FROM users")
        for username, user in users.items():
            conn.execute(
                """
                INSERT INTO users(username, password, role, name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    username,
                    user.get('password', ''),
                    user.get('role', 'user'),
                    user.get('name', username),
                    user.get('created_at', ''),
                ),
            )
        conn.commit()


def list_projects(summary: bool = False) -> list[dict]:
    _ensure_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT pid, name, customer, location, duration, proposal_date, saved_at, saved_by, payload
            FROM projects
            ORDER BY saved_at DESC, pid DESC
            """
        ).fetchall()

    projects = []
    for row in rows:
        entry = {
            'id': row['pid'],
            'name': row['name'],
            'customer': row['customer'] or '',
            'location': row['location'] or '',
            'duration': row['duration'] or '',
            'proposal_date': row['proposal_date'] or '',
            'saved_at': row['saved_at'] or '',
            'saved_by': row['saved_by'] or '',
        }
        if summary:
            payload = _json_loads(row['payload'], {})
            target_margin = float(payload.get('target_margin', 0.40))
            from pnl.services.pnl_service import compute_costs

            entry['costs'] = compute_costs(
                payload.get('resources', []),
                payload.get('rate_card', []),
                target_margin,
            )
        projects.append(entry)
    return projects


def save_project_record(pid: str, data: dict) -> None:
    _ensure_db()
    meta = data.get('_meta', {})
    project = data.get('project', {})
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO projects(pid, name, customer, location, duration, proposal_date, saved_at, saved_by, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pid) DO UPDATE SET
                name=excluded.name,
                customer=excluded.customer,
                location=excluded.location,
                duration=excluded.duration,
                proposal_date=excluded.proposal_date,
                saved_at=excluded.saved_at,
                saved_by=excluded.saved_by,
                payload=excluded.payload
            """,
            (
                pid,
                meta.get('name', pid),
                project.get('customer', ''),
                project.get('location', ''),
                str(project.get('duration_months', '')),
                project.get('proposal_date', ''),
                meta.get('saved_at', ''),
                meta.get('saved_by', ''),
                _json_dumps(data),
            ),
        )
        conn.commit()


def load_project_record(pid: str) -> dict | None:
    _ensure_db()
    with _connect() as conn:
        row = conn.execute("SELECT payload FROM projects WHERE pid = ?", (pid,)).fetchone()
    if not row:
        return None
    return _json_loads(row['payload'], {})


def delete_project_record(pid: str) -> None:
    _ensure_db()
    with _connect() as conn:
        conn.execute("DELETE FROM projects WHERE pid = ?", (pid,))
        conn.execute("DELETE FROM project_versions WHERE pid = ?", (pid,))
        conn.commit()


def rename_project_record(pid: str, new_name: str, new_customer: str = '') -> bool:
    data = load_project_record(pid)
    if data is None:
        return False
    data.setdefault('_meta', {})['name'] = new_name
    if new_customer:
        data.setdefault('project', {})['customer'] = new_customer
    save_project_record(pid, data)
    return True


def save_project_version(pid: str, vid: str, data: dict) -> None:
    _ensure_db()
    meta = data.get('_meta', {})
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO project_versions(pid, vid, saved_at, saved_by, payload)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(pid, vid) DO UPDATE SET
                saved_at=excluded.saved_at,
                saved_by=excluded.saved_by,
                payload=excluded.payload
            """,
            (
                pid,
                vid,
                meta.get('saved_at', ''),
                meta.get('saved_by', ''),
                _json_dumps(data),
            ),
        )
        conn.commit()


def list_project_versions(pid: str) -> list[dict]:
    _ensure_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT vid, saved_at, saved_by
            FROM project_versions
            WHERE pid = ?
            ORDER BY vid
            """,
            (pid,),
        ).fetchall()
    return [
        {
            'vid': row['vid'],
            'saved_at': row['saved_at'] or '',
            'saved_by': row['saved_by'] or '',
        }
        for row in rows
    ]


def load_project_version(pid: str, vid: str) -> dict | None:
    _ensure_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT payload FROM project_versions WHERE pid = ? AND vid = ?",
            (pid, vid),
        ).fetchone()
    if not row:
        return None
    return _json_loads(row['payload'], {})


# Backwards-compatible names for existing imports while the codebase is refactored.
load_settings = load_global_settings
save_settings = save_global_settings
load_data = load_working_data
save_data = save_working_data
