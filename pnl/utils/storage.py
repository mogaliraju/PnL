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


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
    if settings.get('business_units'):
        merged['business_units'] = settings['business_units']
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

        CREATE TABLE IF NOT EXISTS funnel_entries (
            id TEXT PRIMARY KEY,
            record_id TEXT,
            reporting_manager TEXT,
            opportunity_owner TEXT,
            region TEXT,
            account_name TEXT,
            description TEXT,
            opportunity_name TEXT,
            closing_month TEXT,
            ageing_days TEXT,
            stage TEXT,
            fq TEXT,
            final_product TEXT,
            created_time TEXT,
            net_forecasting TEXT,
            otc_usd_k REAL,
            tcv_usd REAL,
            mrc_usd_k REAL,
            acv_usd_k REAL,
            updates TEXT,
            extra_fields TEXT,
            saved_at TEXT,
            saved_by TEXT
        );

        CREATE TABLE IF NOT EXISTS order_bookings (
            id TEXT PRIMARY KEY,
            booking_type TEXT NOT NULL,
            opf_number TEXT,
            opf_date TEXT,
            cdd TEXT,
            bu TEXT,
            customer_name TEXT,
            otc REAL,
            mrc REAL,
            billed_pct REAL,
            milestones TEXT,
            c4c_invoice_raised REAL,
            c4c_amount_received REAL,
            c4c_pending_billing REAL,
            ax_invoice_raised REAL,
            ax_amount_received REAL,
            ax_pending_collection REAL,
            updates TEXT,
            billing_team_comments TEXT,
            pmo TEXT,
            extra_fields TEXT,
            saved_at TEXT,
            saved_by TEXT
        );
        """
    )
    # Add new columns to existing databases that predate this schema
    existing = {row['name'] for row in conn.execute("PRAGMA table_info(order_bookings)").fetchall()}
    for col, col_type in [('billing_team_comments', 'TEXT'), ('pmo', 'TEXT')]:
        if col not in existing:
            conn.execute(f"ALTER TABLE order_bookings ADD COLUMN {col} {col_type}")
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
        if data.get('business_units'):
            settings['business_units'] = data['business_units']
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
            project = payload.get('project', {})
            resources = payload.get('resources', [])
            target_margin = float(payload.get('target_margin', 0.40))
            from pnl.services.pnl_service import compute_costs

            costs = compute_costs(
                resources,
                payload.get('rate_card', []),
                target_margin,
            )
            total_hours = sum(_to_float(r.get('hours')) for r in resources)
            input_cost = _to_float(costs.get('input_cost'))
            discount_pct = _to_float(project.get('discount_pct'))
            add_on_cost = (
                _to_float(project.get('travel_cost'))
                + _to_float(project.get('infra_cost'))
                + _to_float(project.get('third_party_cost'))
            )

            entry.update({
                'company': project.get('company', ''),
                'reference': project.get('reference', ''),
                'customer_first_touch_point': project.get('customer_first_touch_point', ''),
                'project_description': project.get('project_description', ''),
                'partner': project.get('partner', ''),
                'payment_terms': project.get('payment_terms', ''),
                'status': project.get('status', ''),
                'stage': project.get('stage', ''),
                'priority': project.get('priority', ''),
                'project_owner': project.get('project_owner', ''),
                'account_manager': project.get('account_manager', ''),
                'sales_spoc': project.get('sales_spoc', ''),
                'delivery_manager': project.get('delivery_manager', ''),
                'technical_lead': project.get('technical_lead', ''),
                'expected_start_date': project.get('expected_start_date', ''),
                'expected_end_date': project.get('expected_end_date', ''),
                'opportunity_id': project.get('opportunity_id', ''),
                'project_type': project.get('project_type', ''),
                'industry': project.get('industry', ''),
                'delivery_model': project.get('delivery_model', ''),
                'billing_type': project.get('billing_type', ''),
                'currency': project.get('currency', 'USD') or 'USD',
                'business_unit': project.get('business_unit', ''),
                'next_action': project.get('next_action', ''),
                'next_follow_up_date': project.get('next_follow_up_date', ''),
                'discount_pct': discount_pct,
                'travel_cost': _to_float(project.get('travel_cost')),
                'infra_cost': _to_float(project.get('infra_cost')),
                'third_party_cost': _to_float(project.get('third_party_cost')),
                'add_on_cost': add_on_cost,
                'resource_count': len(resources),
                'total_hours': total_hours,
                'avg_rate': (input_cost / total_hours) if total_hours else 0.0,
                'fx_rate': _to_float(payload.get('fx_rate')),
                'costs': costs,
                'profit_amount': _to_float(costs.get('markup')),
            })
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


def load_all_project_records() -> list[dict]:
    _ensure_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT payload
            FROM projects
            ORDER BY saved_at DESC, pid DESC
            """
        ).fetchall()
    return [_json_loads(row['payload'], {}) for row in rows]


