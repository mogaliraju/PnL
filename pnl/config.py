import os

BASE_DIR      = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR      = os.environ.get('DATA_DIR', BASE_DIR)
DATA_FILE     = os.path.join(DATA_DIR, 'data.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
PROJECTS_DIR  = os.path.join(DATA_DIR, 'projects')
VERSIONS_DIR  = os.path.join(DATA_DIR, 'versions')
USERS_FILE    = os.path.join(DATA_DIR, 'users.json')
LOG_FILE      = os.path.join(DATA_DIR, 'pnl.log')

SECRET_KEY = os.environ.get('SECRET_KEY', 'ax-pnl-secret-2026-change-in-prod')

for d in [PROJECTS_DIR, VERSIONS_DIR]:
    os.makedirs(d, exist_ok=True)

# Seed data.json from bundled copy on first run
_SEED = os.path.join(BASE_DIR, 'data.json')
if not os.path.exists(DATA_FILE) and os.path.exists(_SEED) and DATA_DIR != BASE_DIR:
    import shutil
    shutil.copy(_SEED, DATA_FILE)
