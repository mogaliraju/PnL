"""Versioned rate cards and the role catalog (DESIGN.md 5.5, 8). Postgres only.

Rules enforced here, not just in the UI:
  * only one draft and one published card exist (also unique indexes);
  * published and archived cards are read only (RateCardError -> HTTP 409);
  * roles and categories are switched off, never deleted; renaming keeps the id;
  * publishing archives the previous card and publishes the draft in one transaction.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from pnl.utils import storage


class RateCardError(RuntimeError):
    """A request the rate-card rules don't allow. `status` is the HTTP status to return."""

    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


def available() -> bool:
    return storage._features().get('rate_cards', False)


def _require():
    if not available():
        raise RateCardError('Rate cards need database migrations 0002 and 0003. Run scripts/migrate.py.', 503)


def _num(v):
    return None if v is None else float(v) if isinstance(v, Decimal) else v


def _card_row(conn, version: int):
    row = conn.execute("SELECT * FROM rate_card WHERE version = %s", (version,)).fetchone()
    if not row:
        raise RateCardError(f'Rate card v{version} does not exist.', 404)
    return row


def _published(conn):
    return conn.execute("SELECT * FROM rate_card WHERE status = 'published'").fetchone()


def _card_json(r, projects_using: int | None = None) -> dict:
    out = {
        'id': r['id'], 'version': r['version'], 'status': r['status'],
        'effective_from': r['effective_from'].isoformat() if r['effective_from'] else None,
        'note': r['note'] or '', 'created_by': r['created_by'] or '',
        'created_at': r['created_at'].isoformat() if r['created_at'] else None,
        'published_by': r['published_by'] or '',
        'published_at': r['published_at'].isoformat() if r['published_at'] else None,
    }
    if projects_using is not None:
        out['projects_using'] = projects_using
    return out


# ── rate cards ─────────────────────────────────────────────────────────────

def list_cards() -> list[dict]:
    _require()
    with storage._connect() as conn:
        using = {r['rate_card_id']: r['n'] for r in conn.execute(
            "SELECT rate_card_id, COUNT(*) AS n FROM projects WHERE archived_at IS NULL GROUP BY rate_card_id").fetchall()}
        rows = conn.execute("SELECT * FROM rate_card ORDER BY version DESC").fetchall()
    return [_card_json(r, using.get(r['id'], 0)) for r in rows]


