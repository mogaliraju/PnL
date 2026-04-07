"""Excel import route — parses both native PnL exports and generic spreadsheets."""
import traceback
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
    """Read project metadata from Sheet 1 (PnL)."""
    project = {'customer': '', 'location': '', 'duration_months': None,
                'proposal_date': '', 'reference': ''}
    try: project['customer']        = _s(_cv(ws, 3, 2))
    except Exception: pass
    try: project['proposal_date']   = _s(_cv(ws, 3, 10))
    except Exception: pass
    try: project['location']        = _s(_cv(ws, 4, 2))
    except Exception: pass
    try: project['reference']       = _s(_cv(ws, 4, 10))
    except Exception: pass
    try: project['duration_months'] = _n(_cv(ws, 5, 2))
    except Exception: pass
    return project


def _parse_costing_sheet(ws):
    """Read resource rows from Sheet 2 (Input Costing Calculation).
    Columns: 1=#, 2=Role, 3=Level, 4=Hours. Stop at TOTAL row or blank."""
    resources = []
    for row_idx in range(2, 1002):
        try:
            role_val  = _cv(ws, row_idx, 2)
            level_val = _cv(ws, row_idx, 3)
            hours_val = _cv(ws, row_idx, 4)
        except Exception:
            break
        if _s(role_val).upper() == 'TOTAL':
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

    is_native = (len(sheet_names) >= 2
                 and sheet_names[0] == 'PnL'
                 and sheet_names[1] == 'Input Costing Calculation')

    if is_native:
        try:
            project = _parse_pnl_sheet(wb['PnL'])
        except Exception as e:
            warnings.append(f'PnL sheet error: {e}')
        try:
            resources = _parse_costing_sheet(wb['Input Costing Calculation'])
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
