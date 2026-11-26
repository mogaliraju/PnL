"""Phase 5 seeding (DESIGN.md 8.2): copy, never move.

Reads the current rate card and role catalog from app_state.global_settings and every
saved payload, and fills the new tables. The old storage is left exactly as it is.
Only the new columns projects.rate_card_id and project_versions.version_no are backfilled.
"""
import json

BACKFILL = {'projects': {'rate_card_id'}, 'project_versions': {'version_no'}}


def _rate(entry, category):
    """What the app charges today for (level entry, category): same rule as pnl.engine.rate_for."""
    rates = entry.get('rates')
    if isinstance(rates, dict) and rates:
        if category in rates:
            return rates[category]
        return next(iter(rates.values()), None)
    return entry.get('rate')


def migrate(db, log):
    row = db.execute("SELECT json_value FROM app_state WHERE key = 'global_settings'").fetchone()
    settings = json.loads(row[0]) if row and row[0] else {}
    rate_card = [e for e in settings.get('rate_card') or [] if isinstance(e, dict) and e.get('level')]
    catalog = [g for g in settings.get('role_catalog') or [] if isinstance(g, dict) and g.get('group')]

    payloads = [json.loads(p) for (p,) in db.execute(
        "SELECT payload FROM projects UNION ALL SELECT payload FROM project_versions").fetchall()]
    lines = [r for p in payloads for r in (p.get('resources') or []) if isinstance(r, dict)]

    # 1. levels: current rate-card order, then any extra level found on saved lines
    levels = [e['level'] for e in rate_card]
    for r in lines:
        if r.get('level') and r['level'] not in levels:
            levels.append(r['level'])
    level_id = {}
    for i, code in enumerate(levels):
        level_id[code] = db.execute(
            "INSERT INTO level(code, name, sort_order) VALUES (%s, %s, %s) RETURNING id", (code, code, i)).fetchone()[0]
    log(f"    levels: {', '.join(levels)}")

    # 2. categories: catalog order, then rate-card categories, then categories only seen on lines (inactive)
    cats = [g['group'] for g in catalog]
    active_cats = set(cats)
    for e in rate_card:
        for c in (e.get('rates') or {}):
            if c not in cats:
                cats.append(c); active_cats.add(c)
    for r in lines:
        if r.get('group') and r['group'] not in cats:
            cats.append(r['group'])
    cat_id = {}
    for i, name in enumerate(cats):
        cat_id[name] = db.execute(
            "INSERT INTO role_category(name, sort_order, active) VALUES (%s, %s, %s) RETURNING id",
            (name, i, name in active_cats)).fetchone()[0]
    log(f"    categories: {len(cats)} ({len(cats) - len(active_cats)} only on old lines, inactive)")

    # 3. roles: catalog roles active; role names only found on saved lines inactive + imported
    first_level = {}
    for r in lines:
        first_level.setdefault((r.get('group'), r.get('role')), r.get('level'))
    seen = set()
    for g in catalog:
        for name in g.get('roles') or []:
            if (g['group'], name) in seen:
                continue
            seen.add((g['group'], name))
            lv = first_level.get((g['group'], name))
            db.execute("INSERT INTO role(category_id, name, default_level_id, active, imported) VALUES (%s, %s, %s, true, false)",
                       (cat_id[g['group']], name, level_id.get(lv)))
    imported = 0
    for (grp, name), lv in first_level.items():
        if grp and name and (grp, name) not in seen:
            seen.add((grp, name))
            db.execute("INSERT INTO role(category_id, name, default_level_id, active, imported) VALUES (%s, %s, %s, false, true)",
                       (cat_id[grp], name, level_id.get(lv)))
            imported += 1
    log(f"    roles: {len(seen)} ({imported} imported from old resource lines, switched off)")

    # 4. rate card v1, published, with today's effective rate for every category x level
    if not rate_card:
        log("    no rate card in use yet: nothing to copy, v1 not created")
        db.execute("UPDATE project_versions SET version_no = n.rn FROM (SELECT pid AS p, vid AS v, ROW_NUMBER() OVER "
                   "(PARTITION BY pid ORDER BY saved_at, vid) AS rn FROM project_versions) n "
                   "WHERE project_versions.pid = n.p AND project_versions.vid = n.v AND project_versions.version_no IS NULL")
        return
    rc_id = db.execute("""INSERT INTO rate_card(version, status, effective_from, note, created_by, published_by, published_at)
                          VALUES (1, 'published', CURRENT_DATE, 'Copied from the rate card in use before the redesign',
                                  'migration', 'migration', now()) RETURNING id""").fetchone()[0]
    cells = 0
    for e in rate_card:
        for name in cats:
            rate = _rate(e, name) if name in active_cats else None
            db.execute("INSERT INTO rate_card_rate(rate_card_id, category_id, level_id, rate_usd) VALUES (%s, %s, %s, %s)",
                       (rc_id, cat_id[name], level_id[e['level']], rate))
            cells += rate is not None
    log(f"    rate card v1: {cells} rates")

    # 5. every project points at v1 (new column only; payloads untouched)
    db.execute("UPDATE projects SET rate_card_id = %s WHERE rate_card_id IS NULL", (rc_id,))

    # 6. version numbers 1..N per project in save order (new column only)
    db.execute("""UPDATE project_versions SET version_no = n.rn
                  FROM (SELECT pid AS p, vid AS v,
                               ROW_NUMBER() OVER (PARTITION BY pid ORDER BY saved_at, vid) AS rn
                        FROM project_versions) n
                  WHERE project_versions.pid = n.p AND project_versions.vid = n.v AND project_versions.version_no IS NULL""")
