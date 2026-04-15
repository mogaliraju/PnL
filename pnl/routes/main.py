"""Main routes: index page, current-project data, global settings."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
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
IST = timezone(timedelta(hours=5, minutes=30))

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
    refreshed_at_ist = APP_REFRESHED_AT.astimezone(IST)
    return render_template(
        'index.html',
        app_refreshed_at_iso=refreshed_at_ist.isoformat(),
        app_refreshed_at_display=refreshed_at_ist.strftime('%d %b %Y %H:%M IST'),
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
    customer_revenue = defaultdict(float)
    role_counter = Counter()
    group_counter = Counter()
    saved_by_counter = Counter()
    status_counter = Counter()
    stage_counter = Counter()
    priority_counter = Counter()
    bu_counter = Counter()
    monthly_projects = defaultdict(int)
    margin_buckets = {'Below 20%': 0, '20–35%': 0, '35–50%': 0, '50%+': 0}

    STATUS_ORDER  = ['Won', 'Active', 'Submitted', 'Proposal', 'Draft', 'On Hold', 'Lost']
    STAGE_ORDER   = ['Qualification', 'Discovery', 'Solutioning', 'Proposal',
                     'Commercial Review', 'Negotiation', 'Closed Won', 'Closed Lost', 'Closed']
    PRIORITY_ORDER = ['Critical', 'High', 'Medium', 'Low']

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

        loc = (project.get('location') or '').strip()
        cust = (project.get('customer') or '').strip()
        if loc:
            location_counter[loc] += 1
        if cust:
            customer_counter[cust] += 1
            customer_revenue[cust] += costs['sell_cost']
        if meta.get('saved_by'):
            saved_by_counter[meta['saved_by']] += 1

        status_counter[(project.get('status') or 'Draft').strip()] += 1
        stage_counter[(project.get('stage') or 'Qualification').strip()] += 1
        priority_counter[(project.get('priority') or 'Medium').strip()] += 1
        bu = (project.get('business_unit') or '').strip()
        if bu:
            bu_counter[bu] += 1

        saved_at = meta.get('saved_at', '')
        if saved_at:
            monthly_projects[saved_at[:7]] += 1

        margin_pct = costs['gross_margin'] * 100
        if margin_pct < 20:
            margin_buckets['Below 20%'] += 1
        elif margin_pct < 35:
            margin_buckets['20–35%'] += 1
        elif margin_pct < 50:
            margin_buckets['35–50%'] += 1
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

    def ordered_list(counter, order, limit=None):
        result = [{'label': k, 'value': counter[k]} for k in order if k in counter]
        extras = [{'label': k, 'value': v} for k, v in counter.most_common() if k not in order]
        result += extras
        return result[:limit] if limit else result

    top_customers_by_rev = sorted(
        [{'label': k, 'value': round(v, 0)} for k, v in customer_revenue.items()],
        key=lambda x: x['value'], reverse=True
    )[:6]

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
        'status_breakdown':   ordered_list(status_counter, STATUS_ORDER),
        'stage_breakdown':    ordered_list(stage_counter, STAGE_ORDER),
        'priority_breakdown': ordered_list(priority_counter, PRIORITY_ORDER),
        'bu_breakdown':       [{'label': k, 'value': v} for k, v in bu_counter.most_common(8)],
        'top_locations':      [{'label': k, 'value': v} for k, v in location_counter.most_common(6)],
        'top_customers':      top_customers_by_rev,
        'top_roles_by_hours': [{'label': k, 'value': round(v, 1)} for k, v in role_counter.most_common(8)],
        'top_groups_by_hours':[{'label': k, 'value': round(v, 1)} for k, v in group_counter.most_common(8)],
        'projects_by_owner':  [{'label': k, 'value': v} for k, v in saved_by_counter.most_common(6)],
        'projects_by_month':  [
            {'label': m, 'value': monthly_projects[m]}
            for m in sorted(monthly_projects.keys())
        ],
        'margin_buckets': [{'label': k, 'value': v} for k, v in margin_buckets.items()],
    })