def levels(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT id, code, name, sort_order FROM level ORDER BY sort_order, id").fetchall()]


def categories(conn, include_inactive: bool = True) -> list[dict]:
    rows = conn.execute("""
        SELECT c.id, c.name, c.active, c.sort_order,
               COUNT(r.id) FILTER (WHERE r.active) AS active_roles, COUNT(r.id) AS all_roles
        FROM role_category c LEFT JOIN role r ON r.category_id = c.id
        GROUP BY c.id ORDER BY c.sort_order, c.id""").fetchall()
    return [dict(r) for r in rows if include_inactive or r['active']]


def get_matrix(version: int | None = None) -> dict:
    _require()
    with storage._connect() as conn:
        card = _card_row(conn, version) if version else _published(conn)
        if not card:
            raise RateCardError('No rate card has been published yet.', 404)
        rates = {}
        for r in conn.execute("SELECT category_id, level_id, rate_usd FROM rate_card_rate WHERE rate_card_id = %s",
                              (card['id'],)).fetchall():
            rates.setdefault(str(r['category_id']), {})[str(r['level_id'])] = _num(r['rate_usd'])
        pub = _published(conn)
        published_rates = None
        if card['status'] == 'draft' and pub:
            published_rates = {}
            for r in conn.execute("SELECT category_id, level_id, rate_usd FROM rate_card_rate WHERE rate_card_id = %s",
                                  (pub['id'],)).fetchall():
                published_rates.setdefault(str(r['category_id']), {})[str(r['level_id'])] = _num(r['rate_usd'])
        return {
            'card': _card_json(card),
            'published_version': pub['version'] if pub else None,
            'levels': levels(conn),
            'categories': categories(conn),
            'rates': rates,
            'published_rates': published_rates,
        }


def create_draft(username: str, note: str = '') -> dict:
    _require()
    with storage._connect() as conn:
        if conn.execute("SELECT 1 FROM rate_card WHERE status = 'draft'").fetchone():
            raise RateCardError('A draft already exists. Finish or publish it before starting another.')
        pub = _published(conn)
        version = (conn.execute("SELECT COALESCE(MAX(version), 0) AS v FROM rate_card").fetchone()['v'] or 0) + 1
        new_id = conn.execute(
            "INSERT INTO rate_card(version, status, note, created_by) VALUES (%s, 'draft', %s, %s) RETURNING id",
            (version, note or f'Draft based on v{pub["version"]}' if pub else note, username)).fetchone()['id']
        if pub:
            conn.execute("""INSERT INTO rate_card_rate(rate_card_id, category_id, level_id, rate_usd)
                            SELECT %s, category_id, level_id, rate_usd FROM rate_card_rate WHERE rate_card_id = %s""",
                         (new_id, pub['id']))
        conn.commit()
    return get_matrix(version)


def set_rates(version: int, cells: list[dict], note: str | None = None) -> dict:
    """Write rates into a DRAFT. cells: [{category_id, level_id, rate_usd (number or null)}]."""
    _require()
    if not isinstance(cells, list):
        raise RateCardError('Send a list of rates.', 400)
    with storage._connect() as conn:
        card = _card_row(conn, version)
        if card['status'] != 'draft':
            raise RateCardError(f'Rate card v{version} is {card["status"]} and read only. Create a draft to change rates.')
        cat_ids = {r['id'] for r in conn.execute("SELECT id FROM role_category").fetchall()}
        lvl_ids = {r['id'] for r in conn.execute("SELECT id FROM level").fetchall()}
        for c in cells:
            try:
                cid, lid = int(c['category_id']), int(c['level_id'])
            except (KeyError, TypeError, ValueError):
                raise RateCardError('Each rate needs a category_id and a level_id.', 400)
            if cid not in cat_ids or lid not in lvl_ids:
                raise RateCardError('Unknown category or level.', 400)
            rate = c.get('rate_usd')
            if rate in ('', None):
                rate = None
            else:
                try:
                    rate = Decimal(str(rate))
                except Exception:
                    raise RateCardError('Rates must be numbers.', 400)
                if rate < 0 or rate > 100000:
                    raise RateCardError('Rates must be between 0 and 100,000 USD an hour.', 400)
            conn.execute("""INSERT INTO rate_card_rate(rate_card_id, category_id, level_id, rate_usd)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (rate_card_id, category_id, level_id) DO UPDATE SET rate_usd = excluded.rate_usd""",
                         (card['id'], cid, lid, rate))
        if note is not None:
            conn.execute("UPDATE rate_card SET note = %s WHERE id = %s AND status = 'draft'", (note[:500], card['id']))
        conn.commit()
    return get_matrix(version)


def changed_cells(conn, draft_id: int, pub_id: int | None) -> int:
    if not pub_id:
        return conn.execute("SELECT COUNT(*) AS n FROM rate_card_rate WHERE rate_card_id = %s AND rate_usd IS NOT NULL",
                            (draft_id,)).fetchone()['n']
    return conn.execute("""
        SELECT COUNT(*) AS n FROM rate_card_rate d
        FULL OUTER JOIN (SELECT * FROM rate_card_rate WHERE rate_card_id = %s) p
          ON p.category_id = d.category_id AND p.level_id = d.level_id
        WHERE (d.rate_card_id = %s OR d.rate_card_id IS NULL)
          AND d.rate_usd IS DISTINCT FROM p.rate_usd""", (pub_id, draft_id)).fetchone()['n']


def publish(version: int, effective_from: str | None, username: str) -> dict:
    _require()
    try:
        eff = date.fromisoformat(effective_from) if effective_from else date.today()
    except ValueError:
        raise RateCardError('Effective date must be a date (YYYY-MM-DD).', 400)
    with storage._connect() as conn:
        card = _card_row(conn, version)
        if card['status'] != 'draft':
            raise RateCardError(f'Only a draft can be published. v{version} is {card["status"]}.')
        pub = _published(conn)
        changes = changed_cells(conn, card['id'], pub['id'] if pub else None)
        if pub:
            conn.execute("UPDATE rate_card SET status = 'archived' WHERE id = %s", (pub['id'],))
        conn.execute("""UPDATE rate_card SET status = 'published', effective_from = %s,
                        published_by = %s, published_at = now() WHERE id = %s""", (eff, username, card['id']))
        conn.commit()
    out = get_matrix(version)
    out['changes'] = changes
    return out


def card_as_payload(version: int | None = None) -> tuple[int | None, list[dict]]:
    """A card in the payload format the engine and the legacy editor use:
    [{level, rates: {category: rate}}]. Categories that don't offer a level are left out."""
    if not available():
        return None, []
    m = get_matrix(version)
    cats = {str(c['id']): c['name'] for c in m['categories']}
    out = []
    for lv in m['levels']:
        rates = {cats[cid]: r[str(lv['id'])] for cid, r in m['rates'].items()
                 if cid in cats and r.get(str(lv['id'])) is not None}
        if rates:
            out.append({'level': lv['code'], 'rates': rates})
    return m['card']['version'], out


def diff(from_version: int, to_version: int, project_id: str | None = None) -> dict:
    """Rates that differ between two cards; with project_id, the effect on that project's lines."""
    a, b = get_matrix(from_version), get_matrix(to_version)
    cats = {str(c['id']): c['name'] for c in a['categories']}
    lvls = {str(l['id']): l['code'] for l in a['levels']}
    cells = []
    for cid in sorted(set(a['rates']) | set(b['rates'])):
        for lid in sorted(set(a['rates'].get(cid, {})) | set(b['rates'].get(cid, {}))):
            x, y = a['rates'].get(cid, {}).get(lid), b['rates'].get(cid, {}).get(lid)
            if x != y:
                cells.append({'category': cats.get(cid), 'level': lvls.get(lid), 'from': x, 'to': y})
    out = {'from': from_version, 'to': to_version, 'cells': cells}
    if project_id:
        payload = storage.load_project_record(project_id)
        if payload is None:
            raise RateCardError('That project does not exist.', 404)
        from pnl import engine
        _, card_b = card_as_payload(to_version)
        lines = []
        for i, r in enumerate(payload.get('resources') or []):
            if not isinstance(r, dict):
                continue
            old = float(engine.rate_for(payload.get('rate_card') or [], r.get('level'), r.get('group', '')))
            new = float(engine.rate_for(card_b, r.get('level'), r.get('group', '')))
            hours = float(engine.D(r.get('hours')))
            if old != new:
                lines.append({'index': i, 'category': r.get('group'), 'role': r.get('role'), 'level': r.get('level'),
                              'hours': hours, 'from': old, 'to': new, 'cost_change': round((new - old) * hours, 2)})
        before = engine.calculate(payload)
        after = engine.calculate({**payload, 'rate_card': card_b})
        out['project'] = {'lines': lines, 'cost_basis_change': round(float(after.cost_basis - before.cost_basis), 2),
                          'contract_value_change': round(float(after.contract_value - before.contract_value), 2)}
    return out


# ── roles and categories ───────────────────────────────────────────────────

def list_roles() -> dict:
    _require()
    with storage._connect() as conn:
        cats = categories(conn)
        lv = levels(conn)
        usage = {}
        for row in conn.execute("SELECT payload FROM projects WHERE archived_at IS NULL").fetchall():
            p = json.loads(row['payload'])
            for key in {(r.get('group'), r.get('role')) for r in (p.get('resources') or []) if isinstance(r, dict)}:
                usage[key] = usage.get(key, 0) + 1
        names = {c['id']: c['name'] for c in cats}
        roles = [dict(r) for r in conn.execute("""
            SELECT id, category_id, name, default_level_id, active, imported FROM role ORDER BY category_id, lower(name)""").fetchall()]
    for r in roles:
        r['used_in'] = usage.get((names.get(r['category_id']), r['name']), 0)
    return {'categories': cats, 'levels': lv, 'roles': roles}


def add_category(name: str) -> dict:
    _require()
    name = (name or '').strip()
    if not name:
        raise RateCardError('Enter a category name.', 400)
    with storage._connect() as conn:
        if conn.execute("SELECT 1 FROM role_category WHERE lower(name) = lower(%s)", (name,)).fetchone():
            raise RateCardError(f'A category called "{name}" already exists.')
        order = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM role_category").fetchone()['n']
        row = conn.execute("INSERT INTO role_category(name, sort_order) VALUES (%s, %s) RETURNING id", (name, order)).fetchone()
        conn.commit()
    return {'id': row['id'], 'name': name}


def update_category(cid: int, name: str | None = None, active: bool | None = None) -> None:
    _require()
    with storage._connect() as conn:
        if not conn.execute("SELECT 1 FROM role_category WHERE id = %s", (cid,)).fetchone():
            raise RateCardError('That category does not exist.', 404)
        if name is not None:
            name = name.strip()
            if not name:
                raise RateCardError('Enter a category name.', 400)
            if conn.execute("SELECT 1 FROM role_category WHERE lower(name) = lower(%s) AND id <> %s", (name, cid)).fetchone():
                raise RateCardError(f'A category called "{name}" already exists.')
            conn.execute("UPDATE role_category SET name = %s WHERE id = %s", (name, cid))
        if active is not None:
            conn.execute("UPDATE role_category SET active = %s WHERE id = %s", (bool(active), cid))
        conn.commit()


def add_role(category_id: int, name: str, default_level_id: int | None = None) -> dict:
    _require()
    name = (name or '').strip()
    if not name:
        raise RateCardError('Enter a role name.', 400)
    with storage._connect() as conn:
        cat = conn.execute("SELECT name FROM role_category WHERE id = %s", (category_id,)).fetchone()
        if not cat:
            raise RateCardError('That category does not exist.', 404)
        if conn.execute("SELECT 1 FROM role WHERE category_id = %s AND lower(name) = lower(%s)", (category_id, name)).fetchone():
            raise RateCardError(f'{cat["name"]} already has a role called "{name}".')
        row = conn.execute("INSERT INTO role(category_id, name, default_level_id) VALUES (%s, %s, %s) RETURNING id",
                           (category_id, name, default_level_id)).fetchone()
        conn.commit()
    return {'id': row['id'], 'name': name}


def update_role(role_id: int, name: str | None = None, default_level_id=..., active: bool | None = None) -> None:
    """Rename keeps the id, so projects using it show the new name (DESIGN.md 8.3)."""
    _require()
    with storage._connect() as conn:
        role = conn.execute("SELECT * FROM role WHERE id = %s", (role_id,)).fetchone()
        if not role:
            raise RateCardError('That role does not exist.', 404)
        if name is not None:
            name = name.strip()
            if not name:
                raise RateCardError('Enter a role name.', 400)
            if conn.execute("SELECT 1 FROM role WHERE category_id = %s AND lower(name) = lower(%s) AND id <> %s",
                            (role['category_id'], name, role_id)).fetchone():
                raise RateCardError(f'That category already has a role called "{name}".')
            conn.execute("UPDATE role SET name = %s WHERE id = %s", (name, role_id))
        if default_level_id is not ...:
            conn.execute("UPDATE role SET default_level_id = %s WHERE id = %s", (default_level_id, role_id))
        if active is not None:
            conn.execute("UPDATE role SET active = %s WHERE id = %s", (bool(active), role_id))
        conn.commit()


def catalog_as_settings() -> list[dict]:
    """Active roles in the legacy settings shape [{group, roles: [...]}] for screens not yet rebuilt."""
    if not available():
        return []
    data = list_roles()
    out = []
    for c in data['categories']:
        if not c['active']:
            continue
        out.append({'group': c['name'], 'roles': [r['name'] for r in data['roles'] if r['category_id'] == c['id'] and r['active']]})
    return out
