"""Proposal generation API (design/PROPOSALS.md 5.2)."""
import json
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file, session

from pnl import proposals_service as svc
from pnl.utils import storage
from pnl.utils.auth import admin_required, login_required

bp = Blueprint('proposals', __name__)


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw), None
    except svc.ProposalError as e:
        return None, (jsonify({'error': str(e)}), 400)
    except svc.Unavailable as e:
        return None, (jsonify({'error': str(e)}), 503)


@bp.route('/api/projects/<pid>/proposals', methods=['GET'])
@login_required
def list_proposals(pid):
    rows, err = _guard(svc.list_for_project, pid)
    return err or jsonify({'proposals': rows, 'setup_problems': svc.setup_problems()})


@bp.route('/api/projects/<pid>/proposals/defaults', methods=['GET'])
@login_required
def proposal_defaults(pid):
    if not storage.load_project_record(pid):
        return jsonify({'error': 'Project not found.'}), 404
    return jsonify(svc.defaults_for(pid))


@bp.route('/api/projects/<pid>/versions/<int:version_no>/proposals', methods=['POST'])
@login_required
def create_proposal(pid, version_no):
    """multipart: `intake` (JSON text) and an optional `document` (BRD or SOW). Plain JSON also works."""
    if request.files or request.form:
        try:
            intake = json.loads(request.form.get('intake') or '{}')
        except ValueError:
            return jsonify({'error': 'The form data could not be read.'}), 400
        f = request.files.get('document')
        if f and f.filename:
            text, err = _guard(svc.extract_text, f.filename, f.read())
            if err:
                return err
            intake['document_text'] = text
            intake['document_name'] = f.filename
    else:
        intake = request.get_json(silent=True) or {}
    new_id, err = _guard(svc.create, pid, version_no, intake, session['user'])
    return err or (jsonify({'proposal_id': new_id}), 202)


@bp.route('/api/proposals/<int:proposal_id>', methods=['GET'])
@login_required
def get_proposal(proposal_id):
    row, err = _guard(svc.get, proposal_id, request.args.get('content') == '1')
    if err:
        return err
    return jsonify(row) if row else (jsonify({'error': 'Proposal not found.'}), 404)


@bp.route('/api/proposals/<int:proposal_id>/intake', methods=['GET'])
@login_required
def proposal_intake(proposal_id):
    got, err = _guard(svc.intake_of, proposal_id)
    if err:
        return err
    return jsonify(got) if got else (jsonify({'error': 'Proposal not found.'}), 404)


@bp.route('/api/proposals/<int:proposal_id>/download', methods=['GET'])
@login_required
def download_proposal(proposal_id):
    got, err = _guard(svc.download, proposal_id)
    if err:
        return err
    if not got:
        return jsonify({'error': 'That proposal is not ready.'}), 404
    data, filename = got
    return send_file(BytesIO(data), as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')


@bp.route('/api/proposals/capabilities', methods=['GET'])
@login_required
@admin_required
def proposal_capabilities():
    return jsonify(svc.capabilities())
