// ============================================================
// PnL Application — Frontend Logic
// ============================================================

let appData = {};

// ============================================================
// COUNTRIES LIST
// ============================================================
const COUNTRIES = [
  "Afghanistan","Albania","Algeria","Andorra","Angola","Antigua and Barbuda",
  "Argentina","Armenia","Australia","Austria","Azerbaijan","Bahamas","Bahrain",
  "Bangladesh","Barbados","Belarus","Belgium","Belize","Benin","Bhutan",
  "Bolivia","Bosnia and Herzegovina","Botswana","Brazil","Brunei","Bulgaria",
  "Burkina Faso","Burundi","Cabo Verde","Cambodia","Cameroon","Canada",
  "Central African Republic","Chad","Chile","China","Colombia","Comoros",
  "Congo (Brazzaville)","Congo (Kinshasa)","Costa Rica","Croatia","Cuba",
  "Cyprus","Czech Republic","Denmark","Djibouti","Dominica","Dominican Republic",
  "Ecuador","Egypt","El Salvador","Equatorial Guinea","Eritrea","Estonia",
  "Eswatini","Ethiopia","Fiji","Finland","France","Gabon","Gambia","Georgia",
  "Germany","Ghana","Greece","Grenada","Guatemala","Guinea","Guinea-Bissau",
  "Guyana","Haiti","Honduras","Hungary","Iceland","India","Indonesia","Iran",
  "Iraq","Ireland","Israel","Italy","Jamaica","Japan","Jordan","Kazakhstan",
  "Kenya","Kiribati","Kuwait","Kyrgyzstan","Laos","Latvia","Lebanon","Lesotho",
  "Liberia","Libya","Liechtenstein","Lithuania","Luxembourg","Madagascar",
  "Malawi","Malaysia","Maldives","Mali","Malta","Marshall Islands","Mauritania",
  "Mauritius","Mexico","Micronesia","Moldova","Monaco","Mongolia","Montenegro",
  "Morocco","Mozambique","Myanmar","Namibia","Nauru","Nepal","Netherlands",
  "New Zealand","Nicaragua","Niger","Nigeria","North Korea","North Macedonia",
  "Norway","Oman","Pakistan","Palau","Palestine","Panama","Papua New Guinea",
  "Paraguay","Peru","Philippines","Poland","Portugal","Qatar","Romania","Russia",
  "Rwanda","Saint Kitts and Nevis","Saint Lucia","Saint Vincent and the Grenadines",
  "Samoa","San Marino","Sao Tome and Principe","Saudi Arabia","Senegal","Serbia",
  "Seychelles","Sierra Leone","Singapore","Slovakia","Slovenia","Solomon Islands",
  "Somalia","South Africa","South Korea","South Sudan","Spain","Sri Lanka","Sudan",
  "Suriname","Sweden","Switzerland","Syria","Taiwan","Tajikistan","Tanzania",
  "Thailand","Timor-Leste","Togo","Tonga","Trinidad and Tobago","Tunisia","Turkey",
  "Turkmenistan","Tuvalu","Uganda","Ukraine","United Arab Emirates","United Kingdom",
  "United States","Uruguay","Uzbekistan","Vanuatu","Vatican City","Venezuela",
  "Vietnam","Yemen","Zambia","Zimbabwe"
];

let locationSelect = null;

// ---------- Bootstrap Toast helper ----------
function showToast(msg, type = 'success') {
  const el = document.getElementById('toast');
  el.className = `toast align-items-center bg-${type}`;
  document.getElementById('toast-body').textContent = msg;
  bootstrap.Toast.getOrCreateInstance(el, { delay: 3000 }).show();
}

// ---------- Load data on page ready ----------
document.addEventListener('DOMContentLoaded', async () => {
  const res = await fetch('/api/data');
  appData = await res.json();
  populateAll();
});

