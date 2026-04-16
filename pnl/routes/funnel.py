"""Funnel Report CRUD routes."""
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from pnl.utils.storage import (
    list_funnel_entries,
    save_funnel_entry,
    load_funnel_entry,
    delete_funnel_entry,
    safe_filename,
    load_custom_fields,
    save_custom_fields,
    load_column_labels,
    save_column_labels,
)
from pnl.utils.auth import login_required
from pnl.utils.logger import get_logger

bp = Blueprint('funnel', __name__)
log = get_logger(__name__)

STAGES = ['Identified', 'Qualified', 'Proposal Sent', 'Negotiation', 'Closed Won', 'Closed Lost', 'Pipeline']
PRODUCTS = ['Data', 'SAP Services', 'Echo', 'AE', 'AI', 'Connect / Echo', 'MWP', 'RPA']
REGIONS = ['India', 'MEST', 'ASEAN', 'ROW', 'APAC', 'North America', 'South America', 'Europe']
NET_FORECASTING = ['Pipeline', 'Upside', 'Best Case', 'Commit']


@bp.route('/api/funnel', methods=['GET'])
@login_required
def list_funnel():
    return jsonify(list_funnel_entries())


@bp.route('/api/funnel', methods=['POST'])
@login_required
def create_funnel():
    data = request.json or {}
    entry_id = 'funnel_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:22]
    data['saved_at'] = datetime.now().isoformat(timespec='seconds')
    data['saved_by'] = session.get('user', '')
    data['id'] = entry_id
    save_funnel_entry(entry_id, data)
    log.info(f"Funnel entry '{entry_id}' created by '{session.get('user')}'")
    return jsonify({'status': 'ok', 'id': entry_id})


@bp.route('/api/funnel/<entry_id>', methods=['GET'])
@login_required
def get_funnel(entry_id):
    entry = load_funnel_entry(entry_id)
    if entry is None:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(entry)


@bp.route('/api/funnel/<entry_id>', methods=['PUT'])
@login_required
def update_funnel(entry_id):
    existing = load_funnel_entry(entry_id)
    if existing is None:
        return jsonify({'error': 'Not found'}), 404
    data = request.json or {}
    data['id'] = entry_id
    data['saved_at'] = datetime.now().isoformat(timespec='seconds')
    data['saved_by'] = session.get('user', '')
    save_funnel_entry(entry_id, data)
    log.info(f"Funnel entry '{entry_id}' updated by '{session.get('user')}'")
    return jsonify({'status': 'ok', 'id': entry_id})


@bp.route('/api/funnel/<entry_id>', methods=['DELETE'])
@login_required
def delete_funnel(entry_id):
    delete_funnel_entry(entry_id)
    log.info(f"Funnel entry '{entry_id}' deleted by '{session.get('user')}'")
    return jsonify({'status': 'ok'})


@bp.route('/api/funnel/meta/options')
@login_required
def funnel_options():
    return jsonify({
        'stages': STAGES,
        'products': PRODUCTS,
        'regions': REGIONS,
        'net_forecasting': NET_FORECASTING,
    })


@bp.route('/api/funnel/meta/custom-fields', methods=['GET'])
@login_required
def get_funnel_custom_fields():
    return jsonify({
        'custom_fields': load_custom_fields('funnel'),
        'column_labels': load_column_labels('funnel'),
    })


@bp.route('/api/funnel/meta/custom-fields', methods=['POST'])
@login_required
def save_funnel_custom_fields():
    body = request.json or {}
    if 'custom_fields' in body:
        save_custom_fields('funnel', body['custom_fields'])
    if 'column_labels' in body:
        save_column_labels('funnel', body['column_labels'])
    return jsonify({'status': 'ok'})
