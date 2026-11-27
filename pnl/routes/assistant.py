"""PnL assistant API (DESIGN.md 9.2, 9.3): streaming chat, history, one-time export links."""
import json
from datetime import datetime, timezone
from io import BytesIO

from flask import Blueprint, Response, jsonify, request, send_file, session, stream_with_context

from pnl import engine
from pnl.assistant import agent, tools
from pnl.services.excel_service import build_workbook
from pnl.utils import storage
from pnl.utils.auth import login_required
from pnl.utils.logger import get_logger

bp = Blueprint('assistant', __name__)
log = get_logger(__name__)


def _ready():
    try:
        agent._require_tables()
        agent.get_client()
        return None
    except agent.AssistantUnavailable as e:
        return str(e)


@bp.route('/api/assistant/session', methods=['GET'])
@login_required
def get_session():
    problem = _ready()
    if problem:
        return jsonify({'available': False, 'reason': problem, 'messages': []})
    sid = agent.current_session(session['user'], create=False)
    return jsonify({'available': True, 'id': sid, 'model': agent.model_id(),
                    'messages': agent.history(sid, session['user']) if sid else []})


@bp.route('/api/assistant/session', methods=['POST'])
@login_required
def start_session():
    problem = _ready()
    if problem:
        return jsonify({'error': problem}), 503
    return jsonify({'id': agent.new_session(session['user'])})


@bp.route('/api/assistant/chat', methods=['POST'])
@login_required
def chat():
    problem = _ready()
    if problem:
        return jsonify({'error': problem}), 503
    body = request.get_json(silent=True) or {}
    user = session['user']
    try:
        agent.check_rate_limit(user)
    except agent.RateLimited as e:
        return jsonify({'error': str(e)}), 429
    context = body.get('context') if isinstance(body.get('context'), dict) else None

    def events():
        try:
            for ev in agent.chat(user, body.get('message', ''), context, body.get('session_id')):
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        except (agent.AssistantUnavailable, agent.RateLimited) as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        except Exception:
            log.exception('Assistant chat failed')
            yield f"data: {json.dumps({'type': 'error', 'message': 'Something went wrong. Try again.'})}\n\n"

    return Response(stream_with_context(events()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@bp.route('/api/exports/<token>', methods=['GET'])
@login_required
def download(token):
    with storage._connect() as conn:
        row = storage._execute(conn, "SELECT * FROM export_token WHERE token = ?", (token,)).fetchone() \
            if storage._USE_POSTGRES else None
    if not row or row['username'] != session['user']:
        return jsonify({'error': 'That download link is not valid.'}), 404
    if row['expires_at'] < datetime.now(timezone.utc):
        return jsonify({'error': 'That download link has expired. Ask the assistant for a new one.'}), 410
    payload = (storage.load_project_version(row['project_id'], row['version_id']) if row['version_id']
               else storage.load_project_record(row['project_id']))
    if payload is None:
        return jsonify({'error': 'That project or version no longer exists.'}), 404
    overrides = json.loads(row['overrides'] or '{}')
    if overrides:
        with tools._ro() as ro:
            payload = tools.apply_overrides(ro, payload, overrides)
    try:
        costs = engine.legacy_costs_dict(engine.calculate(payload))
    except engine.EngineInputError as e:
        return jsonify({'error': f'The scenario levers are out of range: {e}'}), 400
    buf = BytesIO()
    build_workbook(payload, costs).save(buf)
    buf.seek(0)
    log.info(f"Assistant export '{row['filename']}' downloaded by '{session['user']}'")
    return send_file(buf, as_attachment=True, download_name=row['filename'],
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@bp.route('/api/projects/<pid>/scenario', methods=['POST'])
@login_required
def scenario_snapshot(pid):
    """A project's latest saved state with assistant scenario overrides applied, for the editor
    to load as unsaved changes. Nothing is saved here."""
    payload = storage.load_project_record(pid)
    if payload is None:
        return jsonify({'error': 'That project no longer exists.'}), 404
    overrides = (request.get_json(silent=True) or {}).get('overrides') or {}
    try:
        with tools._ro() as ro:
            payload = tools.apply_overrides(ro, payload, overrides)
    except tools.ToolError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(storage.merge_settings(payload))