function populateAll() {
  populateProject();
  renderResources();
  renderRateCard();
  renderReleases();
  renderPnlRoles();
  populateFundingApprovals();
  populateExportSettings();
  updateSummary();
}

// ============================================================
// PROJECT INFO
// ============================================================
function populateProject() {
  const p = appData.project || {};
  setVal('proj_company', p.company);
  setVal('proj_customer', p.customer);
  setVal('proj_reference', p.reference);
  initLocationDropdown(p.location);
  setVal('proj_proposal_date', p.proposal_date);
  setVal('proj_first_touch', p.customer_first_touch_point);
  setVal('proj_description', p.project_description);
  setVal('proj_partner', p.partner);
  setVal('proj_payment_terms', p.payment_terms);
  setVal('proj_duration', p.duration_months ?? '');

  // Live listeners
  ['proj_company','proj_customer','proj_location','proj_reference','proj_proposal_date',
   'proj_first_touch','proj_description','proj_partner','proj_payment_terms','proj_duration']
    .forEach(id => {
      document.getElementById(id)?.addEventListener('input', () => {
        collectProject();
        updateSummary();
        updateFilenamePreview();
      });
    });
}

function initLocationDropdown(currentValue) {
  // Populate <select> options
  const el = document.getElementById('proj_location');
  el.innerHTML = '<option value="">Select country…</option>';
  COUNTRIES.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c;
    opt.textContent = c;
    el.appendChild(opt);
  });

  // Destroy previous instance if exists
  if (locationSelect) { locationSelect.destroy(); locationSelect = null; }

  locationSelect = new TomSelect('#proj_location', {
    placeholder: 'Search country…',
    allowEmptyOption: true,
    maxOptions: 250,
    onChange() { collectProject(); updateFilenamePreview(); }
  });

  if (currentValue) locationSelect.setValue(currentValue, true);
}

function collectProject() {
  appData.project = {
    company: getVal('proj_company'),
    customer: getVal('proj_customer'),
    location: locationSelect ? (locationSelect.getValue() || '') : getVal('proj_location'),
    reference: getVal('proj_reference'),
    proposal_date: getVal('proj_proposal_date'),
    customer_first_touch_point: getVal('proj_first_touch'),
    project_description: getVal('proj_description'),
    partner: getVal('proj_partner'),
    payment_terms: getVal('proj_payment_terms'),
    duration_months: parseFloat(getVal('proj_duration')) || null
  };
}

// ============================================================
// SUMMARY CALCULATIONS
// ============================================================
function updateSummary() {
  const rateMap = {};
  (appData.rate_card || []).forEach(r => { rateMap[r.level] = r.rate; });
  const resources = appData.resources || [];

  let inputCost = 0;
  resources.forEach(r => {
    inputCost += (r.hours || 0) * (rateMap[r.level] || 0);
  });
  const sellCost = inputCost > 0 ? inputCost / 0.6 : 0;
  const markup = sellCost - inputCost;
  const margin = sellCost > 0 ? markup / sellCost : 0;

  document.getElementById('sum_input_cost').textContent = fmtMoney(inputCost);
  document.getElementById('sum_sell_cost').textContent = fmtMoney(sellCost);
  document.getElementById('sum_markup').textContent = fmtMoney(markup);
  document.getElementById('sum_margin').textContent = (margin * 100).toFixed(1) + '%';
}

// ============================================================
// RESOURCES
// ============================================================
function renderResources() {
  const rateMap = {};
  (appData.rate_card || []).forEach(r => { rateMap[r.level] = r.rate; });
  const resources = appData.resources || [];
  const levels = (appData.rate_card || []).map(r => r.level);

  const tbody = document.getElementById('resources-tbody');
  tbody.innerHTML = '';

  let totalHours = 0, totalCost = 0;

  resources.forEach((res, i) => {
    const rate = rateMap[res.level] || 0;
    const cost = (res.hours || 0) * rate;
    totalHours += (res.hours || 0);
    totalCost += cost;

    const levelOpts = levels.map(l =>
      `<option value="${l}" ${l === res.level ? 'selected' : ''}>${l}</option>`
    ).join('');

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="text-center text-muted small">${i + 1}</td>
      <td><input type="text" class="form-control form-control-sm" value="${esc(res.role)}"
          onchange="appData.resources[${i}].role=this.value; updateSummary()"/></td>
      <td>
        <select class="form-select form-select-sm" onchange="appData.resources[${i}].level=this.value; renderResources(); updateSummary();">
          ${levelOpts}
          <option value="${res.level}" ${!levels.includes(res.level)?'selected':''} style="font-style:italic">${!levels.includes(res.level)?res.level:''}</option>
        </select>
      </td>
      <td><input type="number" class="form-control form-control-sm" value="${res.hours ?? ''}" min="0"
          onchange="appData.resources[${i}].hours=parseFloat(this.value)||0; renderResources(); updateSummary();"/></td>
      <td class="text-end text-muted small">$${rate.toFixed(2)}</td>
      <td class="text-end fw-semibold">${fmtMoney(cost)}</td>
      <td class="text-center">
        <button class="btn btn-outline-danger btn-icon" onclick="removeResource(${i})" title="Remove">
          <i class="bi bi-trash3"></i>
        </button>
      </td>`;
    tbody.appendChild(tr);
  });

  document.getElementById('tot_hours').textContent = totalHours;
  document.getElementById('tot_cost').textContent = fmtMoney(totalCost);
}

function addResource() {
  if (!appData.resources) appData.resources = [];
  const defaultLevel = appData.rate_card?.[0]?.level || 'L3';
  appData.resources.push({ id: Date.now(), role: 'New Role', level: defaultLevel, hours: 0 });
  renderResources();
  updateSummary();
}

function removeResource(i) {
  appData.resources.splice(i, 1);
  renderResources();
  updateSummary();
}

// ============================================================
// RATE CARD
// ============================================================
function renderRateCard() {
  const rc = appData.rate_card || [];
  const tbody = document.getElementById('ratecard-tbody');
  tbody.innerHTML = '';

  rc.forEach((item, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="text-center text-muted small">${i + 1}</td>
      <td><input type="text" class="form-control form-control-sm" value="${esc(item.level)}"
          onchange="appData.rate_card[${i}].level=this.value; renderResources(); renderRateChart(); updateSummary();"/></td>
      <td><input type="number" class="form-control form-control-sm text-end" value="${item.rate}" min="0" step="0.5"
          onchange="appData.rate_card[${i}].rate=parseFloat(this.value)||0; renderResources(); renderRateChart(); updateSummary();"/></td>
      <td class="text-center">
        <button class="btn btn-outline-danger btn-icon" onclick="removeRateLevel(${i})" title="Remove">
          <i class="bi bi-trash3"></i>
        </button>
      </td>`;
    tbody.appendChild(tr);
  });

  renderRateChart();
}

function addRateLevel() {
  if (!appData.rate_card) appData.rate_card = [];
  const nextNum = appData.rate_card.length + 1;
  appData.rate_card.push({ level: `L${nextNum}`, rate: 0 });
  renderRateCard();
}

function removeRateLevel(i) {
  appData.rate_card.splice(i, 1);
  renderRateCard();
  renderResources();
  updateSummary();
}

function renderRateChart() {
  const rc = appData.rate_card || [];
  const maxRate = Math.max(...rc.map(r => r.rate), 1);
  const area = document.getElementById('rate-chart-area');
  area.innerHTML = rc.map(item => `
    <div class="rate-bar-row">
      <div class="rate-bar-label">${esc(item.level)}</div>
      <div class="rate-bar-track">
        <div class="rate-bar-fill" style="width:${(item.rate / maxRate * 100).toFixed(1)}%"></div>
      </div>
      <div class="rate-bar-val">$${item.rate}/hr</div>
    </div>`).join('');
}

