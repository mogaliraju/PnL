"""Excel workbook builder — isolated from Flask."""
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def thin_border():
    t = Side(style='thin')
    return Border(left=t, right=t, top=t, bottom=t)


def fill(hex_color):
    return PatternFill(start_color=hex_color, end_color=hex_color, fill_type='solid')


def _set(ws, row, col, value, bold=False, bg=None, color='000000', num_fmt=None):
    c = ws.cell(row, col)
    c.value = value
    c.font = Font(bold=bold, color=color)
    c.alignment = Alignment(vertical='center', wrap_text=True)
    if bg:
        c.fill = fill(bg)
    if num_fmt:
        c.number_format = num_fmt
    c.border = thin_border()
    return c


def _setc(ws, row, col, value, bold=False, bg=None, num_fmt=None):
    c = ws.cell(row, col)
    c.value = value
    c.font = Font(bold=bold)
    c.alignment = Alignment(vertical='center')
    if bg:
        c.fill = fill(bg)
    if num_fmt:
        c.number_format = num_fmt
    c.border = thin_border()
    return c


def build_workbook(data: dict, costs: dict) -> openpyxl.Workbook:
    input_cost = costs['input_cost']
    sell_cost  = costs['sell_cost']
    markup     = costs['markup']
    markup_pct = costs['markup_pct']
    gross_margin = costs['gross_margin']

    rate_map   = {r['level']: r['rate'] for r in data.get('rate_card', [])}
    resources  = data.get('resources', [])
    proj       = data.get('project', {})
    appr       = data.get('approvals', {})

    wb = openpyxl.Workbook()

    # ── Sheet 1: PnL ────────────────────────────────────────────
    ws = wb.active
    ws.title = 'PnL'

    for i, w in enumerate([22,18,22,20,18,12,14,12,12,14,14,10,14], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Header rows
    ws.merge_cells('A1:M1')
    c = ws['A1']
    c.value = proj.get('company', 'AutomatonsX')
    c.font = Font(bold=True, size=16, color='FFFFFF')
    c.fill = fill('2D1B69')
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 28

    ws.merge_cells('A2:M2')
    c = ws['A2']
    c.value = 'Project Profit and Loss Statement'
    c.font = Font(bold=True, size=13, color='FFFFFF')
    c.fill = fill('6D28D9')
    c.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[2].height = 22

    # Info rows 3-6
    info = [
        (3, 'Customer Name', proj.get('customer',''), 'Date', ''),
        (4, 'Location',      proj.get('location',''), 'Reference', proj.get('reference','')),
    ]
    for row, lbl, val, lbl2, val2 in info:
        _set(ws, row, 1, lbl, bold=True, bg='EDE9FE')
        ws.merge_cells(f'B{row}:J{row}')
        _set(ws, row, 2, val)
        _set(ws, row, 11, lbl2, bold=True, bg='EDE9FE')
        ws.merge_cells(f'L{row}:M{row}')
        _set(ws, row, 12, val2)

    _set(ws, 5, 1, 'Proposal Date', bold=True, bg='EDE9FE')
    ws.merge_cells('B5:J5')
    _set(ws, 5, 2, proj.get('proposal_date') or datetime.today().strftime('%Y-%m-%d'))
    ws.merge_cells('K5:M5')
    _set(ws, 5, 11, proj.get('customer_first_touch_point', ''))

    _set(ws, 6, 1, 'Proposal Value', bold=True, bg='EDE9FE')
    ws.merge_cells('B6:J6')
    _set(ws, 6, 2, sell_cost, num_fmt='#,##0.00')

    # Table header row 7
    ws.row_dimensions[7].height = 30
    hdrs = [('A7','Project Description'),('C7','Delivery Method'),('D7','Partner Details'),
            ('E7','Payment Terms'),('F7','Duration\n(Months)'),('G7','Revenue (USD)'),
            ('H7','Revenue Split'),('I7','Cost Split (%)'),('J7','Cost (USD)'),
            ('K7','Markup Value\n(USD)'),('L7','Markup %'),('M7','Gross Margin')]
    for ref, val in hdrs:
        c = ws[ref]
        c.value = val
        c.font = Font(bold=True, color='FFFFFF', size=9)
        c.fill = fill('6D28D9')
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = thin_border()
    ws.merge_cells('A7:B7')

    # PnL role rows
    pnl_roles = data.get('pnl_roles', [])
    for idx, role in enumerate(pnl_roles):
        r = 8 + idx
        ws.merge_cells(f'A{r}:B{r}')
        _set(ws, r, 1,
             proj.get('project_description', proj.get('customer','')) if idx == 0 else role.get('name',''),
             bold=(idx==0), bg='F5F3FF' if idx==0 else 'F9F9F9')
        _set(ws, r, 3, role.get('name',''))
        _set(ws, r, 4, role.get('partner',''))
        _set(ws, r, 5, role.get('payment_terms',''))
        _set(ws, r, 6, proj.get('duration_months',''))
        if idx == 0:
            _set(ws, r, 7,  sell_cost,   num_fmt='#,##0.00', bg='F0FDF4')
            _set(ws, r, 10, input_cost,  num_fmt='#,##0.00', bg='FEF3C7')
            _set(ws, r, 11, markup,      num_fmt='#,##0.00', bg='F0FDF4')
            _set(ws, r, 12, markup_pct,  num_fmt='0.0%')
            _set(ws, r, 13, gross_margin,num_fmt='0.0%')
        for col in range(1, 14):
            ws.cell(r, col).border = thin_border()

    end_row = 8 + max(len(pnl_roles) - 1, 0)

    # Approvals
    xr = end_row + 2
    ws.row_dimensions[xr - 1].height = 8  # spacer
    for i, (lbl, val) in enumerate([
        ('Prepared By', appr.get('prepared_by', '')),
        ('Reviewed By', appr.get('reviewed_by', '')),
        ('Approved By', appr.get('approved_by', '')),
    ]):
        ws.row_dimensions[xr + i].height = 22
        _set(ws, xr + i, 1, lbl, bold=True, bg='EDE9FE')
        ws.merge_cells(f'B{xr+i}:M{xr+i}')
        _set(ws, xr + i, 2, val)

    # ── Sheet 2: Input Costing Calculation ─────────────────────
    wc = wb.create_sheet('Input Costing Calculation')
    for i, w in enumerate([10, 10, 18, 26, 12, 12], 1):
        wc.column_dimensions[get_column_letter(i)].width = w

    # Header
    wc.row_dimensions[1].height = 24
    for col, (h, bg) in enumerate([
        ('Hours', 'FEF9C3'), ('Cost (USD)', 'DCFCE7'),
        ('Level', 'EDE9FE'), ('Role', 'EDE9FE'),
    ], 1):
        c = wc.cell(1, col)
        c.value = h
        c.font = Font(bold=True, size=9)
        c.fill = fill(bg)
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = thin_border()

    # Resource rows
    total_h = total_c = 0
    for ri, res in enumerate(resources):
        rate = rate_map.get(res.get('level', ''), 0)
        cost = (res.get('hours') or 0) * rate
        total_h += res.get('hours') or 0
        total_c += cost
        row = 2 + ri
        _setc(wc, row, 1, res.get('hours'))
        _setc(wc, row, 2, round(cost, 2), num_fmt='#,##0.00')
        _setc(wc, row, 3, res.get('level'))
        _setc(wc, row, 4, res.get('role'))

    # Totals row
    mr = 2 + len(resources)
    _setc(wc, mr, 1, total_h,          bold=True, bg='FEF9C3')
    _setc(wc, mr, 2, round(total_c,2), bold=True, bg='DCFCE7', num_fmt='#,##0.00')
    _setc(wc, mr, 3, 'Total',          bold=True)

    # Summary
    sr = mr + 2
    _setc(wc, sr,   1, 'Input Cost', bold=True, bg='FEF3C7')
    _setc(wc, sr,   2, input_cost,   num_fmt='#,##0.00', bg='FEF3C7')
    _setc(wc, sr+1, 1, 'Sell Cost',  bold=True, bg='F0FDF4')
    _setc(wc, sr+1, 2, sell_cost,    num_fmt='#,##0.00', bg='F0FDF4')

    return wb
