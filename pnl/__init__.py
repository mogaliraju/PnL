"""PnL application factory."""
from flask import Flask, request
from werkzeug.exceptions import HTTPException
from pnl.config import SECRET_KEY
from pnl.utils.logger import get_logger

log = get_logger(__name__)


def create_app() -> Flask:
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.secret_key = SECRET_KEY

    from pnl.routes import auth, main, projects, export, import_excel, funnel, bookings
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(projects.bp)
    app.register_blueprint(export.bp)
    app.register_blueprint(import_excel.bp)
    app.register_blueprint(funnel.bp)
    app.register_blueprint(bookings.bp)

    @app.errorhandler(Exception)
    def handle_api_error(err):
        """Ensure API callers always get JSON, not HTML error pages."""
        if not (request.path or '').startswith('/api/'):
            if isinstance(err, HTTPException):
                return err
            log.exception("Unhandled page error")
            return "Internal Server Error", 500

        if isinstance(err, HTTPException):
            return {'error': err.description or 'Request failed'}, err.code

        log.exception("Unhandled API error")
        return {'error': str(err) or 'Internal server error'}, 500

    log.info("PnL application created")
    return app