// ============================================================
// RELEASES
// ============================================================
function renderReleases() {
  const releases = appData.releases || [];
  const tbody = document.getElementById('releases-tbody');
  tbody.innerHTML = '';

  releases.forEach((rel, i) => {
    const fields = ['name','entities','ec_time_off','payroll_countries','ec_payroll',
                    'abap_cpi_ptp','btp','rcm_onb_offb','pmgm','lms'];
    const tds = fields.map(f => {
      const isText = f === 'name' || f === 'payroll_countries';
      const val = rel[f] ?? '';
      return `<td><input type="${isText ? 'text' : 'number'}" class="form-control form-control-sm"
        value="${esc(String(val))}" style="min-width:${isText?'120px':'60px'}"
        onchange="appData.releases[${i}]['${f}']=${isText?'this.value':'(parseFloat(this.value)||null)'}"/></td>`;
    }).join('');
    const tr = document.createElement('tr');
    tr.innerHTML = `${tds}
      <td class="text-center">
        <button class="btn btn-outline-danger btn-icon" onclick="removeRelease(${i})">
          <i class="bi bi-trash3"></i>
        </button>
      </td>`;
    tbody.appendChild(tr);
  });
}

function addRelease() {
  if (!appData.releases) appData.releases = [];
  const n = appData.releases.length + 1;
  appData.releases.push({
    name: `R${n}`, entities: null, ec_time_off: null,
    payroll_countries: '', ec_payroll: null, abap_cpi_ptp: null,
    btp: null, rcm_onb_offb: null, pmgm: null, lms: null
  });
  renderReleases();
}

function removeRelease(i) {
  appData.releases.splice(i, 1);
  renderReleases();
}

