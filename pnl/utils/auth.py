from functools import wraps
from flask import session, request, jsonify, redirect, url_for

# While a user still has an admin-set temporary password, only these endpoints work.
_ALLOWED_WHILE_CHANGING = {'auth.change_password', 'auth.logout', 'auth.me', 'auth.login', 'auth.login_page', 'static'}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('auth.login_page'))
        if session.get('must_change') and request.endpoint not in _ALLOWED_WHILE_CHANGING:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Set a new password before continuing.', 'must_change_password': True}), 403
            return redirect(url_for('auth.login_page', change=1))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Admin access required'}), 403
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated
