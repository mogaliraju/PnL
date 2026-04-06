"""Main routes: index page, current-project data, global settings."""
from datetime import date
from flask import Blueprint, render_template, request, jsonify, session
from pnl.utils.storage import load_data, save_data, load_settings, save_settings
from pnl.utils.auth import login_required
from pnl.utils.logger import get_logger

bp = Blueprint('main', __name__)
log = get_logger(__name__)

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
    return render_template('index.html')


@bp.route('/api/data', methods=['GET'])
@login_required
def get_data():
    return jsonify(load_data())


@bp.route('/api/data', methods=['POST'])
@login_required
def update_data():
    data = request.json
    save_data(data)
    log.info(f"Data saved by '{session.get('user')}'")
    return jsonify({'status': 'ok'})


@bp.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    s = request.json or {}
    existing = load_settings()
    if s.get('rate_card'):
        existing['rate_card'] = s['rate_card']
    if s.get('role_catalog'):
        existing['role_catalog'] = s['role_catalog']
    save_settings(existing)
    log.info(f"Settings updated by '{session.get('user')}'")
    return jsonify({'status': 'ok'})
