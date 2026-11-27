"""Proposal generation jobs (design/PROPOSALS.md section 5).

A request stores a `queued` row and hands the work to a small in-process thread pool:
  commercials from the PnL version (engine) -> content from the model (no amounts) ->
  component diagram -> Word document -> row `ready` with the file.
Rows are added and their own status columns filled in; no other table is written.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from pnl import engine
from pnl import proposal_checks
from pnl.proposal_commercials import commercials_from_payload, default_terms, pnl_context
from pnl.utils import storage
from pnl.utils.logger import get_logger

log = get_logger(__name__)

RATE_LIMIT = (10, 60)             # 10 proposals per user per 60 minutes
STUCK_MINUTES = 15
MAX_UPLOAD = 15 * 1024 * 1024
BRANDS = ('automatonsx', 'cloud4c')
ENGAGEMENTS = ('greenfield', 'migration', 'assessment', 'governance')
DEFAULT_PEOPLE = {
    'prepared_by': {'name': 'Srikar Mogaliraju', 'designation': 'Principal Architect - Data Engineering'},
    'reviewed_by': {'automatonsx': {'name': 'Amair Soofi', 'designation': 'Principal Solution Architect'},
                    'cloud4c': {'name': 'Krishna Kumar G', 'designation': 'Head of Data & AI'}},
}

_executor = None
_executor_lock = threading.Lock()


class ProposalError(ValueError):
    """Bad input the person can fix (shown as a 400)."""


class Unavailable(RuntimeError):
    """The server can't build proposals (missing table or tools); shown as a 503."""


# ── capability checks ────────────────────────────────────────────────────

def capabilities() -> dict:
    """What this server has. Generation needs the table, Node with the docx package, and resvg."""
    out = {'table': False, 'node': None, 'docx_module': False, 'resvg': False, 'model_configured': False}
    with storage._connect() as conn:
        if storage._USE_POSTGRES:
            out['table'] = bool(storage._execute(conn, "SELECT to_regclass('public.proposal') AS t").fetchone()['t'])
    node = shutil.which('node')
    if node:
        import subprocess
        try:
            out['node'] = subprocess.run([node, '--version'], capture_output=True, text=True, timeout=10).stdout.strip()
            root = Path(__file__).resolve().parents[1]
            r = subprocess.run([node, '-e', "require.resolve('docx')"], cwd=root / 'proposals' / 'skill' / 'scripts',
                               capture_output=True, text=True, timeout=10)
            out['docx_module'] = r.returncode == 0
        except Exception:
            pass
    try:
        import resvg_py  # noqa: F401
        out['resvg'] = True
    except ImportError:
        pass
    out['model_configured'] = bool(os.environ.get('AWS_BEARER_TOKEN_BEDROCK') or os.environ.get('AWS_ACCESS_KEY_ID')
                                   or os.environ.get('AWS_PROFILE') or _demo())
    out['ready'] = all((out['table'], out['node'], out['docx_module'], out['resvg'], out['model_configured']))
    return out


_CAPS = (0.0, None)


def setup_problems() -> list[str]:
    """Plain-language list of what stops generation on this server (cached for 10 minutes)."""
    import time
    global _CAPS
    if _CAPS[1] is None or time.monotonic() - _CAPS[0] > 600:
        _CAPS = (time.monotonic(), capabilities())
    c = _CAPS[1]
    out = []
    if not c['node']:
        out.append('Node.js is not installed on the server, so the Word document cannot be built.')
    elif not c['docx_module']:
        out.append("The Word builder's package is missing. Add `npm ci --omit=dev` to the build command.")
    if not c['resvg']:
        out.append('The diagram renderer (resvg-py) is not installed.')
    if not c['model_configured']:
        out.append('No Bedrock key is set (AWS_BEARER_TOKEN_BEDROCK).')
    return out


def _require_table(conn):
    if not storage._USE_POSTGRES or not storage._execute(conn, "SELECT to_regclass('public.proposal') AS t").fetchone()['t']:
        raise Unavailable('Proposal generation needs database migration 0006.')


# ── rows ─────────────────────────────────────────────────────────────────

def _row_out(r: dict, with_content: bool = False) -> dict:
    content = json.loads(r['content']) if r.get('content') else {}
    out = {
        'id': r['id'], 'project_id': r['project_id'], 'version_no': r['version_no'], 'brand': r['brand'],
        'engagement_type': r['engagement_type'], 'status': r['status'], 'stage': r['stage'], 'error': r.get('error'),
        'filename': r.get('filename'), 'model_id': r.get('model_id'), 'input_tokens': r.get('input_tokens'),
        'output_tokens': r.get('output_tokens'), 'created_by': r['created_by'],
        'created_at': str(r['created_at']), 'finished_at': str(r['finished_at']) if r.get('finished_at') else None,
        'open_questions': content.get('open_questions') or [],
        'doc_type': (json.loads(r['intake']) if r.get('intake') else {}).get('doc_type'),
        'checks': json.loads(r['checks']) if r.get('checks') else [],
    }
    if with_content:
        out['content'] = content
        out['commercials'] = json.loads(r['commercials']) if r.get('commercials') else None
    return out


