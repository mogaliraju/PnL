"""Excel import route — parses both native PnL exports and generic spreadsheets."""
import re
import traceback
from collections import Counter
from io import BytesIO

import openpyxl
from flask import Blueprint, request, jsonify, session

from pnl.utils.auth import login_required
from pnl.utils.logger import get_logger

bp = Blueprint('import_excel', __name__)
log = get_logger(__name__)


def _cv(ws, row, col):
    try:
        return ws.cell(row=row, column=col).value
    except Exception:
        return None


def _s(val):
    return str(val).strip() if val is not None else ''


def _n(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    try:
        f = float(str(val).strip())
        return int(f) if f == int(f) else f
    except Exception:
        return None


def _parse_pnl_sheet(ws):
    """Read project metadata from Sheet 1 (PnL).
    Handles both native app export format and legacy company Excel format."""
    import datetime as _dt
    project = {'customer': '', 'location': '', 'duration_months': None,
                'proposal_date': '', 'reference': ''}
    try: project['customer'] = _s(_cv(ws, 3, 2))
    except Exception: pass

    # Proposal date: native format puts it at row 3 col 10;
    # legacy format puts a datetime at row 5 col 2.
    try:
        v = _cv(ws, 3, 10)
        if v:
            project['proposal_date'] = _s(v)
        else:
            v2 = _cv(ws, 5, 2)
            if isinstance(v2, _dt.datetime):
                project['proposal_date'] = v2.strftime('%Y-%m-%d')
    except Exception: pass

    try: project['location'] = _s(_cv(ws, 4, 2))
    except Exception: pass
    try: project['reference'] = _s(_cv(ws, 4, 10))
    except Exception: pass

    # Duration: native format puts number at row 5 col 2;
    # legacy format has a datetime there — skip it, try row 8 col 6.
    try:
        v = _cv(ws, 5, 2)
        if isinstance(v, _dt.datetime):
            project['duration_months'] = _n(_cv(ws, 8, 6))
        else:
            project['duration_months'] = _n(v)
    except Exception: pass

    return project


_LEVEL_RE = re.compile(r'^L\d+$', re.I)


def _parse_costing_sheet(ws):
    """Read resource rows from the costing sheet using three strategies in order:
    1. Header keyword scan (looks for 'role', 'level', 'hours' in first 10 rows).
    2. Pattern detection: find adjacent column triplet (text, L\\d+_level, positive_number)
       appearing in at least 2 consecutive rows — handles non-standard layouts.
    3. Fixed fallback: Role=col2, Level=col3, Hours=col4 (native app export positions)."""
    max_col = min(ws.max_column or 25, 30)

    # --- Strategy 1: header keyword scan ---
    headers = {}
    header_row = None
    for hr in range(1, 11):
        row_h = {}
        for col in range(1, max_col + 1):
            h = _s(_cv(ws, hr, col)).lower()
            if not h:
                continue
            if any(k in h for k in ('role', 'resource', 'position', 'title')) and 'role' not in row_h:
                row_h['role'] = col
            elif any(k in h for k in ('level', 'grade', 'band', 'seniority')) and 'level' not in row_h:
                row_h['level'] = col
            elif any(k in h for k in ('hour', 'hrs', 'days')) and 'hours' not in row_h:
                row_h['hours'] = col
        if 'role' in row_h and 'hours' in row_h:
            headers = row_h
            header_row = hr
            break

    # --- Strategy 2: pattern detection (text, L\d+, positive_number) ---
    if header_row is None:
        triplets = []
        for r in range(1, 80):
            for c in range(1, max_col - 1):
                v_role  = _cv(ws, r, c)
                v_level = _cv(ws, r, c + 1)
                v_hours = _cv(ws, r, c + 2)
                if (isinstance(v_role, str) and v_role.strip()
                        and not _LEVEL_RE.match(v_role.strip())
                        and isinstance(v_level, str) and _LEVEL_RE.match(v_level.strip())
                        and isinstance(v_hours, (int, float)) and v_hours > 0):
                    triplets.append((r, c, c + 1, c + 2))
        if triplets:
            col_counts = Counter((rc, lc, hc) for _, rc, lc, hc in triplets)
            (role_col, level_col, hours_col), count = col_counts.most_common(1)[0]
            if count >= 2:
                headers = {'role': role_col, 'level': level_col, 'hours': hours_col}
                # header_row = one before the first matching data row
                header_row = min(r for r, rc, lc, hc in triplets
                                 if rc == role_col and lc == level_col and hc == hours_col) - 1

    # --- Strategy 3: fixed native positions ---
    if header_row is None:
        headers = {'role': 2, 'level': 3, 'hours': 4}
        header_row = 1

    resources = []
    for row_idx in range(header_row + 1, 1002):
        try:
            role_val  = _cv(ws, row_idx, headers['role'])
            level_val = _cv(ws, row_idx, headers.get('level')) if 'level' in headers else None
            hours_val = _cv(ws, row_idx, headers.get('hours')) if 'hours' in headers else None
        except Exception:
            break
        if _s(role_val).upper() in ('TOTAL', 'INPUT COST (USD)', 'SELL COST (USD)'):
            break
        if role_val is None and level_val is None and hours_val is None:
            break
        role = _s(role_val)
        if not role:
            continue
        resources.append({'role': role, 'level': _s(level_val), 'hours': _n(hours_val) or 0})
    return resources


def _parse_generic_sheet(ws):
    """Fallback: scan first sheet headers for role/level/hours columns."""
    resources = []
    headers = {}
    max_col = ws.max_column or 20
    for col in range(1, max_col + 1):
        h = _s(_cv(ws, 1, col)).lower()
        if not h:
            continue
        if any(k in h for k in ('role', 'position', 'title', 'name')) and 'role' not in headers:
            headers['role'] = col
        elif any(k in h for k in ('level', 'grade', 'band', 'seniority')) and 'level' not in headers:
            headers['level'] = col
        elif any(k in h for k in ('hour', 'hrs', 'day')) and 'hours' not in headers:
            headers['hours'] = col
    if 'role' not in headers:
        return resources
    for row_idx in range(2, 1002):
        role_val  = _cv(ws, row_idx, headers['role'])
        level_val = _cv(ws, row_idx, headers.get('level', 0)) if 'level' in headers else None
        hours_val = _cv(ws, row_idx, headers.get('hours', 0)) if 'hours' in headers else None
        if role_val is None and level_val is None and hours_val is None:
            break
        role = _s(role_val)
        if not role:
            continue
        resources.append({'role': role, 'level': _s(level_val), 'hours': _n(hours_val) or 0})
    return resources


@bp.route('/api/import-excel', methods=['POST'])
@login_required
def import_excel():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    f = request.files['file']
    if not f or not f.filename:
        return jsonify({'error': 'No file selected'}), 400
    if not f.filename.lower().endswith(('.xlsx', '.xlsm', '.xltx', '.xltm')):
        return jsonify({'error': 'File must be an Excel workbook (.xlsx)'}), 400

    try:
        wb = openpyxl.load_workbook(BytesIO(f.read()), read_only=True, data_only=True)
    except Exception as e:
        return jsonify({'error': f'Cannot open file: {e}'}), 400

    sheet_names = wb.sheetnames
    project, resources, warnings = {}, [], []

    _sn_lower = [s.lower() for s in sheet_names]
    _pnl_sheet = next((sheet_names[i] for i, s in enumerate(_sn_lower) if s == 'pnl'), None)
    _cost_sheet = next((sheet_names[i] for i, s in enumerate(_sn_lower)
                        if 'costing' in s or 'input cost' in s), None)
    is_native = bool(_pnl_sheet and _cost_sheet)

    if is_native:
        try:
            project = _parse_pnl_sheet(wb[_pnl_sheet])
        except Exception as e:
            warnings.append(f'PnL sheet error: {e}')
        try:
            resources = _parse_costing_sheet(wb[_cost_sheet])
        except Exception as e:
            warnings.append(f'Costing sheet error: {e}')
    else:
        warnings.append('Not a native PnL export — attempting generic extraction.')
        try:
            resources = _parse_generic_sheet(wb[sheet_names[0]])
        except Exception as e:
            warnings.append(f'Generic extraction failed: {e}')

    wb.close()

    if not project.get('customer') and not resources:
        return jsonify({'error': 'Could not extract any data from the file.',
                        'warnings': warnings}), 400

    log.info(f"import-excel: '{f.filename}' by '{session.get('user')}' "
             f"native={is_native} resources={len(resources)}")

    resp = {'project': project, 'resources': resources}
    if warnings:
        resp['warnings'] = warnings
    return jsonify(resp), 200
