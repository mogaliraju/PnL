"""Project CRUD routes and version comparison."""
import json
from datetime import datetime

from flask import Blueprint, request, jsonify, session
from pnl.utils.storage import (
    FeatureUnavailable,
    archive_project_record,
    get_user_pref,
    project_archive_info,
    restore_project_record,
    set_user_pref,
    label_project_version,
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
    archived = request.args.get('archived', 'false').lower() == 'true'
    from pnl.utils.storage import list_projects as list_project_rows

    return jsonify(list_project_rows(summary=summary, archived=archived))


# ── Folders ─────────────────────────────────────────────────
# Must be registered BEFORE the <pid> route to avoid being matched as a pid
@bp.route('/api/projects/folders', methods=['GET'])
@login_required
def list_folders():
    from pnl.utils.storage import list_projects as _list
    projects = _list(summary=False)
    folders = sorted({p['folder'] for p in projects if p.get('folder')})
    return jsonify(folders)


@bp.route('/api/projects', methods=['POST'])
@login_required
def save_project():
    data = request.json or {}
    try:
        validate_payload(data)
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400

    incoming_meta = data.get('_meta', {})
    name = incoming_meta.get('name') or \
           data.get('project', {}).get('customer') or 'Untitled'
    pid  = safe_filename(name) + '_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    data['_meta'] = {
        'name':     name,
        'id':       pid,
        'saved_at': datetime.now().isoformat(timespec='seconds'),
        'saved_by': session.get('user', ''),
        'folder':   incoming_meta.get('folder', ''),
    }

    save_project_record(pid, data)
    vid = _snapshot_version(pid, data)

    save_working_data(data)
    log.info(f"Project '{name}' saved as '{pid}' by '{session.get('user')}'")
    return jsonify({'status': 'ok', 'id': pid, 'name': name, 'vid': vid, 'saved_at': data['_meta']['saved_at']})


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
    # The workspace edits the project name in Details
    incoming_name = str((data.get('_meta') or {}).get('name') or '').strip()
    if incoming_name:
        meta['name'] = incoming_name[:200]
    # Allow folder to be updated from incoming data
    incoming_folder = (data.get('_meta') or {}).get('folder', '')
    if incoming_folder or 'folder' in (data.get('_meta') or {}):
        meta['folder'] = incoming_folder
    data['_meta'] = meta

    save_project_record(pid, data)
    vid = _snapshot_version(pid, data)
    save_working_data(data)
    log.info(f"Project '{pid}' updated by '{session.get('user')}'")
    return jsonify({'status': 'ok', 'id': pid, 'name': meta.get('name', pid), 'vid': vid, 'saved_at': meta['saved_at']})


def _archive(pid):
    if load_project_record(pid) is None:
        return jsonify({'error': 'That project no longer exists.'}), 404
    try:
        changed = archive_project_record(pid, session.get('user', ''))
    except FeatureUnavailable as e:
        return jsonify({'error': str(e)}), 503
    log.info(f"Project '{pid}' archived by '{session.get('user')}'")
    return jsonify({'status': 'archived' if changed else 'already archived', 'id': pid})


@bp.route('/api/projects/<pid>/archive', methods=['POST'])
@login_required
def archive_project(pid):
    return _archive(pid)


@bp.route('/api/projects/<pid>', methods=['DELETE'])
@login_required
def delete_project(pid):
    # Projects are never deleted (DESIGN.md 2.3.1): an old client's delete archives instead.
    return _archive(pid)


@bp.route('/api/projects/<pid>/restore', methods=['POST'])
@login_required
def restore_project(pid):
    info = project_archive_info(pid)
    if info is None:
        return jsonify({'error': 'That project is not in the archive.'}), 404
    # Admins can restore anything; anyone can undo their own archive.
    if session.get('role') != 'admin' and info['archived_by'] != session.get('user'):
        return jsonify({'error': 'Only an admin can restore a project someone else archived.'}), 403
    restore_project_record(pid)
    log.info(f"Project '{pid}' restored by '{session.get('user')}'")
    return jsonify({'status': 'restored', 'id': pid})


# ── Per-user preferences (list columns, filters, saved view) ─────────────────
PREF_KEYS = {'projects_list'}


@bp.route('/api/prefs/<key>', methods=['GET'])
@login_required
def get_pref(key):
    if key not in PREF_KEYS:
        return jsonify({'error': 'Unknown preference.'}), 404
    return jsonify(get_user_pref(session['user'], key, {}))


@bp.route('/api/prefs/<key>', methods=['PUT'])
@login_required
def put_pref(key):
    if key not in PREF_KEYS:
        return jsonify({'error': 'Unknown preference.'}), 404
    value = request.get_json(silent=True)
    if not isinstance(value, dict) or len(json.dumps(value)) > 20000:
        return jsonify({'error': 'Preferences must be a JSON object under 20 KB.'}), 400
    try:
        set_user_pref(session['user'], key, value)
    except FeatureUnavailable as e:
        return jsonify({'error': str(e)}), 503
    return jsonify({'status': 'ok'})


@bp.route('/api/projects/<pid>/folder', methods=['POST'])
@login_required
def set_project_folder(pid):
    body = request.json or {}
    folder = body.get('folder', '').strip()
    data = load_project_record(pid)
    if data is None:
        return jsonify({'error': 'Not found'}), 404
    meta = data.get('_meta', {})
    meta['folder'] = folder
    data['_meta'] = meta
    save_project_record(pid, data)
    log.info(f"Project '{pid}' folder set to '{folder}' by '{session.get('user')}'")
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


@bp.route('/api/projects/<pid>/versions/<vid>', methods=['GET'])
@login_required
def get_version(pid, vid):
    data = load_project_version(pid, vid)
    if data is None:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(data)


@bp.route('/api/projects/<pid>/versions/<vid>/label', methods=['POST'])
@login_required
def set_version_label(pid, vid):
    body = request.json or {}
    lbl = body.get('label', '').strip()
    if not label_project_version(pid, vid, lbl):
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'status': 'ok'})


@bp.route('/api/projects/<pid>/versions/<vid>', methods=['DELETE'])
@login_required
def remove_version(pid, vid):
    # Versions are never deleted (DESIGN.md 2.3.2).
    return jsonify({'error': 'Saved versions are kept permanently and cannot be deleted.'}), 405


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
    return save_project_version(pid, vid, data)


def _load_version_or_project(pid: str, vid: str | None) -> dict | None:
    """Load a specific version snapshot, or the main project file if vid is None."""
    if vid:
        return load_project_version(pid, vid)
    return load_project_record(pid)
