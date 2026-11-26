from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import re

from pnl.utils.storage import (FeatureUnavailable, UserExists, create_user as storage_create_user, load_users,
                               set_user_active, set_user_password)
from pnl.utils.auth import login_required, admin_required
from pnl.utils.logger import get_logger
from datetime import datetime

bp = Blueprint('auth', __name__)
log = get_logger(__name__)


@bp.route('/login', methods=['GET'])
def login_page():
    if session.get('user') and not session.get('must_change'):
        return redirect(url_for('main.index'))
    return render_template('login.html', must_change=bool(session.get('user') and session.get('must_change')),
                           username=session.get('user', ''))


@bp.route('/login', methods=['POST'])
def login():
    data     = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    users    = load_users()
    user     = users.get(username)
    if not user or not check_password_hash(user['password'], password):
        log.warning(f"Failed login attempt for '{username}'")
        return jsonify({'error': 'Invalid username or password'}), 401
    if not user.get('active', True):
        log.warning(f"Sign-in refused for switched-off user '{username}'")
        return jsonify({'error': 'This account has been switched off. Ask an admin if you need access again.',
                        'inactive': True}), 403
    session['user'] = username
    session['role'] = user['role']
    session['name'] = user.get('name', username)
    session['must_change'] = bool(user.get('must_change_password'))
    log.info(f"User '{username}' logged in")
    return jsonify({'status': 'ok', 'role': user['role'], 'name': user.get('name', username),
                    'must_change_password': session['must_change']})


@bp.route('/logout')
def logout():
    log.info(f"User '{session.get('user')}' logged out")
    session.clear()
    return redirect(url_for('auth.login_page'))


@bp.route('/api/me')
@login_required
def me():
    return jsonify({'username': session['user'], 'role': session['role'], 'name': session['name'],
                    'must_change_password': bool(session.get('must_change'))})


# ── User management ───────────────────────────────────────────
@bp.route('/api/users', methods=['GET'])
@login_required
@admin_required
def list_users():
    users = load_users()
    return jsonify([
        {'username': u, 'name': d.get('name', ''), 'role': d.get('role', 'user'),
         'created_at': d.get('created_at', ''), 'active': d.get('active', True),
         'must_change_password': d.get('must_change_password', False), 'deactivated_at': d.get('deactivated_at', '')}
        for u, d in users.items()
    ])


MIN_PASSWORD = 8
USERNAME_RE = re.compile(r'^[a-z0-9][a-z0-9._-]{1,39}$')


def _active_admins(users: dict) -> list[str]:
    return [u for u, d in users.items() if d.get('role') == 'admin' and d.get('active', True)]


@bp.route('/api/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    data     = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '').strip()
    name     = data.get('name', '').strip()
    role     = data.get('role', 'user')
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    if not USERNAME_RE.match(username):
        return jsonify({'error': 'Usernames use 2 to 40 lowercase letters, numbers, dots, dashes or underscores.'}), 400
    if len(password) < MIN_PASSWORD:
        return jsonify({'error': f'The temporary password needs at least {MIN_PASSWORD} characters.'}), 400
    if role not in ('user', 'admin'):
        return jsonify({'error': 'Role must be user or admin.'}), 400
    try:
        # A password set by an admin is temporary: the user changes it at the next sign-in.
        storage_create_user(username, generate_password_hash(password), role, name or username, must_change_password=True)
    except UserExists:
        return jsonify({'error': f'There is already a user called "{username}".'}), 409
    log.info(f"Admin '{session.get('user')}' created user '{username}' with role '{role}'")
    return jsonify({'status': 'ok'})


def _set_active(username, active):
    users = load_users()
    if username not in users:
        return jsonify({'error': 'That user does not exist.'}), 404
    if not active:
        if username == session.get('user'):
            return jsonify({'error': "You can't remove your own account."}), 400
        if users[username].get('role') == 'admin' and _active_admins(users) == [username]:
            return jsonify({'error': 'This is the last active admin. Make someone else an admin first.'}), 400
    try:
        set_user_active(username, active, session.get('user', ''))
    except FeatureUnavailable as e:
        return jsonify({'error': str(e)}), 503
    log.info(f"User '{username}' {'restored' if active else 'switched off'} by '{session.get('user')}'")
    return jsonify({'status': 'active' if active else 'removed'})


@bp.route('/api/users/<username>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(username):
    # Users are switched off, never deleted: saved versions name their authors (DESIGN.md 5.6).
    return _set_active(username, False)


@bp.route('/api/users/<username>/active', methods=['POST'])
@login_required
@admin_required
def set_active(username):
    return _set_active(username, bool((request.json or {}).get('active', True)))


@bp.route('/api/users/<username>/password', methods=['POST'])
@login_required
def change_password(username):
    me = session.get('user')
    is_admin = session.get('role') == 'admin'
    if not is_admin and me != username:
        return jsonify({'error': 'Forbidden'}), 403
    data   = request.json or {}
    new_pw = data.get('password', '').strip()
    if not new_pw:
        return jsonify({'error': 'Password required'}), 400
    if len(new_pw) < MIN_PASSWORD:
        return jsonify({'error': f'Passwords need at least {MIN_PASSWORD} characters.'}), 400
    users = load_users()
    if username not in users:
        return jsonify({'error': 'User not found'}), 404
    if me == username:
        # Changing your own password needs the current one.
        if not check_password_hash(users[username]['password'], data.get('current_password', '')):
            return jsonify({'error': "Your current password isn't right."}), 400
        if check_password_hash(users[username]['password'], new_pw):
            return jsonify({'error': 'Choose a password different from the current one.'}), 400
        set_user_password(username, generate_password_hash(new_pw), must_change=False)
        session['must_change'] = False
    else:
        # An admin reset is temporary: the user must change it at the next sign-in.
        set_user_password(username, generate_password_hash(new_pw), must_change=True)
    log.info(f"Password {'changed' if me == username else 'reset'} for '{username}' by '{me}'")
    return jsonify({'status': 'ok'})