_HAS_CHECKS = None


def _has_checks() -> bool:
    """Migration 0007 adds the checks column; before it, proposals still work without checks."""
    global _HAS_CHECKS
    if _HAS_CHECKS is None:
        with storage._connect() as conn:
            _HAS_CHECKS = bool(storage._execute(conn, "SELECT 1 AS x FROM information_schema.columns WHERE table_name = 'proposal' "
                                                      "AND column_name = 'checks'").fetchone())
    return _HAS_CHECKS


def _cols() -> str:
    return _COLS + (', checks' if _has_checks() else '')


_COLS = ("id, project_id, version_id, version_no, brand, engagement_type, status, stage, intake, commercials, "
         "content, filename, model_id, input_tokens, output_tokens, error, created_by, created_at, finished_at")


def _mark_stuck(conn):
    """Jobs a deploy or restart killed never finish; show them as failed so they can be retried."""
    storage._execute(conn, f"UPDATE proposal SET status = 'failed', error = 'Stopped by a server restart. Generate it again.', "
                           f"finished_at = now() WHERE status IN ('queued', 'running') "
                           f"AND created_at < now() - interval '{STUCK_MINUTES} minutes'")


def list_for_project(pid: str) -> list[dict]:
    with storage._connect() as conn:
        _require_table(conn)
        _mark_stuck(conn)
        conn.commit()
        rows = storage._execute(conn, f"SELECT {_cols()} FROM proposal WHERE project_id = ? ORDER BY created_at DESC, id DESC",
                                (pid,)).fetchall()
    return [_row_out(r) for r in rows]


def get(proposal_id: int, with_content: bool = False) -> dict | None:
    with storage._connect() as conn:
        _require_table(conn)
        _mark_stuck(conn)
        conn.commit()
        r = storage._execute(conn, f"SELECT {_cols()} FROM proposal WHERE id = ?", (proposal_id,)).fetchone()
    return _row_out(r, with_content) if r else None


def intake_of(proposal_id: int) -> dict | None:
    """The form as it was sent, to fill the form again for a retry."""
    with storage._connect() as conn:
        _require_table(conn)
        r = storage._execute(conn, "SELECT intake, version_no FROM proposal WHERE id = ?", (proposal_id,)).fetchone()
    if not r:
        return None
    i = json.loads(r['intake'])
    i['version_no'] = r['version_no']
    return i


def download(proposal_id: int) -> tuple[bytes, str] | None:
    with storage._connect() as conn:
        _require_table(conn)
        r = storage._execute(conn, "SELECT docx, filename FROM proposal WHERE id = ? AND status = 'ready'",
                             (proposal_id,)).fetchone()
    return (bytes(r['docx']), r['filename']) if r and r['docx'] is not None else None


def _set(proposal_id: int, **fields):
    keys = list(fields)
    sets = ', '.join(f"{k} = ?" for k in keys)
    with storage._connect() as conn:
        storage._execute(conn, f"UPDATE proposal SET {sets} WHERE id = ?", (*[fields[k] for k in keys], proposal_id))
        conn.commit()


# ── input ────────────────────────────────────────────────────────────────

def extract_text(filename: str, data: bytes) -> str:
    """Plain text from an uploaded BRD or SOW. The file itself is not kept."""
    if len(data) > MAX_UPLOAD:
        raise ProposalError('That file is larger than 15 MB. Upload a smaller BRD or SOW.')
    name = (filename or '').lower()
    try:
        if name.endswith('.pdf'):
            from pypdf import PdfReader
            return '\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(data)).pages).strip()
        if name.endswith('.docx'):
            import docx
            d = docx.Document(io.BytesIO(data))
            parts = [p.text for p in d.paragraphs]
            for t in d.tables:
                for row in t.rows:
                    parts.append(' | '.join(c.text for c in row.cells))
            return '\n'.join(parts).strip()
        if name.endswith(('.txt', '.md')):
            return data.decode('utf-8', errors='replace').strip()
    except Exception as e:
        raise ProposalError(f"Couldn't read {filename}: {e}")
    raise ProposalError('Upload a PDF, Word (.docx) or text file.')


