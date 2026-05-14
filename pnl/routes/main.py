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
from pnl.services.pnl_service import compute_costs, resolve_margin_inputs

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
        editor_mode=False,
        editor_pid='',
        editor_project_name='',
        launch_new=False,
        home_href='/',
        app_refreshed_at_iso=refreshed_at_ist.isoformat(),
        app_refreshed_at_display=refreshed_at_ist.strftime('%d %b %Y %H:%M IST'),
    )


@bp.route('/project-editor')
@login_required
def project_editor_new():
    refreshed_at_ist = APP_REFRESHED_AT.astimezone(IST)
    return render_template(
        'index.html',
        editor_mode=True,
        editor_pid='',
        editor_project_name='',
        launch_new=True,
        home_href='/',
        app_refreshed_at_iso=refreshed_at_ist.isoformat(),
        app_refreshed_at_display=refreshed_at_ist.strftime('%d %b %Y %H:%M IST'),
    )


@bp.route('/project-editor/<pid>')
@login_required
def project_editor_existing(pid):
    refreshed_at_ist = APP_REFRESHED_AT.astimezone(IST)
    return render_template(
        'index.html',
        editor_mode=True,
        editor_pid=pid,
        editor_project_name='',
        launch_new=False,
        home_href='/',
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
    ax_margin_sum = 0.0
    cloud4c_margin_sum = 0.0

    location_counter = Counter()
    customer_counter = Counter()
    customer_revenue = defaultdict(float)
    customer_ax_margins = defaultdict(list)
    role_counter = Counter()
    group_counter = Counter()
    saved_by_counter = Counter()
    status_counter = Counter()
    stage_counter = Counter()
    priority_counter = Counter()
    bu_counter = Counter()
    monthly_projects = defaultdict(int)
    margin_buckets = {'Below 20%': 0, '20–35%': 0, '35–50%': 0, '50%+': 0}
    ax_margin_buckets = {'Below 10%': 0, '10–15%': 0, '15–20%': 0, '20%+': 0}
    status_revenue = defaultdict(float)
    stage_revenue = defaultdict(float)
    projects_summary = []

    STATUS_ORDER  = ['Won', 'Active', 'Submitted', 'Proposal', 'Draft', 'On Hold', 'Lost']
    STAGE_ORDER   = ['Qualification', 'Discovery', 'Solutioning', 'Proposal',
                     'Commercial Review', 'Negotiation', 'Closed Won', 'Closed Lost', 'Closed']
    PRIORITY_ORDER = ['Critical', 'High', 'Medium', 'Low']

    for payload in projects:
        meta = payload.get('_meta', {})
        project = payload.get('project', {})
        resources = payload.get('resources', [])
        cloud4c_margin, ax_margin = resolve_margin_inputs(payload)
        costs = compute_costs(
            resources,
            payload.get('rate_card', []),
            cloud4c_margin=cloud4c_margin,
            ax_margin=ax_margin,
            one_time_costs=payload.get('one_time_costs', []),
        )

        total_resources += len(resources)
        total_hours += sum(float(r.get('hours') or 0) for r in resources)
        total_input_cost += costs['input_cost']
        total_revenue += costs['sell_cost']
        margin_sum += costs['gross_margin']
        ax_margin_sum += costs['ax_margin']
        cloud4c_margin_sum += costs['cloud4c_margin']

        loc = (project.get('location') or '').strip()
        cust = (project.get('customer') or '').strip()
        status = (project.get('status') or 'Draft').strip()
        stage = (project.get('stage') or 'Qualification').strip()

        if loc:
            location_counter[loc] += 1
        if cust:
            customer_counter[cust] += 1
            customer_revenue[cust] += costs['sell_cost']
            customer_ax_margins[cust].append(costs['ax_margin'])
        if meta.get('saved_by'):
            saved_by_counter[meta['saved_by']] += 1

        status_counter[status] += 1
        stage_counter[stage] += 1
        status_revenue[status] += costs['sell_cost']
        stage_revenue[stage] += costs['sell_cost']
        priority_counter[(project.get('priority') or 'Medium').strip()] += 1
        bu = (project.get('business_unit') or '').strip()
        if bu:
            bu_counter[bu] += 1

        saved_at = meta.get('saved_at', '')
        if saved_at:
            monthly_projects[saved_at[:7]] += 1

        projects_summary.append({
            'name': meta.get('name') or cust or 'Unnamed',
            'customer': cust,
            'status': status,
            'stage': stage,
            'priority': (project.get('priority') or 'Medium').strip(),
            'revenue': round(costs['sell_cost'], 0),
            'input_cost': round(costs['input_cost'], 0),
            'ax_margin': round(costs['ax_margin'] * 100, 1),
            'cloud4c_margin': round(costs['cloud4c_margin'] * 100, 1),
            'gross_margin': round(costs['gross_margin'] * 100, 1),
        })

        margin_pct = costs['gross_margin'] * 100
        if margin_pct < 20:
            margin_buckets['Below 20%'] += 1
        elif margin_pct < 35:
            margin_buckets['20–35%'] += 1
        elif margin_pct < 50:
            margin_buckets['35–50%'] += 1
        else:
            margin_buckets['50%+'] += 1

        ax_pct = costs['ax_margin'] * 100
        if ax_pct < 10:
            ax_margin_buckets['Below 10%'] += 1
        elif ax_pct < 15:
            ax_margin_buckets['10–15%'] += 1
        elif ax_pct < 20:
            ax_margin_buckets['15–20%'] += 1
        else:
            ax_margin_buckets['20%+'] += 1

        for resource in resources:
            role = resource.get('role', '').strip()
            group = resource.get('group', '').strip()
            hours = float(resource.get('hours') or 0)
            if role:
                role_counter[role] += hours
            if group:
                group_counter[group] += hours

    avg_margin = (margin_sum / total_projects) if total_projects else 0
    avg_ax_margin = (ax_margin_sum / total_projects) if total_projects else 0
    avg_cloud4c_margin = (cloud4c_margin_sum / total_projects) if total_projects else 0
    avg_resources = (total_resources / total_projects) if total_projects else 0

    def ordered_list(counter, order, limit=None):
        result = [{'label': k, 'value': counter[k]} for k in order if k in counter]
        extras = [{'label': k, 'value': v} for k, v in counter.most_common() if k not in order]
        result += extras
        return result[:limit] if limit else result

    top_customers_by_rev = sorted(
        [{
            'label': k,
            'value': round(v, 0),
            'ax_margin': round(sum(customer_ax_margins[k]) / len(customer_ax_margins[k]) * 100, 1) if customer_ax_margins[k] else 0,
        } for k, v in customer_revenue.items()],
        key=lambda x: x['value'], reverse=True
    )[:8]

    won_submitted_revenue = sum(
        v for s, v in status_revenue.items()
        if s.lower() in ('won', 'active', 'submitted')
    )
    at_risk = [p for p in projects_summary if p['ax_margin'] < 20]

    return jsonify({
        'kpis': {
            'projects': total_projects,
            'resources': total_resources,
            'hours': round(total_hours, 1),
            'input_cost': round(total_input_cost, 2),
            'revenue': round(total_revenue, 2),
            'gross_profit': round(total_revenue - total_input_cost, 2),
            'avg_margin': round(avg_margin, 4),
            'avg_ax_margin': round(avg_ax_margin, 4),
            'avg_cloud4c_margin': round(avg_cloud4c_margin, 4),
            'avg_resources_per_project': round(avg_resources, 1),
            'active_pipeline': round(won_submitted_revenue, 2),
            'at_risk_count': len(at_risk),
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
        'margin_buckets':  [{'label': k, 'value': v} for k, v in margin_buckets.items()],
        'ax_margin_buckets': [{'label': k, 'value': v} for k, v in ax_margin_buckets.items()],
        'status_revenue':  [
            {'label': k, 'count': status_counter[k], 'value': round(status_revenue[k], 0)}
            for k in STATUS_ORDER if k in status_revenue
        ],
        'stage_revenue':   [
            {'label': k, 'count': stage_counter[k], 'value': round(stage_revenue[k], 0)}
            for k in STAGE_ORDER if k in stage_revenue
        ],
        'projects_summary': sorted(projects_summary, key=lambda p: p['ax_margin']),
        'at_risk': sorted(at_risk, key=lambda p: p['ax_margin']),
    })
