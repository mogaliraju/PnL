"""Rate cards and roles API (DESIGN.md 8.4). Reading needs sign-in; changes need an admin."""
from flask import Blueprint, jsonify, request, session

from pnl import rates
from pnl.rates import RateCardError
from pnl.utils.auth import admin_required, login_required
from pnl.utils.logger import get_logger

bp = Blueprint('rates', __name__)
log = get_logger(__name__)


@bp.errorhandler(RateCardError)
def _rate_error(e):
    return jsonify({'error': str(e)}), e.status


def _body() -> dict:
    b = request.get_json(silent=True)
    return b if isinstance(b, dict) else {}


@bp.route('/api/rate-cards', methods=['GET'])
@login_required
def list_cards():
    return jsonify(rates.list_cards())


@bp.route('/api/rate-cards/<int:version>', methods=['GET'])
@login_required
def get_card(version):
    return jsonify(rates.get_matrix(version))


@bp.route('/api/rate-cards/published', methods=['GET'])
@login_required
def get_published():
    return jsonify(rates.get_matrix(None))


@bp.route('/api/rate-cards/draft', methods=['POST'])
@login_required
@admin_required
def create_draft():
    out = rates.create_draft(session['user'], _body().get('note', ''))
    log.info(f"Rate card draft v{out['card']['version']} created by '{session['user']}'")
    return jsonify(out), 201


@bp.route('/api/rate-cards/<int:version>/rates', methods=['PUT'])
@login_required
@admin_required
def put_rates(version):
    b = _body()
    return jsonify(rates.set_rates(version, b.get('rates', []), b.get('note')))


@bp.route('/api/rate-cards/<int:version>/publish', methods=['POST'])
@login_required
@admin_required
def publish(version):
    out = rates.publish(version, _body().get('effective_from'), session['user'])
    log.info(f"Rate card v{version} published by '{session['user']}' ({out['changes']} rates changed)")
    return jsonify(out)


@bp.route('/api/rate-cards/diff', methods=['GET'])
@login_required
def diff():
    try:
        a, b = int(request.args['from']), int(request.args['to'])
    except (KeyError, ValueError):
        return jsonify({'error': 'Pass from and to rate card versions.'}), 400
    return jsonify(rates.diff(a, b, request.args.get('project_id')))


@bp.route('/api/roles', methods=['GET'])
@login_required
def list_roles():
    return jsonify(rates.list_roles())


@bp.route('/api/roles', methods=['POST'])
@login_required
@admin_required
def add_role():
    b = _body()
    try:
        cid = int(b.get('category_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Pick a category.'}), 400
    lvl = b.get('default_level_id')
    return jsonify(rates.add_role(cid, b.get('name', ''), int(lvl) if lvl else None)), 201


@bp.route('/api/roles/<int:role_id>', methods=['PATCH'])
@login_required
@admin_required
def patch_role(role_id):
    b = _body()
    kwargs = {}
    if 'name' in b:
        kwargs['name'] = str(b['name'])
    if 'default_level_id' in b:
        kwargs['default_level_id'] = int(b['default_level_id']) if b['default_level_id'] else None
    if 'active' in b:
        kwargs['active'] = bool(b['active'])
    rates.update_role(role_id, **kwargs)
    return jsonify({'status': 'ok'})


@bp.route('/api/role-categories', methods=['GET'])
@login_required
def list_categories():
    return jsonify(rates.list_roles()['categories'])


@bp.route('/api/role-categories', methods=['POST'])
@login_required
@admin_required
def add_category():
    return jsonify(rates.add_category(_body().get('name', ''))), 201


@bp.route('/api/role-categories/<int:cid>', methods=['PATCH'])
@login_required
@admin_required
def patch_category(cid):
    b = _body()
    rates.update_category(cid, name=b.get('name'), active=b.get('active') if 'active' in b else None)
    return jsonify({'status': 'ok'})
