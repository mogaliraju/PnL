"""Excel workbook builder — isolated from Flask."""
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter, range_boundaries

# ── AX Brand Palette ──────────────────────────────────────────
AX_DARK   = '2D1B69'   # deep navy-purple  (primary headers)
AX_MED    = '5B21B6'   # medium purple     (sub-headers)
AX_LIGHT  = '7C3AED'   # violet            (table headers)
AX_PALE   = 'EDE9FE'   # lavender tint     (label cells)
AX_ACCENT = 'DDD6FE'   # light purple      (alternate rows)
AX_AMBER  = 'FEF3C7'   # amber tint        (cost highlight)
AX_GREEN  = 'DCFCE7'   # green tint        (revenue highlight)
AX_WHITE  = 'FFFFFF'
AX_TEXT   = '1E1B4B'   # dark indigo text


def _side(style='thin'):
    return Side(style=style)


def _thin():
    t = _side()
    return Border(left=t, right=t, top=t, bottom=t)


def _fill(hex_color):
    return PatternFill(start_color=hex_color, end_color=hex_color, fill_type='solid')


def _border_range(ws, min_row, max_row, min_col, max_col, style='thin'):
    """Apply a proper closed border to every cell in a range.
    Outer edges get the given style; inner grid lines get thin."""
    t = _side(style)
    i = _side('thin')
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            ws.cell(row, col).border = Border(
                top    = t if row == min_row else i,
                bottom = t if row == max_row else i,
                left   = t if col == min_col else i,
                right  = t if col == max_col else i,
            )


def _merge(ws, range_str, value='', bold=False, size=11, color=AX_TEXT,
           bg=None, h_align='left', v_align='center', wrap=False,
           num_fmt=None, italic=False):
    """Merge cells, style the top-left, and close borders on all cells."""
    ws.merge_cells(range_str)
    min_col, min_row, max_col, max_row = range_boundaries(range_str)
    c = ws.cell(min_row, min_col)
    c.value = value
    c.font = Font(bold=bold, size=size, color=color, italic=italic)
    c.alignment = Alignment(horizontal=h_align, vertical=v_align, wrap_text=wrap)
    if bg:
        c.fill = _fill(bg)
    if num_fmt:
        c.number_format = num_fmt
    # Close outer border on every cell in the merged range
    _border_range(ws, min_row, max_row, min_col, max_col)
    return c


def _cell(ws, row, col, value='', bold=False, size=11, color=AX_TEXT,
          bg=None, h_align='left', v_align='center', wrap=False, num_fmt=None):
    c = ws.cell(row, col)
    c.value = value
    c.font = Font(bold=bold, size=size, color=color)
    c.alignment = Alignment(horizontal=h_align, vertical=v_align, wrap_text=wrap)
    if bg:
        c.fill = _fill(bg)
    if num_fmt:
        c.number_format = num_fmt
    c.border = _thin()
    return c