def _clean_intake(raw: dict, project: dict, version_no: int) -> dict:
    """Validate the form and fill defaults. Raises ProposalError with a readable message."""
    i = dict(raw or {})
    brand = str(i.get('brand') or '').lower()
    if brand not in BRANDS:
        raise ProposalError('Choose AutomatonsX or Cloud4C.')
    eng = str(i.get('engagement_type') or '').lower()
    if eng not in ENGAGEMENTS:
        raise ProposalError('Choose the engagement type.')
    client = str(i.get('client') or project.get('customer') or '').strip()
    if not client:
        raise ProposalError('Enter the client name.')
    i.update(brand=brand, engagement_type=eng, client=client[:120],
             client_short=str(i.get('client_short') or client.split()[0])[:60])
    i['doc_type'] = i.get('doc_type') if i.get('doc_type') in ('Technical Proposal', 'Techno-Commercial Proposal') \
        else 'Techno-Commercial Proposal'
    i['include_commercials'] = bool(i.get('include_commercials', True))
    i.setdefault('currency', 'USD')
    i['version'] = str(i.get('version') or 'V0.1')[:20]
    i['date'] = date.today().strftime('%-d %B %Y') if os.name != 'nt' else date.today().strftime('%d %B %Y')
    i.setdefault('version_comment', f'Prepared from PnL version {version_no}')
    i['sources'] = [s for s in (i.get('sources') or []) if isinstance(s, dict) and str(s.get('name') or '').strip()][:12]
    i['target_technologies'] = [str(t) for t in (i.get('target_technologies') or []) if str(t).strip()][:12]
    i['extra_sections'] = [s for s in (i.get('extra_sections') or []) if s in ('project_governance', 'risks')]
    if eng == 'migration':
        m = i.get('migration') or {}
        if not str(m.get('source_platform') or '').strip() or not str(m.get('target_platform') or '').strip():
            raise ProposalError('For a migration, enter the source and target platforms.')
    if not (str(i.get('brief') or '').strip() or str(i.get('document_text') or '').strip()):
        raise ProposalError('Write a short brief or upload the BRD or SOW.')
    for k in ('brief', 'document_text'):
        i[k] = str(i.get(k) or '')[:120_000]
    people = i.get('people') or {}
    pb = people.get('prepared_by') or {}
    rv = people.get('reviewed_by') or {}
    people['prepared_by'] = {**DEFAULT_PEOPLE['prepared_by'], **{k: v for k, v in pb.items() if v}}
    people['reviewed_by'] = {**DEFAULT_PEOPLE['reviewed_by'][brand], **{k: v for k, v in rv.items() if v}}
    people.setdefault('account_manager', {'name': project.get('account_manager') or ''})
    i['people'] = people
    corp = i.get('corporate') or {}
    corp.setdefault('company_name', 'AutomatonsX' if brand == 'automatonsx' else 'Cloud4C Services')
    if brand == 'cloud4c':
        corp.setdefault('website', 'www.cloud4c.com')
    i['corporate'] = corp
    i.pop('client_logo_path', None)            # never a server path from the browser
    return i


# ── create and run ───────────────────────────────────────────────────────

def _versions(pid: str) -> list[dict]:
    return storage.list_project_versions(pid)


def create(pid: str, version_no: int, raw_intake: dict, username: str) -> int:
    rec = storage.load_project_record(pid)
    if not rec:
        raise ProposalError('Project not found.')
    v = next((x for x in _versions(pid) if x['version_no'] == version_no), None)
    if not v:
        raise ProposalError(f'Version {version_no} of this project is not saved.')
    payload = storage.load_project_version(pid, v['vid']) or {}
    intake = _clean_intake(raw_intake, payload.get('project') or {}, version_no)
    try:
        engine.calculate(payload)
    except engine.EngineInputError:
        raise ProposalError('The margins or discount on this version are out of range. Fix them in the editor first.')

    with storage._connect() as conn:
        _require_table(conn)
        n = storage._execute(conn, "SELECT COUNT(*) AS c FROM proposal WHERE created_by = ? "
                                   f"AND created_at > now() - interval '{RATE_LIMIT[1]} minutes'", (username,)).fetchone()['c']
        if n >= RATE_LIMIT[0]:
            raise ProposalError(f'You can generate {RATE_LIMIT[0]} proposals an hour. Try again later.')
        row = storage._execute(conn, "INSERT INTO proposal(project_id, version_id, version_no, brand, engagement_type, intake, "
                                     "created_by, stage) VALUES (?, ?, ?, ?, ?, ?, ?, 'Waiting to start') RETURNING id",
                               (pid, v['vid'], version_no, intake['brand'], intake['engagement_type'],
                                json.dumps(intake), username)).fetchone()
        conn.commit()
    pid_ = row['id']
    _submit(run, pid_)
    return pid_


def _submit(fn, *args):
    if os.environ.get('PNL_PROPOSALS_INLINE'):          # tests: run in the request thread
        fn(*args)
        return
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='proposal')
    _executor.submit(fn, *args)


