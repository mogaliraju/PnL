from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from pnl.utils.storage import load_users, save_users
from pnl.utils.auth import login_required, admin_required
from pnl.utils.logger import get_logger
from datetime import datetime

bp = Blueprint('auth', __name__)
log = get_logger(__name__)


@bp.route('/login', methods=['GET'])
def login_page():
    if session.get('user'):
        return redirect(url_for('main.index'))
    return render_template('login.html')


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
    session['user'] = username
    session['role'] = user['role']
    session['name'] = user.get('name', username)
    log.info(f"User '{username}' logged in")
    return jsonify({'status': 'ok', 'role': user['role'], 'name': user.get('name', username)})


@bp.route('/logout')
def logout():
    log.info(f"User '{session.get('user')}' logged out")
    session.clear()
    return redirect(url_for('auth.login_page'))


@bp.route('/api/me')
@login_required
def me():
    return jsonify({'username': session['user'], 'role': session['role'], 'name': session['name']})


# ── User management ───────────────────────────────────────────
@bp.route('/api/users', methods=['GET'])
@login_required
@admin_required
def list_users():
    users = load_users()
    return jsonify([
        {'username': u, 'name': d.get('name',''), 'role': d.get('role','user'),
         'created_at': d.get('created_at','')}
        for u, d in users.items()
    ])


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
    users = load_users()
    if username in users:
        return jsonify({'error': 'User already exists'}), 409
    users[username] = {
        'password':   generate_password_hash(password),
        'role':       role,
        'name':       name or username,
        'created_at': datetime.now().isoformat(timespec='seconds')
    }
    save_users(users)
    log.info(f"Admin created user '{username}' with role '{role}'")
    return jsonify({'status': 'ok'})


@bp.route('/api/users/<username>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(username):
    if username == 'admin':
        return jsonify({'error': 'Cannot delete the admin account'}), 400
    users = load_users()
    users.pop(username, None)
    save_users(users)
    log.info(f"Admin deleted user '{username}'")
    return jsonify({'status': 'ok'})


@bp.route('/api/users/<username>/password', methods=['POST'])
@login_required
def change_password(username):
    if session.get('role') != 'admin' and session.get('user') != username:
        return jsonify({'error': 'Forbidden'}), 403
    data   = request.json or {}
    new_pw = data.get('password', '').strip()
    if not new_pw:
        return jsonify({'error': 'Password required'}), 400
    users = load_users()
    if username not in users:
        return jsonify({'error': 'User not found'}), 404
    users[username]['password'] = generate_password_hash(new_pw)
    save_users(users)
    log.info(f"Password changed for '{username}'")
    return jsonify({'status': 'ok'})
