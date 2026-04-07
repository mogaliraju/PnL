import os

BASE_DIR      = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR      = os.environ.get('DATA_DIR', BASE_DIR)
DATA_FILE     = os.path.join(DATA_DIR, 'data.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
PROJECTS_DIR  = os.path.join(DATA_DIR, 'projects')
VERSIONS_DIR  = os.path.join(DATA_DIR, 'versions')
USERS_FILE    = os.path.join(DATA_DIR, 'users.json')
DB_FILE       = os.path.join(DATA_DIR, 'pnl.sqlite3')
LOG_FILE      = os.path.join(DATA_DIR, 'pnl.log')

APP_ENV = os.environ.get('PNL_ENV') or os.environ.get('FLASK_ENV') or 'development'
IS_PRODUCTION = APP_ENV.lower() == 'production'

_secret_key = os.environ.get('SECRET_KEY')
if _secret_key:
    SECRET_KEY = _secret_key
elif IS_PRODUCTION:
    raise RuntimeError('SECRET_KEY must be set when PNL_ENV=production')
else:
    SECRET_KEY = 'pnl-dev-insecure-secret'

for d in [PROJECTS_DIR, VERSIONS_DIR]:
    os.makedirs(d, exist_ok=True)

# Seed data.json from bundled copy on first run
_SEED = os.path.join(BASE_DIR, 'data.json')
if not os.path.exists(DATA_FILE) and os.path.exists(_SEED) and DATA_DIR != BASE_DIR:
    import shutil
    shutil.copy(_SEED, DATA_FILE)