// ============================================================
// PNL ROLES
// ============================================================
function renderPnlRoles() {
  const roles = appData.pnl_roles || [];
  const tbody = document.getElementById('pnl-roles-tbody');
  tbody.innerHTML = '';

  roles.forEach((role, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="text-center text-muted small">${i + 1}</td>
      <td><input type="text" class="form-control form-control-sm" value="${esc(role.name||'')}"
          onchange="appData.pnl_roles[${i}].name=this.value"/></td>
      <td><input type="text" class="form-control form-control-sm" value="${esc(role.partner||'')}"
          onchange="appData.pnl_roles[${i}].partner=this.value"/></td>
      <td><input type="text" class="form-control form-control-sm" value="${esc(role.payment_terms||'')}"
          onchange="appData.pnl_roles[${i}].payment_terms=this.value"/></td>
      <td class="text-center">
        <button class="btn btn-outline-danger btn-icon" onclick="removePnlRole(${i})">
          <i class="bi bi-trash3"></i>
        </button>
      </td>`;
    tbody.appendChild(tr);
  });
}

function addPnlRole() {
  if (!appData.pnl_roles) appData.pnl_roles = [];
  appData.pnl_roles.push({ id: Date.now(), name: 'New Role', partner: '', payment_terms: '' });
  renderPnlRoles();
}

function removePnlRole(i) {
  appData.pnl_roles.splice(i, 1);
  renderPnlRoles();
}

// ============================================================
// FUNDING & APPROVALS
// ============================================================
function populateFundingApprovals() {
  const att = appData.attachments || {};
  document.getElementById('att_customer_po').checked = !!att.customer_po;
  document.getElementById('att_cloud4c').checked = !!att.cloud4c_quote;
  document.getElementById('att_partner').checked = !!att.partner_proposal;

  const f = appData.funding || {};
  const setFund = (prefix, obj) => {
    setVal(`fund_${prefix}_method`, obj?.method);
    setVal(`fund_${prefix}_ref`, obj?.reference);
    setVal(`fund_${prefix}_currency`, obj?.currency || 'USD');
    setVal(`fund_${prefix}_value`, obj?.value ?? '');
  };
  setFund('mkt', f.marketing);
  setFund('mgmt', f.management);
  setFund('disc', f.discount);

  const appr = appData.approvals || {};
  setVal('appr_prepared_by', appr.prepared_by);
  setVal('appr_reviewed_by', appr.reviewed_by);
  setVal('appr_approved_by', appr.approved_by);
}

function collectFundingApprovals() {
  appData.attachments = {
    customer_po: document.getElementById('att_customer_po').checked,
    cloud4c_quote: document.getElementById('att_cloud4c').checked,
    partner_proposal: document.getElementById('att_partner').checked
  };

  const getFund = prefix => ({
    method: getVal(`fund_${prefix}_method`),
    reference: getVal(`fund_${prefix}_ref`),
    currency: getVal(`fund_${prefix}_currency`) || 'USD',
    value: parseFloat(getVal(`fund_${prefix}_value`)) || null
  });
  appData.funding = {
    marketing: getFund('mkt'),
    management: getFund('mgmt'),
    discount: getFund('disc')
  };

  appData.approvals = {
    prepared_by: getVal('appr_prepared_by'),
    reviewed_by: getVal('appr_reviewed_by'),
    approved_by: getVal('appr_approved_by')
  };
}

// ============================================================
// EXPORT SETTINGS
// ============================================================
function populateExportSettings() {
  setVal('export_filename', appData.export_filename || '');
  updateFilenamePreview();
  document.getElementById('export_filename')?.addEventListener('input', updateFilenamePreview);
}

function collectExportSettings() {
  appData.export_filename = getVal('export_filename');
}

function updateFilenamePreview() {
  const customer = (appData.project?.customer || 'PnL').trim().replace(/[^a-zA-Z0-9 _-]/g, '').replace(/ /g, '_');
  const base = getVal('export_filename').trim() || `${customer}_PnL`;
  const now = new Date();
  const ts = now.getFullYear().toString()
    + String(now.getMonth()+1).padStart(2,'0')
    + String(now.getDate()).padStart(2,'0')
    + '_'
    + String(now.getHours()).padStart(2,'0')
    + String(now.getMinutes()).padStart(2,'0')
    + String(now.getSeconds()).padStart(2,'0');
  const el = document.getElementById('filename_preview');
  if (el) el.textContent = `${base}_${ts}.xlsx`;
}

// ============================================================
// SAVE & EXPORT
// ============================================================
function collectAll() {
  collectProject();
  collectFundingApprovals();
  collectExportSettings();
  // Resources and rate card are updated in-place via onchange handlers
}

async function saveAll() {
  collectAll();
  try {
    const res = await fetch('/api/data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(appData)
    });
    if (res.ok) showToast('Saved successfully!', 'success');
    else showToast('Save failed', 'danger');
  } catch (e) {
    showToast('Error: ' + e.message, 'danger');
  }
}

async function exportExcel() {
  collectAll();
  try {
    showToast('Generating Excel…', 'primary');
    const res = await fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(appData)
    });

    if (!res.ok) {
      // Error responses come back as JSON
      const err = await res.json();
      showToast('Export failed: ' + (err.error || 'unknown error'), 'danger');
      return;
    }

    // Success: stream the blob as a browser download
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename[^;=\n]*=["']?([^"';\n]+)/);
    const filename = match ? match[1] : (appData.export_filename || 'PnL_Export') + '.xlsx';
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    showToast(`✓ Downloaded: ${filename}`, 'success');
  } catch (e) {
    showToast('Error: ' + e.message, 'danger');
  }
}

// ============================================================
// HELPERS
// ============================================================
function setVal(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val ?? '';
}
function getVal(id) {
  return document.getElementById(id)?.value ?? '';
}
function esc(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fmtMoney(n) {
  if (isNaN(n)) return '$0.00';
  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
