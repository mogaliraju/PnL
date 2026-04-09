"""Main routes: index page, current-project data, global settings."""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from flask import Blueprint, render_template, request, jsonify, session
from pnl.utils.storage import (
    load_all_project_records,
    load_working_data,
    save_working_data,
    load_global_settings,
    save_global_settings,
)
from pnl.utils.auth import login_required
from pnl.utils.logger import get_logger
from pnl.services.pnl_service import compute_costs

bp = Blueprint('main', __name__)
log = get_logger(__name__)
APP_REFRESHED_AT = datetime.now(timezone.utc)

# Simple in-process daily cache — resets on server restart, refreshes each new day
_fx_cache = {'date': None, 'rate': None, 'updated': None}


@bp.route('/api/exchange-rate')
@login_required
def exchange_rate():
    today = date.today().isoformat()
    if _fx_cache['date'] != today:
        try:
            import requests as _req
            r = _req.get('https://open.er-api.com/v6/latest/USD', timeout=6)
            r.raise_for_status()
            body = r.json()
            _fx_cache['date']    = today
            _fx_cache['rate']    = body['rates']['INR']
            _fx_cache['updated'] = body.get('time_last_update_utc', '')
            log.info(f"Exchange rate refreshed: 1 USD = {_fx_cache['rate']} INR")
        except Exception as e:
            log.warning(f"Exchange rate fetch failed: {e}")
            if _fx_cache['rate'] is None:
                return jsonify({'error': str(e)}), 503
    return jsonify({
        'usd_to_inr': _fx_cache['rate'],
        'updated':    _fx_cache['updated'],
        'cached_date': _fx_cache['date'],
    })


@bp.route('/')
@login_required
def index():
    return render_template(
        'index.html',
        app_refreshed_at_iso=APP_REFRESHED_AT.isoformat(),
        app_refreshed_at_display=APP_REFRESHED_AT.strftime('%d %b %Y %H:%M UTC'),
    )


@bp.route('/api/data', methods=['GET'])
@login_required
def get_data():
    return jsonify(load_working_data())


@bp.route('/api/data', methods=['POST'])
@login_required
def update_data():
    data = request.json
    save_working_data(data)
    log.info(f"Data saved by '{session.get('user')}'")
    return jsonify({'status': 'ok'})


@bp.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    s = request.json or {}
    existing = load_global_settings()
    if s.get('rate_card'):
        existing['rate_card'] = s['rate_card']
    if s.get('role_catalog'):
        existing['role_catalog'] = s['role_catalog']
    if s.get('business_units'):
        existing['business_units'] = s['business_units']
    save_global_settings(existing)
    log.info(f"Settings updated by '{session.get('user')}'")
    return jsonify({'status': 'ok'})


@bp.route('/api/dashboard')
@login_required
def dashboard_data():
    projects = load_all_project_records()

    total_projects = len(projects)
    total_resources = 0
    total_hours = 0.0
    total_input_cost = 0.0
    total_revenue = 0.0
    margin_sum = 0.0

    location_counter = Counter()
    customer_counter = Counter()
    role_counter = Counter()
    group_counter = Counter()
    saved_by_counter = Counter()
    monthly_projects = defaultdict(int)
    margin_buckets = {
        'Below 20%': 0,
        '20%-35%': 0,
        '35%-50%': 0,
        '50%+': 0,
    }

    for payload in projects:
        meta = payload.get('_meta', {})
        project = payload.get('project', {})
        resources = payload.get('resources', [])
        target_margin = float(payload.get('target_margin', 0.40))
        costs = compute_costs(resources, payload.get('rate_card', []), target_margin)

        total_resources += len(resources)
        total_hours += sum(float(r.get('hours') or 0) for r in resources)
        total_input_cost += costs['input_cost']
        total_revenue += costs['sell_cost']
        margin_sum += costs['gross_margin']

        if project.get('location'):
            location_counter[project['location']] += 1
        if project.get('customer'):
            customer_counter[project['customer']] += 1
        if meta.get('saved_by'):
            saved_by_counter[meta['saved_by']] += 1

        saved_at = meta.get('saved_at', '')
        if saved_at:
            monthly_projects[saved_at[:7]] += 1

        margin_pct = costs['gross_margin'] * 100
        if margin_pct < 20:
            margin_buckets['Below 20%'] += 1
        elif margin_pct < 35:
            margin_buckets['20%-35%'] += 1
        elif margin_pct < 50:
            margin_buckets['35%-50%'] += 1
        else:
            margin_buckets['50%+'] += 1

        for resource in resources:
            role = resource.get('role', '').strip()
            group = resource.get('group', '').strip()
            hours = float(resource.get('hours') or 0)
            if role:
                role_counter[role] += hours
            if group:
                group_counter[group] += hours

    avg_margin = (margin_sum / total_projects) if total_projects else 0
    avg_resources = (total_resources / total_projects) if total_projects else 0

    return jsonify({
        'kpis': {
            'projects': total_projects,
            'resources': total_resources,
            'hours': round(total_hours, 1),
            'input_cost': round(total_input_cost, 2),
            'revenue': round(total_revenue, 2),
            'avg_margin': round(avg_margin, 4),
            'avg_resources_per_project': round(avg_resources, 1),
        },
        'top_locations': [{'label': k, 'value': v} for k, v in location_counter.most_common(6)],
        'top_customers': [{'label': k, 'value': v} for k, v in customer_counter.most_common(6)],
        'top_roles_by_hours': [{'label': k, 'value': round(v, 1)} for k, v in role_counter.most_common(8)],
        'top_groups_by_hours': [{'label': k, 'value': round(v, 1)} for k, v in group_counter.most_common(8)],
        'projects_by_owner': [{'label': k, 'value': v} for k, v in saved_by_counter.most_common(6)],
        'projects_by_month': [
            {'label': month, 'value': monthly_projects[month]}
            for month in sorted(monthly_projects.keys())
        ],
        'margin_buckets': [{'label': k, 'value': v} for k, v in margin_buckets.items()],
    })
