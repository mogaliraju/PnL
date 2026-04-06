"""Excel export route."""
import traceback
from datetime import datetime
from io import BytesIO

from flask import Blueprint, request, jsonify, send_file, session
from pnl.utils.storage import save_data
from pnl.utils.auth import login_required
from pnl.utils.validators import validate_payload, ValidationError
from pnl.services.pnl_service import compute_costs
from pnl.services.excel_service import build_workbook
from pnl.utils.logger import get_logger

bp = Blueprint('export', __name__)
log = get_logger(__name__)


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

        save_data(data)

        rate_map      = {r['level']: r['rate'] for r in data.get('rate_card', [])}
        target_margin = float(data.get('target_margin', 0.40))
        costs         = compute_costs(data.get('resources', []), rate_map, target_margin)

        wb  = build_workbook(data, costs)
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)

        customer     = data.get('project', {}).get('customer', 'PnL') or 'PnL'
        safe_cust    = ''.join(c for c in customer if c.isalnum() or c in ' _-').strip().replace(' ', '_')
        timestamp    = datetime.now().strftime('%Y%m%d_%H%M%S')
        base         = data.get('export_filename') or f"{safe_cust}_PnL"
        filename     = f"{base}_{timestamp}.xlsx"

        log.info(f"Excel exported: '{filename}' by '{session.get('user')}'")
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        log.error(f"Export failed: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e), 'detail': traceback.format_exc()}), 500