def run(proposal_id: int) -> None:
    """The job. Every failure ends as status 'failed' with a message the person can act on."""
    from proposals import assemble, generator
    tmp = Path(tempfile.mkdtemp(prefix='proposal-'))
    try:
        with storage._connect() as conn:
            r = storage._execute(conn, "SELECT project_id, version_id, version_no, intake FROM proposal WHERE id = ?",
                                 (proposal_id,)).fetchone()
        intake = json.loads(r['intake'])
        _set(proposal_id, status='running', stage='Pricing from the PnL version')
        payload = storage.load_project_version(r['project_id'], r['version_id']) or {}
        com = commercials_from_payload(
            payload, intake['brand'], project_name=intake['client'], version_no=r['version_no'],
            client_short=intake['client_short'], overrides=intake.get('commercial_terms') or {})
        _set(proposal_id, commercials=json.dumps(com), stage='Writing the content')

        if _demo() and generator._client is None:
            generator.set_client(_DemoBedrock())
        content, usage = generator.generate_content(intake, pnl_context(com))
        _set(proposal_id, content=json.dumps(content), model_id=usage.get('model_id'),
             input_tokens=usage['inputTokens'], output_tokens=usage['outputTokens'], stage='Drawing the architecture')

        png = assemble.render_diagram(content['component_diagram'], tmp / 'component_arch.png')
        _set(proposal_id, stage='Building the document')
        spec = assemble.build_spec(intake, content, com, png)
        safe = ''.join(ch if ch.isalnum() else '_' for ch in intake['client']).strip('_') or 'Client'
        filename = f"{safe}_Proposal_{intake['version']}.docx"
        out = assemble.render_docx(spec, tmp / filename)
        _set(proposal_id, stage='Checking the proposal')
        checks = proposal_checks.run_checks(intake, content, com)
        extra = {'checks': json.dumps(checks)} if _has_checks() else {}
        _set(proposal_id, docx=out.read_bytes(), filename=filename, status='ready', stage='Ready', finished_at=_now(), **extra)
    except Exception as e:                                   # noqa: BLE001 - everything ends in a readable row
        log.exception(f'Proposal {proposal_id} failed')
        _set(proposal_id, status='failed', stage='Failed', error=_friendly(e), finished_at=_now())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _demo() -> bool:
    from pnl import config
    return bool(os.environ.get('PNL_PROPOSALS_FAKE')) and not config.IS_PRODUCTION


class _DemoBedrock:
    """Local demo only (PNL_PROPOSALS_FAKE=1, refused in production): returns the bundled sample content."""
    def converse(self, **kw):
        import time
        time.sleep(2)
        brand = 'cloud4c' if 'Cloud4C' in kw['system'][0]['text'][:400] else 'automatonsx'
        content = json.loads((Path(__file__).resolve().parents[1] / 'proposals' / 'samples' / brand / 'content.json').read_text())
        content['open_questions'] = ['Demo mode: this is the sample content, not written for this client.'] + content.get('open_questions', [])
        return {'output': {'message': {'role': 'assistant', 'content': [{'toolUse': {
                    'toolUseId': 'demo', 'name': 'submit_proposal_content', 'input': content}}]}},
                'stopReason': 'tool_use', 'usage': {'inputTokens': 0, 'outputTokens': 0}}


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _friendly(e: Exception) -> str:
    msg = str(e)
    name = type(e).__name__
    if 'Throttl' in name or 'Throttl' in msg:
        return 'The model is busy right now. Try again in a few minutes.'
    if 'AccessDenied' in name or 'AccessDenied' in msg or 'not authorized' in msg:
        return "The proposal model isn't enabled for this AWS account. Ask an admin to enable Claude Opus 4.6 in Bedrock."
    if 'build_proposal.js' in msg or 'node' in msg.lower() and 'not found' in msg.lower():
        return "The Word builder isn't available on this server. Ask an admin to check the proposal setup."
    if isinstance(e, engine.EngineInputError):
        return 'The margins or discount on this version are out of range. Fix them in the editor first.'
    return f"Generation failed: {msg[:300]}"


def defaults_for(pid: str) -> dict:
    """Prefill for the Generate dialog."""
    rec = storage.load_project_record(pid) or {}
    project = rec.get('project') or {}
    return {
        'client': project.get('customer') or '',
        'industry': project.get('industry') or '',
        'region': project.get('location') or '',
        'brief': project.get('project_description') or '',
        'versions': [{'version_no': v['version_no'], 'label': v.get('label') or '', 'saved_at': v['saved_at']}
                     for v in _versions(pid)],
        'people': {**DEFAULT_PEOPLE, 'account_manager': {'name': project.get('account_manager') or ''}},
        'terms': {b: default_terms(b, project.get('customer') or 'the client') for b in BRANDS},
    }
