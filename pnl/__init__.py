"""PnL application factory."""
from flask import Flask
from pnl.config import SECRET_KEY
from pnl.utils.logger import get_logger

log = get_logger(__name__)


def create_app() -> Flask:
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.secret_key = SECRET_KEY

    from pnl.routes import auth, main, projects, export, import_excel
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(projects.bp)
    app.register_blueprint(export.bp)
    app.register_blueprint(import_excel.bp)

    log.info("PnL application created")
    return app
