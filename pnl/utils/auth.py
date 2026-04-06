from functools import wraps
from flask import session, request, jsonify, redirect, url_for


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            if request.is_json:
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            if request.is_json:
                return jsonify({'error': 'Admin access required'}), 403
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated
