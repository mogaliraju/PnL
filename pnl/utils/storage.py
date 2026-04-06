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


# ── Settings ──────────────────────────────────────────────────
def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, 'r') as f:
        return json.load(f)


def save_settings(s: dict):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(s, f, indent=2)
    log.info("Settings saved")


# ── Project data ──────────────────────────────────────────────
def load_data() -> dict:
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    s = load_settings()
    if s.get('rate_card'):
        data['rate_card'] = s['rate_card']
    if s.get('role_catalog'):
        data['role_catalog'] = s['role_catalog']
    return data


def save_data(data: dict):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    s = load_settings()
    if data.get('rate_card'):
        s['rate_card'] = data['rate_card']
    if data.get('role_catalog'):
        s['role_catalog'] = data['role_catalog']
    save_settings(s)


def merge_settings(data: dict) -> dict:
    """Inject current global rate card + catalog into a project dict."""
    s = load_settings()
    if s.get('rate_card'):
        data['rate_card'] = s['rate_card']
    if s.get('role_catalog'):
        data['role_catalog'] = s['role_catalog']
    return data


# ── Users ─────────────────────────────────────────────────────
def load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        admin = {
            'admin': {
                'password':   generate_password_hash('admin123'),
                'role':       'admin',
                'name':       'Administrator',
                'created_at': datetime.now().isoformat(timespec='seconds')
            }
        }
        with open(USERS_FILE, 'w') as f:
            json.dump(admin, f, indent=2)
        log.info("Created default admin user")
        return admin
    with open(USERS_FILE, 'r') as f:
        return json.load(f)


def save_users(users: dict):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)