def build_workbook(data: dict, costs: dict) -> openpyxl.Workbook:
    input_cost   = costs['input_cost']
    sell_cost    = costs['sell_cost']
    markup       = costs['markup']
    markup_pct   = costs['markup_pct']
    gross_margin = costs['gross_margin']

    rate_map  = {r['level']: r['rate'] for r in data.get('rate_card', [])}
    resources = data.get('resources', [])
    proj      = data.get('project', {})
    appr      = data.get('approvals', {})

    wb = openpyxl.Workbook()

    # ══════════════════════════════════════════════════════════════
    # Sheet 1 — PnL
    # ══════════════════════════════════════════════════════════════
    ws = wb.active
    ws.title = 'PnL'
    ws.sheet_view.showGridLines = False

    # Column widths  A  B   C   D   E   F   G   H   I   J   K   L   M
    col_widths =    [22,16, 18, 16, 16, 10, 14, 12, 12, 14, 14, 10, 12]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ── Row 1: Company banner ──────────────────────────────────
    ws.row_dimensions[1].height = 36
    _merge(ws, 'A1:M1',
           value=proj.get('company', 'AutomatonsX'),
           bold=True, size=18, color=AX_WHITE, bg=AX_DARK,
           h_align='center')

    # ── Row 2: Title ──────────────────────────────────────────
    ws.row_dimensions[2].height = 24
    _merge(ws, 'A2:M2',
           value='Project Profit and Loss Statement',
           bold=True, size=12, color=AX_WHITE, bg=AX_MED,
           h_align='center', italic=True)

    # ── Rows 3–5: Info section ─────────────────────────────────
    def _info_row(row, lbl_l, val_l, lbl_r, val_r, val_r_fmt=None, val_r_bg=None):
        ws.row_dimensions[row].height = 20
        _cell(ws, row, 1, lbl_l, bold=True, bg=AX_PALE, size=10)
        _merge(ws, f'B{row}:H{row}', val_l, size=10)
        _cell(ws, row, 9, lbl_r, bold=True, bg=AX_PALE, size=10)
        c = _merge(ws, f'J{row}:M{row}', val_r, size=10,
                   num_fmt=val_r_fmt, bg=val_r_bg or AX_WHITE)
        return c

    _info_row(3, 'Customer Name', proj.get('customer', ''),
              'Proposal Date', proj.get('proposal_date') or datetime.today().strftime('%Y-%m-%d'))
    _info_row(4, 'Location', proj.get('location', ''),
              'Reference No.', proj.get('reference', ''))
    _info_row(5, 'Duration (Months)', proj.get('duration_months', ''),
              'Proposal Value (USD)', sell_cost,
              val_r_fmt='#,##0.00', val_r_bg=AX_AMBER)

    # ── Row 6: Table header ─────────────────────────────────────
    ws.row_dimensions[6].height = 34
    table_headers = [
        ('A6:B6', 'Project Description'),
        ('C6:C6', 'Delivery\nMethod'),
        ('D6:D6', 'Partner\nDetails'),
        ('E6:E6', 'Payment\nTerms'),
        ('F6:F6', 'Duration\n(Months)'),
        ('G6:G6', 'Revenue\n(USD)'),
        ('H6:H6', 'Revenue\nSplit %'),
        ('I6:I6', 'Cost\nSplit %'),
        ('J6:J6', 'Cost\n(USD)'),
        ('K6:K6', 'Markup\n(USD)'),
        ('L6:L6', 'Markup\n%'),
        ('M6:M6', 'Gross\nMargin'),
    ]
    for rng, hdr in table_headers:
        _merge(ws, rng, hdr, bold=True, size=9, color=AX_WHITE,
               bg=AX_LIGHT, h_align='center', wrap=True)

    # ── Row 7+: Project data rows ───────────────────────────────
    pnl_roles = data.get('pnl_roles', [])
    # Always output at least one data row
    if not pnl_roles:
        pnl_roles = [{}]

    for idx, role in enumerate(pnl_roles):
        r = 7 + idx
        ws.row_dimensions[r].height = 22
        row_bg = AX_PALE if idx % 2 == 0 else AX_WHITE

        desc = (proj.get('project_description') or proj.get('customer', '')) if idx == 0 else role.get('name', '')
        _merge(ws, f'A{r}:B{r}', desc, bold=(idx == 0), size=10, bg=row_bg)
        _cell(ws, r, 3,  role.get('name', ''),          size=10, bg=row_bg)
        _cell(ws, r, 4,  role.get('partner', ''),        size=10, bg=row_bg)
        _cell(ws, r, 5,  role.get('payment_terms', ''),  size=10, bg=row_bg)
        _cell(ws, r, 6,  proj.get('duration_months', ''),size=10, bg=row_bg, h_align='center')

        if idx == 0:
            _cell(ws, r, 7,  sell_cost,    size=10, bg=AX_GREEN, num_fmt='#,##0.00', h_align='right')
            _cell(ws, r, 8,  '',           size=10, bg=row_bg)
            _cell(ws, r, 9,  '',           size=10, bg=row_bg)
            _cell(ws, r, 10, input_cost,   size=10, bg=AX_AMBER, num_fmt='#,##0.00', h_align='right')
            _cell(ws, r, 11, markup,       size=10, bg=AX_GREEN, num_fmt='#,##0.00', h_align='right')
            _cell(ws, r, 12, markup_pct,   size=10, bg=row_bg,   num_fmt='0.0%',     h_align='center')
            _cell(ws, r, 13, gross_margin, size=10, bg=row_bg,   num_fmt='0.0%',     h_align='center')
        else:
            for col in range(7, 14):
                _cell(ws, r, col, '', size=10, bg=row_bg)

    end_row = 7 + len(pnl_roles) - 1

    # ── Approvals ───────────────────────────────────────────────
    ar = end_row + 2
    for i, (lbl, val) in enumerate([
        ('Prepared By', appr.get('prepared_by', '')),
        ('Reviewed By', appr.get('reviewed_by', '')),
        ('Approved By', appr.get('approved_by', '')),
    ]):
        ws.row_dimensions[ar + i].height = 22
        _cell(ws, ar + i, 1, lbl, bold=True, size=10, bg=AX_PALE)
        _merge(ws, f'B{ar+i}:M{ar+i}', val, size=10)

    # ══════════════════════════════════════════════════════════════
    # Sheet 2 — Input Costing Calculation
    # ══════════════════════════════════════════════════════════════
    wc = wb.create_sheet('Input Costing Calculation')
    wc.sheet_view.showGridLines = False

    # Column widths: #, Role, Level, Hours, Rate($/hr), Cost(USD)
    for i, w in enumerate([6, 32, 18, 10, 14, 16], 1):
        wc.column_dimensions[get_column_letter(i)].width = w

    # ── Header row ─────────────────────────────────────────────
    wc.row_dimensions[1].height = 28
    sheet2_hdrs = ['#', 'Role', 'Level', 'Hours', 'Rate ($/hr)', 'Cost (USD)']
    hdr_bgs = [AX_PALE, AX_LIGHT, AX_LIGHT, AX_AMBER, AX_PALE, AX_GREEN]
    hdr_colors = [AX_TEXT, AX_WHITE, AX_WHITE, AX_TEXT, AX_TEXT, AX_TEXT]
    for col, (h, bg, fc) in enumerate(zip(sheet2_hdrs, hdr_bgs, hdr_colors), 1):
        _cell(wc, 1, col, h, bold=True, size=10, color=fc, bg=bg, h_align='center')

    # ── Resource rows ──────────────────────────────────────────
    total_h = total_c = 0
    for ri, res in enumerate(resources):
        rate = rate_map.get(res.get('level', ''), 0)
        hours = res.get('hours') or 0
        cost  = hours * rate
        total_h += hours
        total_c += cost
        row = 2 + ri
        row_bg = AX_ACCENT if ri % 2 == 0 else AX_WHITE
        wc.row_dimensions[row].height = 18
        _cell(wc, row, 1, ri + 1,           size=10, bg=row_bg, h_align='center')
        _cell(wc, row, 2, res.get('role',''),size=10, bg=row_bg)
        _cell(wc, row, 3, res.get('level',''),size=10, bg=row_bg, h_align='center')
        _cell(wc, row, 4, hours,             size=10, bg=row_bg, h_align='center')
        _cell(wc, row, 5, rate,              size=10, bg=row_bg, num_fmt='#,##0.00', h_align='right')
        _cell(wc, row, 6, round(cost, 2),    size=10, bg=row_bg, num_fmt='#,##0.00', h_align='right')

    # ── Totals row ─────────────────────────────────────────────
    tr = 2 + len(resources)
    wc.row_dimensions[tr].height = 20
    _cell(wc, tr, 1, '',             bold=True, size=10, bg=AX_PALE)
    _cell(wc, tr, 2, 'TOTAL',        bold=True, size=10, bg=AX_PALE, h_align='right')
    _cell(wc, tr, 3, '',             bold=True, size=10, bg=AX_PALE)
    _cell(wc, tr, 4, total_h,        bold=True, size=10, bg=AX_AMBER, h_align='center')
    _cell(wc, tr, 5, '',             bold=True, size=10, bg=AX_PALE)
    _cell(wc, tr, 6, round(total_c, 2), bold=True, size=10, bg=AX_GREEN, num_fmt='#,##0.00', h_align='right')

    # ── Summary block ──────────────────────────────────────────
    sr = tr + 2
    wc.row_dimensions[sr].height = 20
    wc.row_dimensions[sr + 1].height = 20
    wc.row_dimensions[sr + 2].height = 20

    _merge(wc, f'A{sr}:E{sr}',   'Input Cost (USD)',  bold=True, size=10, bg=AX_PALE, h_align='right')
    _cell (wc,  sr, 6, input_cost, bold=True, size=10, bg=AX_AMBER, num_fmt='#,##0.00', h_align='right')

    _merge(wc, f'A{sr+1}:E{sr+1}', 'Sell Cost (USD)',   bold=True, size=10, bg=AX_PALE, h_align='right')
    _cell (wc,  sr+1, 6, sell_cost, bold=True, size=10, bg=AX_GREEN, num_fmt='#,##0.00', h_align='right')

    _merge(wc, f'A{sr+2}:E{sr+2}', 'Gross Margin',      bold=True, size=10, bg=AX_PALE, h_align='right')
    _cell (wc,  sr+2, 6, gross_margin, bold=True, size=10, bg=AX_PALE, num_fmt='0.0%', h_align='right')

    return wb