# Backwards-compatible names for existing imports while the codebase is refactored.
load_settings = load_global_settings
save_settings = save_global_settings
load_data = load_working_data
save_data = save_working_data


# ── Funnel Entries ────────────────────────────────────────────

def list_funnel_entries() -> list[dict]:
    _ensure_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM funnel_entries ORDER BY saved_at DESC, id DESC"
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['extra_fields'] = _json_loads(d.get('extra_fields'), {})
        result.append(d)
    return result


def save_funnel_entry(entry_id: str, data: dict) -> None:
    _ensure_db()
    extra = data.get('extra_fields') or {}
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO funnel_entries(
                id, record_id, reporting_manager, opportunity_owner, region,
                account_name, description, opportunity_name, closing_month,
                ageing_days, stage, fq, final_product, created_time,
                net_forecasting, otc_usd_k, tcv_usd, mrc_usd_k, acv_usd_k,
                updates, extra_fields, saved_at, saved_by
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                record_id=excluded.record_id,
                reporting_manager=excluded.reporting_manager,
                opportunity_owner=excluded.opportunity_owner,
                region=excluded.region,
                account_name=excluded.account_name,
                description=excluded.description,
                opportunity_name=excluded.opportunity_name,
                closing_month=excluded.closing_month,
                ageing_days=excluded.ageing_days,
                stage=excluded.stage,
                fq=excluded.fq,
                final_product=excluded.final_product,
                created_time=excluded.created_time,
                net_forecasting=excluded.net_forecasting,
                otc_usd_k=excluded.otc_usd_k,
                tcv_usd=excluded.tcv_usd,
                mrc_usd_k=excluded.mrc_usd_k,
                acv_usd_k=excluded.acv_usd_k,
                updates=excluded.updates,
                extra_fields=excluded.extra_fields,
                saved_at=excluded.saved_at,
                saved_by=excluded.saved_by
            """,
            (
                entry_id,
                data.get('record_id', ''),
                data.get('reporting_manager', ''),
                data.get('opportunity_owner', ''),
                data.get('region', ''),
                data.get('account_name', ''),
                data.get('description', ''),
                data.get('opportunity_name', ''),
                data.get('closing_month', ''),
                data.get('ageing_days', ''),
                data.get('stage', ''),
                data.get('fq', ''),
                data.get('final_product', ''),
                data.get('created_time', ''),
                data.get('net_forecasting', ''),
                _to_float(data.get('otc_usd_k'), None),
                _to_float(data.get('tcv_usd'), None),
                _to_float(data.get('mrc_usd_k'), None),
                _to_float(data.get('acv_usd_k'), None),
                data.get('updates', ''),
                _json_dumps(extra),
                data.get('saved_at', ''),
                data.get('saved_by', ''),
            ),
        )
        conn.commit()


def load_funnel_entry(entry_id: str) -> dict | None:
    _ensure_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM funnel_entries WHERE id = ?", (entry_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d['extra_fields'] = _json_loads(d.get('extra_fields'), {})
    return d


def delete_funnel_entry(entry_id: str) -> None:
    _ensure_db()
    with _connect() as conn:
        conn.execute("DELETE FROM funnel_entries WHERE id = ?", (entry_id,))
        conn.commit()


# ── Order Bookings ────────────────────────────────────────────

def list_order_bookings(booking_type: str | None = None) -> list[dict]:
    _ensure_db()
    with _connect() as conn:
        if booking_type:
            rows = conn.execute(
                "SELECT * FROM order_bookings WHERE booking_type = ? ORDER BY saved_at DESC, id DESC",
                (booking_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM order_bookings ORDER BY saved_at DESC, id DESC"
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['extra_fields'] = _json_loads(d.get('extra_fields'), {})
        result.append(d)
    return result


def save_order_booking(booking_id: str, data: dict) -> None:
    _ensure_db()
    extra = data.get('extra_fields') or {}
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO order_bookings(
                id, booking_type, opf_number, opf_date, cdd, bu, customer_name,
                otc, mrc, billed_pct, milestones,
                c4c_invoice_raised, c4c_amount_received, c4c_pending_billing,
                ax_invoice_raised, ax_amount_received, ax_pending_collection,
                updates, billing_team_comments, pmo,
                extra_fields, saved_at, saved_by
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                booking_type=excluded.booking_type,
                opf_number=excluded.opf_number,
                opf_date=excluded.opf_date,
                cdd=excluded.cdd,
                bu=excluded.bu,
                customer_name=excluded.customer_name,
                otc=excluded.otc,
                mrc=excluded.mrc,
                billed_pct=excluded.billed_pct,
                milestones=excluded.milestones,
                c4c_invoice_raised=excluded.c4c_invoice_raised,
                c4c_amount_received=excluded.c4c_amount_received,
                c4c_pending_billing=excluded.c4c_pending_billing,
                ax_invoice_raised=excluded.ax_invoice_raised,
                ax_amount_received=excluded.ax_amount_received,
                ax_pending_collection=excluded.ax_pending_collection,
                updates=excluded.updates,
                billing_team_comments=excluded.billing_team_comments,
                pmo=excluded.pmo,
                extra_fields=excluded.extra_fields,
                saved_at=excluded.saved_at,
                saved_by=excluded.saved_by
            """,
            (
                booking_id,
                data.get('booking_type', 'OTC'),
                data.get('opf_number', ''),
                data.get('opf_date', ''),
                data.get('cdd', ''),
                data.get('bu', ''),
                data.get('customer_name', ''),
                _to_float(data.get('otc'), None),
                _to_float(data.get('mrc'), None),
                _to_float(data.get('billed_pct'), None),
                data.get('milestones', ''),
                _to_float(data.get('c4c_invoice_raised'), None),
                _to_float(data.get('c4c_amount_received'), None),
                _to_float(data.get('c4c_pending_billing'), None),
                _to_float(data.get('ax_invoice_raised'), None),
                _to_float(data.get('ax_amount_received'), None),
                _to_float(data.get('ax_pending_collection'), None),
                data.get('updates', ''),
                data.get('billing_team_comments', ''),
                data.get('pmo', ''),
                _json_dumps(extra),
                data.get('saved_at', ''),
                data.get('saved_by', ''),
            ),
        )
        conn.commit()


