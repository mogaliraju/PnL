"""Project CRUD routes and version comparison."""
from datetime import datetime

from flask import Blueprint, request, jsonify, session
from pnl.utils.storage import (
    delete_project_record,
    list_project_versions,
    load_project_record,
    load_project_version,
    rename_project_record,
    save_project_record,
    save_project_version,
    save_working_data,
    safe_filename,
    merge_settings,
)
from pnl.utils.auth import login_required
from pnl.utils.validators import validate_payload, ValidationError
from pnl.services.pnl_service import compare_versions
from pnl.utils.logger import get_logger

bp = Blueprint('projects', __name__)
log = get_logger(__name__)


@bp.route('/api/projects', methods=['GET'])
@login_required
def list_projects():
    summary = request.args.get('summary', 'false').lower() == 'true'
    from pnl.utils.storage import list_projects as list_project_rows

    return jsonify(list_project_rows(summary=summary))


@bp.route('/api/projects', methods=['POST'])
@login_required
def save_project():
    data = request.json or {}
    try:
        validate_payload(data)
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400

    name = data.get('_meta', {}).get('name') or \
           data.get('project', {}).get('customer') or 'Untitled'
    pid  = safe_filename(name) + '_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    data['_meta'] = {
        'name':     name,
        'id':       pid,
        'saved_at': datetime.now().isoformat(timespec='seconds'),
        'saved_by': session.get('user', ''),
    }

    save_project_record(pid, data)
    _snapshot_version(pid, data)

    save_working_data(data)
    log.info(f"Project '{name}' saved as '{pid}' by '{session.get('user')}'")
    return jsonify({'status': 'ok', 'id': pid, 'name': name})


@bp.route('/api/projects/<pid>', methods=['GET'])
@login_required
def load_project(pid):
    data = load_project_record(pid)
    if data is None:
        return jsonify({'error': 'Not found'}), 404
    data = merge_settings(data)
    log.info(f"Project '{pid}' loaded by '{session.get('user')}'")
    return jsonify(data)


@bp.route('/api/projects/<pid>', methods=['PUT'])
@login_required
def update_project(pid):
    existing = load_project_record(pid)
    if existing is None:
        return jsonify({'error': 'Not found'}), 404
    data = request.json or {}
    try:
        validate_payload(data)
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400

    # Preserve original _meta (id, name, created) but update saved_at/by
    meta = existing.get('_meta', {})
    meta['saved_at'] = datetime.now().isoformat(timespec='seconds')
    meta['saved_by'] = session.get('user', '')
    data['_meta'] = meta

    save_project_record(pid, data)
    _snapshot_version(pid, data)
    save_working_data(data)
    log.info(f"Project '{pid}' updated by '{session.get('user')}'")
    return jsonify({'status': 'ok', 'id': pid, 'name': meta.get('name', pid)})


@bp.route('/api/projects/<pid>', methods=['DELETE'])
@login_required
def delete_project(pid):
    delete_project_record(pid)
    log.info(f"Project '{pid}' deleted by '{session.get('user')}'")
    return jsonify({'status': 'ok'})


@bp.route('/api/projects/<pid>/rename', methods=['POST'])
@login_required
def rename_project(pid):
    body = request.json or {}
    new_name = body.get('name', '').strip()
    new_customer = body.get('customer', '').strip()
    if not new_name:
        return jsonify({'error': 'Name required'}), 400
    if not rename_project_record(pid, new_name, new_customer):
        return jsonify({'error': 'Not found'}), 404
    log.info(f"Project '{pid}' renamed to '{new_name}' by '{session.get('user')}'")
    return jsonify({'status': 'ok'})


# ── Versions ──────────────────────────────────────────────────
@bp.route('/api/projects/<pid>/versions', methods=['GET'])
@login_required
def list_versions(pid):
    return jsonify(list_project_versions(pid))


@bp.route('/api/compare', methods=['POST'])
@login_required
def compare():
    body = request.json or {}
    pid1, vid1 = body.get('pid1'), body.get('vid1')
    pid2, vid2 = body.get('pid2'), body.get('vid2')

    v1 = _load_version_or_project(pid1, vid1)
    v2 = _load_version_or_project(pid2, vid2)

    if v1 is None:
        return jsonify({'error': f'Project/version not found: {pid1}/{vid1}'}), 404
    if v2 is None:
        return jsonify({'error': f'Project/version not found: {pid2}/{vid2}'}), 404

    result = compare_versions(v1, v2)
    return jsonify(result)


# ── Helpers ───────────────────────────────────────────────────
def _snapshot_version(pid: str, data: dict):
    """Save a timestamped snapshot under versions/<pid>/."""
    vid = datetime.now().strftime('%Y%m%d_%H%M%S')
    save_project_version(pid, vid, data)


def _load_version_or_project(pid: str, vid: str | None) -> dict | None:
    """Load a specific version snapshot, or the main project file if vid is None."""
    if vid:
        return load_project_version(pid, vid)
    return load_project_record(pid)
