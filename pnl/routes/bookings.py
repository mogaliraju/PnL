"""Order Bookings & Commits CRUD routes."""
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from pnl.utils.storage import (
    list_order_bookings,
    save_order_booking,
    load_order_booking,
    delete_order_booking,
    load_custom_fields,
    save_custom_fields,
    load_column_labels,
    save_column_labels,
)
from pnl.utils.auth import login_required
from pnl.utils.logger import get_logger

bp = Blueprint('bookings', __name__)
log = get_logger(__name__)

BUS = ['SAP', 'EDM', 'AE', 'AI', 'MWP', 'RPA', 'Data']


@bp.route('/api/bookings', methods=['GET'])
@login_required
def list_bookings():
    booking_type = request.args.get('type')  # OTC or MRC
    return jsonify(list_order_bookings(booking_type))


@bp.route('/api/bookings', methods=['POST'])
@login_required
def create_booking():
    data = request.json or {}
    booking_id = 'booking_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:24]
    data['saved_at'] = datetime.now().isoformat(timespec='seconds')
    data['saved_by'] = session.get('user', '')
    data['id'] = booking_id
    save_order_booking(booking_id, data)
    log.info(f"Booking '{booking_id}' ({data.get('booking_type','OTC')}) created by '{session.get('user')}'")
    return jsonify({'status': 'ok', 'id': booking_id})


@bp.route('/api/bookings/<booking_id>', methods=['GET'])
@login_required
def get_booking(booking_id):
    entry = load_order_booking(booking_id)
    if entry is None:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(entry)


@bp.route('/api/bookings/<booking_id>', methods=['PUT'])
@login_required
def update_booking(booking_id):
    existing = load_order_booking(booking_id)
    if existing is None:
        return jsonify({'error': 'Not found'}), 404
    data = request.json or {}
    data['id'] = booking_id
    data['saved_at'] = datetime.now().isoformat(timespec='seconds')
    data['saved_by'] = session.get('user', '')
    save_order_booking(booking_id, data)
    log.info(f"Booking '{booking_id}' updated by '{session.get('user')}'")
    return jsonify({'status': 'ok', 'id': booking_id})


@bp.route('/api/bookings/<booking_id>', methods=['DELETE'])
@login_required
def delete_booking(booking_id):
    delete_order_booking(booking_id)
    log.info(f"Booking '{booking_id}' deleted by '{session.get('user')}'")
    return jsonify({'status': 'ok'})


@bp.route('/api/bookings/meta/options')
@login_required
def bookings_options():
    return jsonify({'bus': BUS})


@bp.route('/api/bookings/meta/custom-fields', methods=['GET'])
@login_required
def get_bookings_custom_fields():
    return jsonify({
        'custom_fields': load_custom_fields('bookings'),
        'column_labels': load_column_labels('bookings'),
    })


@bp.route('/api/bookings/meta/custom-fields', methods=['POST'])
@login_required
def save_bookings_custom_fields():
    body = request.json or {}
    if 'custom_fields' in body:
        save_custom_fields('bookings', body['custom_fields'])
    if 'column_labels' in body:
        save_column_labels('bookings', body['column_labels'])
    return jsonify({'status': 'ok'})
