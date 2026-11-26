import uuid
"""Excel export route."""
import traceback
from datetime import datetime
from io import BytesIO

from flask import Blueprint, request, jsonify, send_file, session
from pnl.utils.auth import login_required
from pnl.utils.validators import validate_payload, ValidationError
from pnl import engine
from pnl.services.excel_service import build_workbook
from pnl.utils.logger import get_logger

bp = Blueprint('export', __name__)
log = get_logger(__name__)


def _safe_name(name) -> str:
    """File name from the Export dialog: no path separators or reserved characters."""
    cleaned = ''.join(' ' if c in '\\/:*?"<>|' or ord(c) < 32 else c for c in str(name or ''))
    return ' '.join(cleaned.split())[:120].strip(' .')


@bp.route('/api/export', methods=['POST'])
@login_required
def export_excel():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data received'}), 400

        try:
            validate_payload(data)
        except ValidationError as e:
            return jsonify({'error': str(e)}), 400

        # Same engine as every screen, in the project's own calculation mode
        try:
            costs = engine.legacy_costs_dict(engine.calculate(data))
        except engine.EngineInputError as e:
            return jsonify({'error': f'Fix the levers before exporting: {e}'}), 400

        wb  = build_workbook(data, costs)
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)

        customer     = data.get('project', {}).get('customer', 'PnL') or 'PnL'
        safe_cust    = ''.join(c for c in customer if c.isalnum() or c in ' _-').strip().replace(' ', '_')
        timestamp    = datetime.now().strftime('%Y%m%d_%H%M%S')
        requested    = _safe_name(data.get('download_name'))
        if requested:
            filename = f"{requested}.xlsx"           # name chosen in the Export dialog
        else:
            base     = data.get('export_filename') or f"{safe_cust}_PnL"
            filename = f"{base}_{timestamp}.xlsx"

        log.info(f"Excel exported: '{filename}' by '{session.get('user')}'")
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        ref = uuid.uuid4().hex[:8]
        log.error(f"Export failed [ref {ref}]: {e}\n{traceback.format_exc()}")
        return jsonify({'error': f'Something went wrong while building the workbook (reference {ref}).',
                        'reference': ref}), 500