def load_order_booking(booking_id: str) -> dict | None:
    _ensure_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM order_bookings WHERE id = ?", (booking_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d['extra_fields'] = _json_loads(d.get('extra_fields'), {})
    return d


def delete_order_booking(booking_id: str) -> None:
    _ensure_db()
    with _connect() as conn:
        conn.execute("DELETE FROM order_bookings WHERE id = ?", (booking_id,))
        conn.commit()


# ── Custom Field Schemas ──────────────────────────────────────
# Each module ('funnel' | 'bookings') stores a list of custom field defs:
#   [{'key': 'cf_xyz', 'label': 'My Column', 'type': 'text|number|date'}, ...]

def load_custom_fields(module: str) -> list:
    _ensure_db()
    with _connect() as conn:
        return _get_state(conn, f'custom_fields_{module}', [])


def save_custom_fields(module: str, fields: list) -> None:
    _ensure_db()
    with _connect() as conn:
        _set_state(conn, f'custom_fields_{module}', fields)
        conn.commit()


def load_column_labels(module: str) -> dict:
    """Returns overridden display labels for built-in columns: {field_key: label}."""
    _ensure_db()
    with _connect() as conn:
        return _get_state(conn, f'column_labels_{module}', {})


def save_column_labels(module: str, labels: dict) -> None:
    _ensure_db()
    with _connect() as conn:
        _set_state(conn, f'column_labels_{module}', labels)
        conn.commit()
