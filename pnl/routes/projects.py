"""Project CRUD routes and version comparison."""
import json
import os
from datetime import datetime

from flask import Blueprint, request, jsonify, session
from pnl.config import PROJECTS_DIR, VERSIONS_DIR
from pnl.utils.storage import load_data, save_data, load_settings, safe_filename, merge_settings
from pnl.utils.auth import login_required
from pnl.utils.validators import validate_payload, ValidationError
from pnl.services.pnl_service import compare_versions, compute_costs
from pnl.utils.logger import get_logger

bp = Blueprint('projects', __name__)
log = get_logger(__name__)


@bp.route('/api/projects', methods=['GET'])
@login_required
def list_projects():
    summary = request.args.get('summary', 'false').lower() == 'true'
    projects = []
    for fname in sorted(os.listdir(PROJECTS_DIR), reverse=True):
        if fname.endswith('.json'):
            path = os.path.join(PROJECTS_DIR, fname)
            try:
                with open(path) as f:
                    d = json.load(f)
                meta = d.get('_meta', {})
                proj = d.get('project', {})
                entry = {
                    'id':           fname[:-5],
                    'name':         meta.get('name', fname[:-5]),
                    'customer':     proj.get('customer', ''),
                    'location':     proj.get('location', ''),
                    'duration':     proj.get('duration_months', ''),
                    'proposal_date':proj.get('proposal_date', ''),
                    'saved_at':     meta.get('saved_at', ''),
                    'saved_by':     meta.get('saved_by', ''),
                }
                if summary:
                    rate_map = {r['level']: r['rate'] for r in d.get('rate_card', [])}
                    target_margin = float(d.get('target_margin', 0.40))
                    costs = compute_costs(d.get('resources', []), rate_map, target_margin)
                    entry['costs'] = costs
                projects.append(entry)
            except Exception:
                pass
    return jsonify(projects)


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

    path = os.path.join(PROJECTS_DIR, pid + '.json')
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

    # Also snapshot as a version for comparison
    _snapshot_version(pid, data)

    save_data(data)
    log.info(f"Project '{name}' saved as '{pid}' by '{session.get('user')}'")
    return jsonify({'status': 'ok', 'id': pid, 'name': name})


@bp.route('/api/projects/<pid>', methods=['GET'])
@login_required
def load_project(pid):
    path = os.path.join(PROJECTS_DIR, pid + '.json')
    if not os.path.exists(path):
        return jsonify({'error': 'Not found'}), 404
    with open(path) as f:
        data = json.load(f)
    data = merge_settings(data)
    save_data(data)
    log.info(f"Project '{pid}' loaded by '{session.get('user')}'")
    return jsonify(data)


@bp.route('/api/projects/<pid>', methods=['PUT'])
@login_required
def update_project(pid):
    path = os.path.join(PROJECTS_DIR, pid + '.json')
    if not os.path.exists(path):
        return jsonify({'error': 'Not found'}), 404
    data = request.json or {}
    try:
        validate_payload(data)
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400

    # Preserve original _meta (id, name, created) but update saved_at/by
    with open(path) as f:
        existing = json.load(f)
    meta = existing.get('_meta', {})
    meta['saved_at'] = datetime.now().isoformat(timespec='seconds')
    meta['saved_by'] = session.get('user', '')
    data['_meta'] = meta

    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

    _snapshot_version(pid, data)
    save_data(data)
    log.info(f"Project '{pid}' updated by '{session.get('user')}'")
    return jsonify({'status': 'ok', 'id': pid, 'name': meta.get('name', pid)})


@bp.route('/api/projects/<pid>', methods=['DELETE'])
@login_required
def delete_project(pid):
    path = os.path.join(PROJECTS_DIR, pid + '.json')
    if os.path.exists(path):
        os.remove(path)
    log.info(f"Project '{pid}' deleted by '{session.get('user')}'")
    return jsonify({'status': 'ok'})


@bp.route('/api/projects/<pid>/rename', methods=['POST'])
@login_required
def rename_project(pid):
    path = os.path.join(PROJECTS_DIR, pid + '.json')
    if not os.path.exists(path):
        return jsonify({'error': 'Not found'}), 404
    body = request.json or {}
    new_name = body.get('name', '').strip()
    new_customer = body.get('customer', '').strip()
    if not new_name:
        return jsonify({'error': 'Name required'}), 400
    with open(path) as f:
        data = json.load(f)
    data.setdefault('_meta', {})['name'] = new_name
    if new_customer:
        data.setdefault('project', {})['customer'] = new_customer
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    log.info(f"Project '{pid}' renamed to '{new_name}' by '{session.get('user')}'")
    return jsonify({'status': 'ok'})


# ── Versions ──────────────────────────────────────────────────
@bp.route('/api/projects/<pid>/versions', methods=['GET'])
@login_required
def list_versions(pid):
    versions = []
    vdir = os.path.join(VERSIONS_DIR, pid)
    if not os.path.exists(vdir):
        return jsonify([])
    for fname in sorted(os.listdir(vdir)):
        if fname.endswith('.json'):
            path = os.path.join(vdir, fname)
            try:
                with open(path) as f:
                    d = json.load(f)
                meta = d.get('_meta', {})
                versions.append({
                    'vid':      fname[:-5],
                    'saved_at': meta.get('saved_at', ''),
                    'saved_by': meta.get('saved_by', ''),
                })
            except Exception:
                pass
    return jsonify(versions)


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
    vdir = os.path.join(VERSIONS_DIR, pid)
    os.makedirs(vdir, exist_ok=True)
    vid = datetime.now().strftime('%Y%m%d_%H%M%S')
    with open(os.path.join(vdir, vid + '.json'), 'w') as f:
        json.dump(data, f, indent=2)


def _load_version_or_project(pid: str, vid: str | None) -> dict | None:
    """Load a specific version snapshot, or the main project file if vid is None."""
    if vid:
        path = os.path.join(VERSIONS_DIR, pid, vid + '.json')
    else:
        path = os.path.join(PROJECTS_DIR, pid + '.json')
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)
