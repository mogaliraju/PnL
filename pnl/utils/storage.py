import json
import re
import os
from datetime import datetime
from werkzeug.security import generate_password_hash
from pnl.config import DATA_FILE, SETTINGS_FILE, USERS_FILE
from pnl.utils.logger import get_logger

log = get_logger(__name__)


def safe_filename(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name.strip())


def _read_json_file(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write_json_file(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as target:
        json.dump(payload, target, indent=2)
        target.flush()
        os.fsync(target.fileno())


def _merge_global_settings(data: dict, settings: dict) -> dict:
    merged = dict(data)
    if settings.get('rate_card'):
        merged['rate_card'] = settings['rate_card']
    if settings.get('role_catalog'):
        merged['role_catalog'] = settings['role_catalog']
    return merged


def load_global_settings() -> dict:
    return _read_json_file(SETTINGS_FILE, {})


def save_global_settings(settings: dict):
    _write_json_file(SETTINGS_FILE, settings)
    log.info("Settings saved")


def load_working_data() -> dict:
    data = _read_json_file(DATA_FILE, {})
    return _merge_global_settings(data, load_global_settings())


def save_working_data(data: dict):
    _write_json_file(DATA_FILE, data)
    s = load_global_settings()
    if data.get('rate_card'):
        s['rate_card'] = data['rate_card']
    if data.get('role_catalog'):
        s['role_catalog'] = data['role_catalog']
    save_global_settings(s)


def merge_settings(data: dict) -> dict:
    """Inject current global rate card + catalog into a project dict."""
    return _merge_global_settings(data, load_global_settings())


def load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        bootstrap_password = os.environ.get('PNL_BOOTSTRAP_ADMIN_PASSWORD', '').strip()
        bootstrap_username = os.environ.get('PNL_BOOTSTRAP_ADMIN_USERNAME', 'admin').strip() or 'admin'
        bootstrap_name = os.environ.get('PNL_BOOTSTRAP_ADMIN_NAME', 'Administrator').strip() or 'Administrator'

        if bootstrap_password:
            admin = {
                bootstrap_username.lower(): {
                    'password': generate_password_hash(bootstrap_password),
                    'role': 'admin',
                    'name': bootstrap_name,
                    'created_at': datetime.now().isoformat(timespec='seconds')
                }
            }
            _write_json_file(USERS_FILE, admin)
            log.warning("Bootstrapped admin user from environment because users.json was missing")
            return admin

        log.warning("users.json is missing and no bootstrap admin password was provided")
        return {}
    return _read_json_file(USERS_FILE, {})


def save_users(users: dict):
    _write_json_file(USERS_FILE, users)


# Backwards-compatible names for existing imports while the codebase is refactored.
load_settings = load_global_settings
save_settings = save_global_settings
load_data = load_working_data
save_data = save_working_data
