// ============================================================
// PnL Application — Frontend Logic
// ============================================================

let appData = {};
let currentUser = {};
const DEFAULT_BUSINESS_UNITS = ['EDM', 'AI', 'SAP', 'RPA'];
const ALL_PROJECTS_SORT_STORAGE_KEY = 'pnl.allProjects.sort';
const ALL_PROJECTS_SEARCH_STORAGE_KEY = 'pnl.allProjects.search';

function buildDefaultProject(overrides = {}) {
  return {
    company: 'AutomatonsX',
    customer: '',
    location: '',
    reference: '',
    proposal_date: '',
    customer_first_touch_point: '',
    project_description: '',
    partner: 'AutomatonsX',
    payment_terms: 'As per proposal',
    duration_months: null,
    status: 'Draft',
    stage: 'Qualification',
    priority: 'Medium',
    project_owner: '',
    business_unit: '',
    account_manager: '',
    sales_spoc: '',
    delivery_manager: '',
    technical_lead: '',
    expected_start_date: '',
    expected_end_date: '',
    opportunity_id: '',
    project_type: '',
    industry: '',
    delivery_model: 'Offshore',
    billing_type: 'Time & Material',
    currency: 'USD',
    discount_pct: null,
    travel_cost: null,
    infra_cost: null,
    third_party_cost: null,
    internal_notes: '',
    risks: '',
    dependencies: '',
    next_action: '',
    next_follow_up_date: '',
    ...overrides,
  };
}

function normalizeProject(project = {}) {
  return buildDefaultProject({
    ...project,
    project_description: project.project_description ?? project.description ?? '',
  });
}

function normalizeBusinessUnits(units = []) {
  return [...new Set(
    [...DEFAULT_BUSINESS_UNITS, ...(Array.isArray(units) ? units : [])]
      .map(v => String(v || '').trim())
      .filter(Boolean)
  )];
}

// ── Auth / session ───────────────────────────────────────────
async function loadSession() {
  const res = await fetch('/api/me');
  if (!res.ok) { window.location.href = '/login'; return; }
  currentUser = await res.json();
  document.getElementById('nav_username').textContent = currentUser.name || currentUser.username;
  document.getElementById('nav_role_label').textContent =
    currentUser.role === 'admin' ? '👑 Administrator' : '👤 User';
  if (currentUser.role === 'admin') {
    document.getElementById('nav_admin_link').classList.remove('d-none');
    // Load users modal on open
    document.getElementById('usersModal')
      ?.addEventListener('show.bs.modal', loadUsersList);
  }
}

// ── User management ──────────────────────────────────────────
async function loadUsersList() {
  const res  = await fetch('/api/users');
  const list = await res.json();
  const el   = document.getElementById('users-list');
  el.innerHTML = `
    <table class="table table-bordered table-hover align-middle">
      <thead class="table-dark">
        <tr><th>Username</th><th>Full Name</th><th>Role</th><th>Created</th><th style="width:120px"></th></tr>
      </thead>
      <tbody>
        ${list.map(u => `
          <tr>
            <td class="fw-semibold">${esc(u.username)}</td>
            <td>${esc(u.name)}</td>
            <td><span class="badge ${u.role==='admin'?'text-bg-warning':'text-bg-secondary'}">${u.role}</span></td>
            <td class="small text-muted">${u.created_at?.replace('T',' ') || ''}</td>
            <td class="text-center">
              <button class="btn btn-outline-primary btn-sm me-1"
                onclick="adminResetPassword('${esc(u.username)}')" title="Reset password">
                <i class="bi bi-key"></i>
              </button>
              ${u.username !== 'admin' ? `
              <button class="btn btn-outline-danger btn-sm"
                onclick="deleteUser('${esc(u.username)}')" title="Delete">
                <i class="bi bi-trash3"></i>
              </button>` : ''}
            </td>
          </tr>`).join('')}
      </tbody>
    </table>`;
}

async function createUser() {
  const username = document.getElementById('new_user_username').value.trim();
  const name     = document.getElementById('new_user_name').value.trim();
  const password = document.getElementById('new_user_password').value.trim();
  const role     = document.getElementById('new_user_role').value;
  if (!username || !password) { showToast('Username and password required', 'danger'); return; }
  const res = await fetch('/api/users', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ username, name, password, role })
  });
  const json = await res.json();
  if (res.ok) {
    document.getElementById('new_user_username').value = '';
    document.getElementById('new_user_name').value = '';
    document.getElementById('new_user_password').value = '';
    loadUsersList();
    showToast(`User "${username}" created`, 'success');
  } else {
    showToast(json.error || 'Failed', 'danger');
  }
}

async function deleteUser(username) {
  if (!confirm(`Delete user "${username}"?`)) return;
  await fetch(`/api/users/${username}`, { method: 'DELETE' });
  loadUsersList();
  showToast(`User "${username}" deleted`, 'success');
}

async function adminResetPassword(username) {
  const pw = prompt(`Set new password for "${username}":`);
  if (!pw) return;
  const res = await fetch(`/api/users/${username}/password`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ password: pw })
  });
  if (res.ok) showToast('Password updated', 'success');
  else showToast('Failed', 'danger');
}

async function changePassword() {
  const pw1 = document.getElementById('new_password').value;
  const pw2 = document.getElementById('confirm_password').value;
  if (!pw1) { showToast('Enter a password', 'danger'); return; }
  if (pw1 !== pw2) { showToast('Passwords do not match', 'danger'); return; }
  const res = await fetch(`/api/users/${currentUser.username}/password`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ password: pw1 })
  });
  if (res.ok) {
    showToast('Password changed', 'success');
    bootstrap.Modal.getInstance(document.getElementById('changePasswordModal'))?.hide();
    document.getElementById('new_password').value = '';
    document.getElementById('confirm_password').value = '';
  } else {
    showToast('Failed', 'danger');
  }
}

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
  await loadSession();
  // Verify session is valid (will redirect to /login if not)
  const res = await fetch('/api/data');
  if (!res.ok) { window.location.href = '/login'; return; }
  // Load global settings (rate card + catalog) but start with a blank project
  const serverData = await res.json();
  appData = {
    project: buildDefaultProject(),
    resources: [], pnl_roles: [], releases: [],
    rate_card:    serverData.rate_card    || [],
    role_catalog: serverData.role_catalog || [],
    business_units: normalizeBusinessUnits(serverData.business_units || []),
    attachments: { customer_po: false, cloud4c_quote: false, partner_proposal: false },
    funding: { marketing: {currency:'USD',value:null}, management: {currency:'USD',value:null}, discount: {currency:'USD',value:null} },
    approvals: { prepared_by: '', reviewed_by: '', approved_by: '' },
    export_filename: '',
    fx_rate: null,
  };
  populateAll();
  loadExchangeRate();
  // Open All Projects tab on first load — no active project yet
  updateProjectBadge(null);
  document.querySelector('[href="#tab-all-projects"]')?.click();
  loadAllProjects();

  // Clear validation state when user types in customer field
  document.getElementById('proj_customer')?.addEventListener('input', function() {
    this.classList.remove('is-invalid');
  });
});

function populateAll() {
  appData.project = normalizeProject(appData.project || {});
  appData.business_units = normalizeBusinessUnits(appData.business_units || []);
  if (typeof appData.target_margin === 'number') {
    _targetMargin = appData.target_margin;
  }
  if (typeof appData.fx_rate === 'number' && appData.fx_rate > 0) {
    _usdToInr = appData.fx_rate;
    const inlineEl = document.getElementById('fx_rate_inline');
    if (inlineEl) inlineEl.value = _usdToInr.toFixed(2);
  }
  populateProject();
  renderResources();
  renderRateCard();
  renderReleases();
  renderPnlRoles();
  renderCatalogList();
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
  setVal('proj_status', p.status);
  setVal('proj_stage', p.stage);
  setVal('proj_priority', p.priority);
  setVal('proj_owner', p.project_owner);
  renderBusinessUnitOptions(p.business_unit);
  setVal('proj_account_manager', p.account_manager);
  setVal('proj_sales_spoc', p.sales_spoc);
  setVal('proj_delivery_manager', p.delivery_manager);
  setVal('proj_technical_lead', p.technical_lead);
  setVal('proj_start_date', p.expected_start_date);
  setVal('proj_end_date', p.expected_end_date);
  setVal('proj_opportunity_id', p.opportunity_id);
  setVal('proj_type', p.project_type);
  setVal('proj_industry', p.industry);
  setVal('proj_delivery_model', p.delivery_model);
  setVal('proj_billing_type', p.billing_type);
  setVal('proj_currency', p.currency);
  setVal('proj_discount_pct', p.discount_pct ?? '');
  setVal('proj_travel_cost', p.travel_cost ?? '');
  setVal('proj_infra_cost', p.infra_cost ?? '');
  setVal('proj_third_party_cost', p.third_party_cost ?? '');
  setVal('proj_internal_notes', p.internal_notes);
  setVal('proj_risks', p.risks);
  setVal('proj_dependencies', p.dependencies);
  setVal('proj_next_action', p.next_action);
  setVal('proj_follow_up_date', p.next_follow_up_date);

  bindProjectFieldListeners([
    'proj_company','proj_customer','proj_location','proj_reference','proj_proposal_date',
    'proj_first_touch','proj_description','proj_partner','proj_payment_terms','proj_duration',
    'proj_status','proj_stage','proj_priority','proj_owner','proj_business_unit','proj_account_manager',
    'proj_sales_spoc','proj_delivery_manager','proj_technical_lead','proj_start_date',
    'proj_end_date','proj_opportunity_id','proj_type','proj_industry','proj_delivery_model',
    'proj_billing_type','proj_currency','proj_discount_pct','proj_travel_cost',
    'proj_infra_cost','proj_third_party_cost','proj_internal_notes','proj_risks',
    'proj_dependencies','proj_next_action','proj_follow_up_date'
  ]);
}

function renderBusinessUnitOptions(currentValue = '') {
  const el = document.getElementById('proj_business_unit');
  if (!el) return;
  appData.business_units = normalizeBusinessUnits(appData.business_units || []);
  const units = currentValue && !appData.business_units.includes(currentValue)
    ? normalizeBusinessUnits([...appData.business_units, currentValue])
    : appData.business_units;
  el.innerHTML = '<option value="">Select business unit…</option>'
    + units.map(unit =>
      `<option value="${esc(unit)}" ${unit === currentValue ? 'selected' : ''}>${esc(unit)}</option>`
    ).join('');
}

function addBusinessUnit() {
  const name = prompt('Enter a new business unit name:');
  const trimmed = String(name || '').trim();
  if (!trimmed) return;
  const existing = normalizeBusinessUnits(appData.business_units || []);
  const present = existing.find(unit => unit.toLowerCase() === trimmed.toLowerCase());
  appData.business_units = normalizeBusinessUnits(present ? existing : [...existing, trimmed]);
  renderBusinessUnitOptions(present || trimmed);
  collectProject();
  showToast(`Business unit "${present || trimmed}" ${present ? 'selected' : 'added'}`, 'success');
}

function bindProjectFieldListeners(ids) {
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (!el || el.dataset.boundProjectField === '1') return;
    const handler = () => {
      collectProject();
      updateSummary();
      updateFilenamePreview();
    };
    el.addEventListener('input', handler);
    el.addEventListener('change', handler);
    el.dataset.boundProjectField = '1';
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
    placeholder: '',
    allowEmptyOption: true,
    maxOptions: 250,
    onChange() { collectProject(); updateFilenamePreview(); }
  });

  if (currentValue) locationSelect.setValue(currentValue, true);
}

function collectProject() {
  appData.project = normalizeProject({
    company: getVal('proj_company'),
    customer: getVal('proj_customer'),
    location: locationSelect ? (locationSelect.getValue() || '') : getVal('proj_location'),
    reference: getVal('proj_reference'),
    proposal_date: getVal('proj_proposal_date'),
    customer_first_touch_point: getVal('proj_first_touch'),
    project_description: getVal('proj_description'),
    partner: getVal('proj_partner'),
    payment_terms: getVal('proj_payment_terms'),
    duration_months: parseFloat(getVal('proj_duration')) || null,
    status: getVal('proj_status'),
    stage: getVal('proj_stage'),
    priority: getVal('proj_priority'),
    project_owner: getVal('proj_owner'),
    business_unit: getVal('proj_business_unit'),
    account_manager: getVal('proj_account_manager'),
    sales_spoc: getVal('proj_sales_spoc'),
    delivery_manager: getVal('proj_delivery_manager'),
    technical_lead: getVal('proj_technical_lead'),
    expected_start_date: getVal('proj_start_date'),
    expected_end_date: getVal('proj_end_date'),
    opportunity_id: getVal('proj_opportunity_id'),
    project_type: getVal('proj_type'),
    industry: getVal('proj_industry'),
    delivery_model: getVal('proj_delivery_model'),
    billing_type: getVal('proj_billing_type'),
    currency: getVal('proj_currency'),
    discount_pct: parseFloat(getVal('proj_discount_pct')) || null,
    travel_cost: parseFloat(getVal('proj_travel_cost')) || null,
    infra_cost: parseFloat(getVal('proj_infra_cost')) || null,
    third_party_cost: parseFloat(getVal('proj_third_party_cost')) || null,
    internal_notes: getVal('proj_internal_notes'),
    risks: getVal('proj_risks'),
    dependencies: getVal('proj_dependencies'),
    next_action: getVal('proj_next_action'),
    next_follow_up_date: getVal('proj_follow_up_date'),
  });
}

// ============================================================
// SUMMARY CALCULATIONS
// ============================================================
function updateSummary() {
  const resources = appData.resources || [];

  let inputCost = 0;
  resources.forEach(r => {
    inputCost += (r.hours || 0) * _getRateForResource(r);
  });
  const divisor  = 1 - _targetMargin;
  const sellCost = inputCost > 0 ? inputCost / divisor : 0;
  const markup   = sellCost - inputCost;
  const margin   = sellCost > 0 ? markup / sellCost : _targetMargin;

  document.getElementById('sum_input_cost').textContent = fmtMoney(inputCost);
  document.getElementById('sum_sell_cost').textContent  = fmtMoney(sellCost);
  document.getElementById('sum_markup').textContent     = fmtMoney(markup);
  document.getElementById('sum_margin').textContent     = (margin * 100).toFixed(1) + '%';

  // INR display
  const inrEl = document.getElementById('sum_inr_rate');
  if (inrEl) inrEl.textContent = _usdToInr ? `₹${_usdToInr.toFixed(2)}` : '—';
}

function toggleMarginEdit() {
  const row = document.getElementById('margin-edit-row');
  const isHidden = row.classList.contains('d-none');
  row.classList.toggle('d-none');
  if (isHidden) {
    const inp = document.getElementById('target_margin_input');
    inp.value = (_targetMargin * 100).toFixed(0);
    inp.focus();
  }
}

function applyMargin() {
  const val = parseFloat(document.getElementById('target_margin_input').value);
  if (isNaN(val) || val <= 0 || val >= 100) { showToast('Enter a valid % between 1 and 99', 'danger'); return; }
  _targetMargin = val / 100;
  document.getElementById('margin-edit-row').classList.add('d-none');
  updateSummary();
  showToast(`Gross margin target set to ${val.toFixed(1)}%`, 'success');
}

function toggleFxEdit() {
  const row = document.getElementById('fx-edit-row');
  const isHidden = row.classList.contains('d-none');
  row.classList.toggle('d-none');
  if (isHidden) {
    const inp = document.getElementById('fx_rate_input');
    inp.value = _usdToInr ? _usdToInr.toFixed(2) : '';
    inp.focus();
  }
}

function applyFxRate() {
  const val = parseFloat(document.getElementById('fx_rate_input').value);
  if (isNaN(val) || val <= 0) { showToast('Enter a valid exchange rate', 'danger'); return; }
  _usdToInr = val;
  appData.fx_rate = val;
  document.getElementById('fx-edit-row').classList.add('d-none');
  const inlineEl = document.getElementById('fx_rate_inline');
  if (inlineEl) inlineEl.value = val.toFixed(2);
  renderRateCard();
  updateSummary();
  showToast(`USD → INR set to ₹${val.toFixed(2)}`, 'success');
}

// ============================================================
// RESOURCES
// ============================================================
function renderResources() {
  const resources = appData.resources || [];
  const levels    = (appData.rate_card || []).map(r => r.level);
  const catalog   = appData.role_catalog || [];

  const tbody = document.getElementById('resources-tbody');
  tbody.innerHTML = '';

  let totalHours = 0, totalCost = 0;

  resources.forEach((res, i) => {
    const rate = _getRateForResource(res);
    const cost = (res.hours || 0) * rate;
    totalHours += (res.hours || 0);
    totalCost  += cost;

    // Determine saved group for this resource
    const savedGroup = res.group ||
      catalog.find(g => g.roles.includes(res.role))?.group ||
      (catalog[0]?.group || '');

    const groupOpts = catalog.map(g =>
      `<option value="${esc(g.group)}" ${g.group === savedGroup ? 'selected' : ''}>${esc(g.group)}</option>`
    ).join('');

    // Roles for the current group
    const groupRoles = catalog.find(g => g.group === savedGroup)?.roles || [];
    const roleOpts = groupRoles.map(r =>
      `<option value="${esc(r)}" ${r === res.role ? 'selected' : ''}>${esc(r)}</option>`
    ).join('');

    const levelOpts = levels.map(l =>
      `<option value="${l}" ${l === res.level ? 'selected' : ''}>${l}</option>`
    ).join('');

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="text-center text-muted small">${i + 1}</td>
      <td>
        <select class="form-select form-select-sm" id="res_group_${i}"
          onchange="onResGroupChange(${i}, this.value)">
          ${groupOpts}
        </select>
      </td>
      <td>
        <select class="form-select form-select-sm" id="res_role_${i}"
          onchange="appData.resources[${i}].role=this.value; updateSummary()">
          ${roleOpts}
        </select>
      </td>
      <td>
        <select class="form-select form-select-sm"
          onchange="appData.resources[${i}].level=this.value; renderResources(); updateSummary();">
          ${levelOpts}
        </select>
      </td>
      <td><input type="number" class="form-control form-control-sm" value="${res.hours ?? ''}" min="0"
          oninput="updateResourceCost(${i}, this.value)"/></td>
      <td class="text-end fw-bold rate-cell" id="res_rate_${i}">$${rate.toFixed(2)}</td>
      <td class="text-end fw-semibold" id="res_cost_${i}">${fmtMoney(cost)}</td>
      <td class="text-end text-muted small" id="res_cost_inr_${i}">${_usdToInr ? '₹' + Math.round(cost * _usdToInr).toLocaleString('en-IN') : ''}</td>
      <td class="text-center">
        <button class="btn btn-outline-danger btn-icon" onclick="removeResource(${i})" title="Remove">
          <i class="bi bi-trash3"></i>
        </button>
      </td>`;
    tbody.appendChild(tr);
  });

  document.getElementById('tot_hours').textContent = totalHours;
  document.getElementById('tot_cost').textContent  = fmtMoney(totalCost);
  const totInrEl = document.getElementById('tot_cost_inr');
  if (totInrEl) totInrEl.textContent = _usdToInr ? '₹' + Math.round(totalCost * _usdToInr).toLocaleString('en-IN') : '';
}

function updateResourceCost(i, hoursVal) {
  const hours = parseFloat(hoursVal) || 0;
  appData.resources[i].hours = hours;

  const rate = _getRateForResource(appData.resources[i]);
  const cost = hours * rate;

  const costEl = document.getElementById(`res_cost_${i}`);
  if (costEl) costEl.textContent = fmtMoney(cost);
  const inrEl = document.getElementById(`res_cost_inr_${i}`);
  if (inrEl) inrEl.textContent = _usdToInr ? '₹' + Math.round(cost * _usdToInr).toLocaleString('en-IN') : '';

  let totalHours = 0, totalCost = 0;
  (appData.resources || []).forEach(r => {
    totalHours += (r.hours || 0);
    totalCost  += (r.hours || 0) * _getRateForResource(r);
  });
  document.getElementById('tot_hours').textContent = totalHours;
  document.getElementById('tot_cost').textContent  = fmtMoney(totalCost);
  const totInrEl = document.getElementById('tot_cost_inr');
  if (totInrEl) totInrEl.textContent = _usdToInr ? '₹' + Math.round(totalCost * _usdToInr).toLocaleString('en-IN') : '';
  updateSummary();
}

function onResGroupChange(i, groupName) {
  const catalog = appData.role_catalog || [];
  const group   = catalog.find(g => g.group === groupName);
  const roles   = group?.roles || [];
  appData.resources[i].group = groupName;
  appData.resources[i].role  = roles[0] || '';

  // Repopulate role select
  const roleEl = document.getElementById(`res_role_${i}`);
  if (roleEl) {
    roleEl.innerHTML = roles.map(r =>
      `<option value="${esc(r)}">${esc(r)}</option>`
    ).join('');
  }
  // Re-compute rate & cost for this row (rate depends on group)
  const rate    = _getRateForResource(appData.resources[i]);
  const cost    = (appData.resources[i].hours || 0) * rate;
  const rateEl  = document.getElementById(`res_rate_${i}`);
  const costEl  = document.getElementById(`res_cost_${i}`);
  const inrEl   = document.getElementById(`res_cost_inr_${i}`);
  if (rateEl) rateEl.textContent = '$' + rate.toFixed(2);
  if (costEl) costEl.textContent = fmtMoney(cost);
  if (inrEl)  inrEl.textContent  = _usdToInr ? '₹' + Math.round(cost * _usdToInr).toLocaleString('en-IN') : '';
  updateSummary();
}

function addResource() {
  if (!appData.resources) appData.resources = [];
  const defaultLevel = appData.rate_card?.[0]?.level || 'L3';
  const firstGroup   = appData.role_catalog?.[0];
  appData.resources.push({
    id:    Date.now(),
    group: firstGroup?.group || '',
    role:  firstGroup?.roles?.[0] || '',
    level: defaultLevel,
    hours: 0
  });
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
function collectRateCard() {
  // Rates are updated in-place via setRate(); only need to sync level names
  const rows = document.querySelectorAll('#ratecard-tbody tr[data-rc-idx]');
  rows.forEach(row => {
    const i = parseInt(row.dataset.rcIdx);
    if (!appData.rate_card[i]) return;
    const levelInput = row.querySelector('input[type="text"]');
    if (levelInput) appData.rate_card[i].level = levelInput.value.trim();
  });
}

// ── Rate card helpers ─────────────────────────────────────────
function _getRate(rcItem, category) {
  /** Get rate from a rate_card item for a given category.
   *  Supports new {rates:{cat:val}} and old {rate:val} formats. */
  if (!rcItem) return 0;
  const rates = rcItem.rates;
  if (rates && typeof rates === 'object') {
    if (category && category in rates) return rates[category] || 0;
    const vals = Object.values(rates);
    return vals.length ? (vals[0] || 0) : 0;
  }
  return rcItem.rate || 0;  // backward compat
}

function _getRateForResource(res) {
  /** Look up the rate for a resource using its level + group. */
  const item = (appData.rate_card || []).find(r => r.level === res.level);
  return _getRate(item, res.group || '');
}

function setRate(levelIdx, value, category) {
  /** Store a category-specific rate on the rate_card item. */
  const item = appData.rate_card[levelIdx];
  if (!item) return;
  if (!item.rates || typeof item.rates !== 'object') {
    // Migrate old flat rate → per-category object, copying old rate to all existing categories
    item.rates = {};
    const oldRate = item.rate || 0;
    (appData.role_catalog || []).forEach(g => { item.rates[g.group] = oldRate; });
    delete item.rate;
  }
  item.rates[category] = parseFloat(value) || 0;
}

let _usdToInr = null;
let _currentPid = null;   // PID of the project currently loaded in the editor
let _targetMargin = 0.40; // default 40%

async function fetchExchangeRate() {
  const attempts = [
    async () => {
      const res = await fetch('/api/exchange-rate', { cache: 'no-store' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      const fx = await res.json();
      return Number(fx.usd_to_inr);
    },
    async () => {
      const res = await fetch('https://open.er-api.com/v6/latest/USD', { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const fx = await res.json();
      return Number(fx.rates?.INR);
    }
  ];

  let lastError = null;
  for (const attempt of attempts) {
    try {
      const rate = await attempt();
      if (Number.isFinite(rate) && rate > 0) return rate;
      throw new Error('Invalid exchange rate response');
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error('Could not fetch exchange rate');
}

async function loadExchangeRate() {
  const inlineEl = document.getElementById('fx_rate_inline');
  if (inlineEl) inlineEl.placeholder = 'Fetching…';
  try {
    _usdToInr = await fetchExchangeRate();
    appData.fx_rate = _usdToInr;
    if (inlineEl) inlineEl.value = _usdToInr.toFixed(2);
    renderRateCard();
    updateSummary();
    showToast(`Live USD → INR refreshed to ₹${_usdToInr.toFixed(2)}`, 'success');
  } catch (e) {
    if (inlineEl) inlineEl.placeholder = 'Unavailable — enter manually';
    showToast('Could not refresh INR rate right now. You can still enter it manually.', 'danger');
  }
}

function applyFxRateInline() {
  const val = parseFloat(document.getElementById('fx_rate_inline')?.value);
  if (isNaN(val) || val <= 0) { showToast('Enter a valid exchange rate', 'danger'); return; }
  _usdToInr = val;
  appData.fx_rate = val;
  renderRateCard();
  updateSummary();
  showToast(`USD → INR set to ₹${val.toFixed(2)}`, 'success');
}

function renderRateCard() {
  const rc      = appData.rate_card || [];
  const catalog = appData.role_catalog || [];
  const tbody   = document.getElementById('ratecard-tbody');
  const filterEl = document.getElementById('ratecard-category-filter');
  tbody.innerHTML = '';
  const showInr = _usdToInr !== null;

  // Sync category dropdown with current catalog
  if (filterEl) {
    const currentVal = filterEl.value;
    filterEl.innerHTML = catalog.map(g =>
      `<option value="${esc(g.group)}" ${g.group === currentVal ? 'selected' : ''}>${esc(g.group)}</option>`
    ).join('');
    if (!filterEl.value && catalog.length) filterEl.value = catalog[0].group;
  }

  const selectedCat = filterEl?.value || '';
  sortRateCard(selectedCat);

  rc.forEach((item, i) => {
    const rate    = _getRate(item, selectedCat);
    const inrVal  = showInr ? Math.round(rate * _usdToInr) : null;
    const inrCell = showInr ? `<td class="text-end text-muted small">₹${inrVal.toLocaleString('en-IN')}</td>` : '<td></td>';
    const tr = document.createElement('tr');
    tr.dataset.rcIdx = i;
    tr.innerHTML = `
      <td class="text-center text-muted small">${i + 1}</td>
      <td><input type="text" class="form-control form-control-sm" value="${esc(item.level)}"
          oninput="appData.rate_card[${i}].level=this.value; renderRateChart(); saveSettings();"/></td>
      <td><input type="number" class="form-control form-control-sm text-end" value="${rate}" min="0" step="0.5"
          oninput="setRate(${i},this.value,'${esc(selectedCat)}'); renderResources(); updateSummary(); renderRateChart();"/></td>
      ${inrCell}
      <td class="text-center">
        <button class="btn btn-outline-danger btn-icon" onclick="removeRateLevel(${i})" title="Remove">
          <i class="bi bi-trash3"></i>
        </button>
      </td>`;
    tbody.appendChild(tr);
  });

  renderRateChart();
}

function collectAllRates() {
  // Explicitly read every rate input from the DOM into appData before saving
  const cat = document.getElementById('ratecard-category-filter')?.value || '';
  document.querySelectorAll('#ratecard-tbody tr[data-rc-idx]').forEach(row => {
    const i = parseInt(row.dataset.rcIdx);
    if (!appData.rate_card[i]) return;
    const levelInput = row.querySelector('input[type="text"]');
    const rateInput  = row.querySelector('input[type="number"]');
    if (levelInput) appData.rate_card[i].level = levelInput.value.trim();
    if (rateInput)  setRate(i, rateInput.value, cat);
  });
}

async function saveSettings() {
  const res = await fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      rate_card:    appData.rate_card,
      role_catalog: appData.role_catalog
    })
  });
  if (!res.ok) showToast('Save failed — please try again', 'danger');
}

function sortRateCard(category) {
  const cat = category || document.getElementById('ratecard-category-filter')?.value || '';
  appData.rate_card.sort((a, b) => _getRate(a, cat) - _getRate(b, cat));
}

function addRateLevel() {
  if (!appData.rate_card) appData.rate_card = [];
  const nextNum = appData.rate_card.length + 1;
  // Build rates object with 0 for every catalog category
  const rates = {};
  (appData.role_catalog || []).forEach(g => { rates[g.group] = 0; });
  appData.rate_card.push({ level: `L${nextNum}`, rates });
  renderRateCard();
  saveSettings();
}

function removeRateLevel(i) {
  appData.rate_card.splice(i, 1);
  renderRateCard();
  renderResources();
  updateSummary();
  saveSettings();
}

function renderRateChart() {
  const rc  = appData.rate_card || [];
  const cat = document.getElementById('ratecard-category-filter')?.value || '';
  const rates = rc.map(r => _getRate(r, cat));
  const maxRate = Math.max(...rates, 1);
  const area = document.getElementById('rate-chart-area');
  area.innerHTML = rc.map((item, i) => `
    <div class="rate-bar-row">
      <div class="rate-bar-label">${esc(item.level)}</div>
      <div class="rate-bar-track">
        <div class="rate-bar-fill" style="width:${(rates[i] / maxRate * 100).toFixed(1)}%"></div>
      </div>
      <div class="rate-bar-val">$${rates[i]}/hr</div>
    </div>`).join('');
}

// ============================================================
// RELEASES
// ============================================================
function renderReleases() {
  const releases = appData.releases || [];
  const tbody = document.getElementById('releases-tbody');
  if (!tbody) return;
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
const _pnlRoleSelects = {}; // track TomSelect instances by row index

function allCatalogRoles() {
  return (appData.role_catalog || []).flatMap(g =>
    g.roles.map(r => ({ value: r, text: r, group: g.group }))
  );
}

function renderPnlRoles() {
  // Destroy existing TomSelect instances
  Object.values(_pnlRoleSelects).forEach(ts => { try { ts.destroy(); } catch(e){} });
  Object.keys(_pnlRoleSelects).forEach(k => delete _pnlRoleSelects[k]);

  const roles = appData.pnl_roles || [];
  const tbody = document.getElementById('pnl-roles-tbody');
  if (!tbody) return;

  roles.forEach((role, i) => {
    const selectId = `pnl_role_sel_${i}`;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="text-center text-muted small">${i + 1}</td>
      <td><select id="${selectId}"></select></td>
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

    // Build grouped options
    const groups = {};
    allCatalogRoles().forEach(r => {
      if (!groups[r.group]) groups[r.group] = [];
      groups[r.group].push({ value: r.value, text: r.text });
    });
    const optGroups = Object.entries(groups).map(([label, items]) => ({ label, options: items }));

    const ts = new TomSelect(`#${selectId}`, {
      options: allCatalogRoles(),
      optgroups: optGroups,
      optgroupField: 'group',
      labelField: 'text',
      valueField: 'value',
      searchField: 'text',
      create(input) {
        // Add new role to catalog under Custom group
        addRoleToCatalog(input, 'Custom');
        return { value: input, text: input, group: 'Custom' };
      },
      placeholder: 'Search or type new role…',
      onChange(val) { appData.pnl_roles[i].name = val; }
    });

    if (role.name) ts.setValue(role.name, true);
    _pnlRoleSelects[i] = ts;
  });

  renderCatalogList();
}

function addPnlRole() {
  if (!appData.pnl_roles) appData.pnl_roles = [];
  const first = allCatalogRoles()[0];
  appData.pnl_roles.push({
    id: Date.now(),
    name: first ? first.value : '',
    partner: appData.project?.partner || '',
    payment_terms: appData.project?.payment_terms || ''
  });
  renderPnlRoles();
}

function removePnlRole(i) {
  appData.pnl_roles.splice(i, 1);
  renderPnlRoles();
}

// ============================================================
// ROLE CATALOG MANAGEMENT
// ============================================================
function addRoleToCatalog(roleName, groupName) {
  roleName = roleName.trim();
  if (!roleName) return;
  if (!appData.role_catalog) appData.role_catalog = [];
  let group = appData.role_catalog.find(g => g.group === groupName);
  if (!group) {
    group = { group: groupName, roles: [] };
    appData.role_catalog.push(group);
    // Keep custom group select in sync
    const sel = document.getElementById('new_catalog_group');
    if (sel && ![...sel.options].some(o => o.value === groupName)) {
      const opt = document.createElement('option');
      opt.value = groupName; opt.textContent = groupName;
      sel.appendChild(opt);
    }
  }
  if (!group.roles.includes(roleName)) {
    group.roles.push(roleName);
    renderCatalogList();
  }
}

function addToCatalog() {
  const name = document.getElementById('new_catalog_role').value.trim();
  const group = document.getElementById('new_catalog_group').value;
  if (!name) { showToast('Enter a role name', 'danger'); return; }
  addRoleToCatalog(name, group);
  document.getElementById('new_catalog_role').value = '';
  renderPnlRoles();
  saveSettings();
  showToast(`Added "${name}" to catalog`, 'success');
}

function removeFromCatalog(groupName, roleName) {
  const group = (appData.role_catalog || []).find(g => g.group === groupName);
  if (group) {
    group.roles = group.roles.filter(r => r !== roleName);
    renderPnlRoles();
    saveSettings();
  }
}

function refreshGroupDropdown() {
  const sel = document.getElementById('new_catalog_group');
  if (!sel) return;
  const current = sel.value;
  const groups = (appData.role_catalog || []).map(g => g.group);
  sel.innerHTML = groups.map(g =>
    `<option value="${esc(g)}" ${g === current ? 'selected' : ''}>${esc(g)}</option>`
  ).join('');
}

function addCatalogCategory() {
  const input = document.getElementById('new_catalog_category');
  const name = input.value.trim();
  if (!name) { showToast('Enter a category name', 'danger'); return; }
  if (!appData.role_catalog) appData.role_catalog = [];
  if (appData.role_catalog.find(g => g.group === name)) {
    showToast('Category already exists', 'warning'); return;
  }
  appData.role_catalog.push({ group: name, roles: [] });
  // Add 0-rate slot for new category in every existing rate card level
  (appData.rate_card || []).forEach(item => {
    if (!item.rates || typeof item.rates !== 'object') {
      item.rates = {};
      const oldRate = item.rate || 0;
      (appData.role_catalog || []).forEach(g => { item.rates[g.group] = item.rates[g.group] ?? oldRate; });
      delete item.rate;
    }
    if (!(name in item.rates)) item.rates[name] = 0;
  });
  input.value = '';
  refreshGroupDropdown();
  renderCatalogList();
  saveSettings();
  showToast(`Category "${name}" added`, 'success');
}

function renderCatalogList() {
  const el = document.getElementById('catalog-list');
  if (!el) return;
  refreshGroupDropdown();
  renderRateCard(); // keep category filter in sync
  const catalog = appData.role_catalog || [];
  el.innerHTML = catalog.map(g => `
    <div class="mb-3">
      <div class="d-flex justify-content-between align-items-center mb-1">
        <span class="fw-semibold text-uppercase small" style="color:var(--ax-mid);letter-spacing:.5px">${esc(g.group)}</span>
        <button class="btn btn-link btn-sm p-0 text-danger" style="font-size:11px"
          onclick="removeCatalogCategory('${esc(g.group)}')" title="Delete category">
          <i class="bi bi-trash3"></i>
        </button>
      </div>
      ${g.roles.map(r => `
        <div class="d-flex justify-content-between align-items-center px-2 py-1 rounded mb-1"
             style="background:var(--ax-tint2);">
          <span>${esc(r)}</span>
          <button class="btn btn-link btn-sm p-0 text-danger" style="font-size:12px"
            onclick="removeFromCatalog('${esc(g.group)}','${esc(r)}')">
            <i class="bi bi-x-circle"></i>
          </button>
        </div>`).join('')}
    </div>`).join('');
}

function removeCatalogCategory(groupName) {
  const g = (appData.role_catalog || []).find(g => g.group === groupName);
  if (g && g.roles.length > 0) {
    if (!confirm(`Delete category "${groupName}" and its ${g.roles.length} role(s)?`)) return;
  }
  appData.role_catalog = (appData.role_catalog || []).filter(g => g.group !== groupName);
  refreshGroupDropdown();
  renderCatalogList();
  renderResources();
  saveSettings();
  showToast(`Category "${groupName}" deleted`, 'success');
}

// ============================================================
// EXCEL IMPORT
// ============================================================
function _importProgressOverlay() {
  const el = document.createElement('div');
  el.id = 'import-overlay';
  el.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;display:flex;align-items:center;justify-content:center';
  el.innerHTML = `
    <div class="card shadow-lg" style="min-width:340px;max-width:420px;padding:28px 32px">
      <div class="d-flex align-items-center mb-3 gap-2">
        <i class="bi bi-file-earmark-excel fs-4 text-success"></i>
        <h6 class="mb-0 fw-semibold">Importing Excel</h6>
      </div>
      <div class="progress mb-2" style="height:10px;border-radius:6px">
        <div id="imp-bar" class="progress-bar progress-bar-striped progress-bar-animated"
             style="width:0%;transition:width .3s ease;background:var(--ax-deep)"></div>
      </div>
      <div class="d-flex justify-content-between align-items-center">
        <small id="imp-status" class="text-muted">Preparing…</small>
        <small id="imp-pct" class="fw-semibold text-muted">0%</small>
      </div>
    </div>`;
  document.body.appendChild(el);
  return {
    remove: () => el.remove(),
    set: (pct, msg) => {
      document.getElementById('imp-bar').style.width = pct + '%';
      document.getElementById('imp-status').textContent = msg;
      document.getElementById('imp-pct').textContent = pct + '%';
    },
    done: (msg) => {
      const bar = document.getElementById('imp-bar');
      bar.style.width = '100%';
      bar.classList.remove('progress-bar-animated');
      bar.style.background = '#198754';
      document.getElementById('imp-status').textContent = msg;
      document.getElementById('imp-pct').textContent = '100%';
    }
  };
}

function importExcel(input) {
  const file = input.files[0];
  if (!file) return;
  input.value = '';

  const ui = _importProgressOverlay();
  const fd = new FormData();
  fd.append('file', file);

  const xhr = new XMLHttpRequest();

  // Upload phase → 0–75%
  xhr.upload.onprogress = (e) => {
    if (!e.lengthComputable) return;
    const pct = Math.round((e.loaded / e.total) * 75);
    ui.set(pct, `Uploading… (${(e.loaded/1024).toFixed(0)} KB / ${(e.total/1024).toFixed(0)} KB)`);
  };

  // Upload done, server now processing → 75–95% animated
  xhr.upload.onload = () => ui.set(85, 'Analysing sheet data…');

  xhr.onload = () => {
    let json;
    try { json = JSON.parse(xhr.responseText); } catch (e) {
      ui.remove();
      showToast('Import error: invalid server response', 'danger');
      return;
    }
    if (xhr.status !== 200) {
      ui.remove();
      showToast('Import failed: ' + (json.error || xhr.statusText), 'danger');
      return;
    }

    ui.done('Import complete!');

    // Brief pause so user sees 100% before we switch views
    setTimeout(() => {
      ui.remove();
      const warn = json.warnings?.length ? ` (${json.warnings.join('; ')})` : '';
      document.querySelector('[href="#tab-all-projects"]')?.click();
      loadAllProjects();
      showToast(`Imported ${json.imported_count || 0} projects${warn}`, 'success');
    }, 600);
  };

  xhr.onerror = () => { ui.remove(); showToast('Import error: network failure', 'danger'); };
  xhr.ontimeout = () => { ui.remove(); showToast('Import error: request timed out', 'danger'); };

  xhr.open('POST', '/api/import-excel');
  xhr.send(fd);
}

// ============================================================
// PROJECTS — save / load / delete
// ============================================================
async function loadDashboard() {
  const container = document.getElementById('dashboard-container');
  if (!container) return;
  container.innerHTML = `<div class="text-center text-muted py-5"><i class="bi bi-hourglass-split me-1"></i>Loading…</div>`;

  let data;
  try {
    const res = await fetch('/api/dashboard', { cache: 'no-store' });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    data = await res.json();
  } catch (e) {
    container.innerHTML = `<div class="text-center text-danger py-5"><i class="bi bi-exclamation-triangle me-1"></i>Could not load analytics: ${e.message}</div>`;
    return;
  }

  const k = data.kpis || {};
  const fmtMoney = v => {
    const n = Number(v || 0);
    if (n >= 1_000_000) return '$' + (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return '$' + (n / 1_000).toFixed(1) + 'K';
    return '$' + n.toLocaleString('en-US', { maximumFractionDigits: 0 });
  };
  const fmtNum = v => Number(v || 0).toLocaleString('en-US', { maximumFractionDigits: 1 });
  const fmtPct = v => ((Number(v || 0)) * 100).toFixed(1) + '%';
  const marginColor = m => {
    const p = Number(m || 0) * 100;
    return p >= 35 ? '#16a34a' : p >= 20 ? '#d97706' : '#dc2626';
  };

  container.innerHTML = `
    <!-- KPI Cards -->
    <div class="row g-3 mb-4">
      <div class="col-6 col-md-3">
        <div class="db-kpi">
          <div class="db-kpi-icon" style="background:#ede9fe;color:#6d28d9"><i class="bi bi-folder2-open"></i></div>
          <div class="db-kpi-body">
            <div class="db-kpi-label">Total Projects</div>
            <div class="db-kpi-value">${fmtNum(k.projects)}</div>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="db-kpi">
          <div class="db-kpi-icon" style="background:#dcfce7;color:#16a34a"><i class="bi bi-cash-stack"></i></div>
          <div class="db-kpi-body">
            <div class="db-kpi-label">Portfolio Revenue</div>
            <div class="db-kpi-value">${fmtMoney(k.revenue)}</div>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="db-kpi">
          <div class="db-kpi-icon" style="background:#fef3c7;color:#d97706"><i class="bi bi-coin"></i></div>
          <div class="db-kpi-body">
            <div class="db-kpi-label">Input Cost</div>
            <div class="db-kpi-value">${fmtMoney(k.input_cost)}</div>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="db-kpi">
          <div class="db-kpi-icon" style="background:#fce7f3;color:#db2777"><i class="bi bi-speedometer2"></i></div>
          <div class="db-kpi-body">
            <div class="db-kpi-label">Avg Gross Margin</div>
            <div class="db-kpi-value" style="color:${marginColor(k.avg_margin)}">${fmtPct(k.avg_margin)}</div>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-4">
        <div class="db-kpi db-kpi-subtle">
          <div class="db-kpi-icon" style="background:#e0f2fe;color:#0284c7"><i class="bi bi-people"></i></div>
          <div class="db-kpi-body">
            <div class="db-kpi-label">Total Resources</div>
            <div class="db-kpi-value">${fmtNum(k.resources)}</div>
          </div>
        </div>
      </div>
      <div class="col-6 col-md-4">
        <div class="db-kpi db-kpi-subtle">
          <div class="db-kpi-icon" style="background:#f0fdf4;color:#15803d"><i class="bi bi-clock-history"></i></div>
          <div class="db-kpi-body">
            <div class="db-kpi-label">Total Hours</div>
            <div class="db-kpi-value">${fmtNum(k.hours)}</div>
          </div>
        </div>
      </div>
      <div class="col-12 col-md-4">
        <div class="db-kpi db-kpi-subtle">
          <div class="db-kpi-icon" style="background:#f5f3ff;color:#7c3aed"><i class="bi bi-person-badge"></i></div>
          <div class="db-kpi-body">
            <div class="db-kpi-label">Avg Resources / Project</div>
            <div class="db-kpi-value">${fmtNum(k.avg_resources_per_project)}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Status + Stage -->
    <div class="row g-3 mb-4">
      <div class="col-lg-5">
        <div class="db-card h-100">
          <div class="db-card-header"><i class="bi bi-circle-half me-2"></i>Project Status</div>
          <div class="db-card-body">${renderStatusBars(data.status_breakdown)}</div>
        </div>
      </div>
      <div class="col-lg-7">
        <div class="db-card h-100">
          <div class="db-card-header"><i class="bi bi-funnel me-2"></i>Pipeline Stages</div>
          <div class="db-card-body">${renderStagePipeline(data.stage_breakdown)}</div>
        </div>
      </div>
    </div>

    <!-- Margin + Priority + BU -->
    <div class="row g-3 mb-4">
      <div class="col-lg-4">
        <div class="db-card h-100">
          <div class="db-card-header"><i class="bi bi-bar-chart me-2"></i>Margin Distribution</div>
          <div class="db-card-body">${renderMarginBars(data.margin_buckets)}</div>
        </div>
      </div>
      <div class="col-lg-4">
        <div class="db-card h-100">
          <div class="db-card-header"><i class="bi bi-flag me-2"></i>Priority Breakdown</div>
          <div class="db-card-body">${renderPriorityBars(data.priority_breakdown)}</div>
        </div>
      </div>
      <div class="col-lg-4">
        <div class="db-card h-100">
          <div class="db-card-header"><i class="bi bi-grid me-2"></i>Business Units</div>
          <div class="db-card-body">${renderAnalyticsBars(data.bu_breakdown, 'projects')}</div>
        </div>
      </div>
    </div>

    <!-- Customers + Groups + Owner -->
    <div class="row g-3 mb-4">
      <div class="col-lg-4">
        <div class="db-card h-100">
          <div class="db-card-header"><i class="bi bi-building me-2"></i>Top Customers <span class="db-card-sub">by revenue</span></div>
          <div class="db-card-body">${renderAnalyticsBars(data.top_customers, 'revenue')}</div>
        </div>
      </div>
      <div class="col-lg-4">
        <div class="db-card h-100">
          <div class="db-card-header"><i class="bi bi-diagram-3 me-2"></i>Resource Groups</div>
          <div class="db-card-body">${renderAnalyticsBars(data.top_groups_by_hours, 'hours')}</div>
        </div>
      </div>
      <div class="col-lg-4">
        <div class="db-card h-100">
          <div class="db-card-header"><i class="bi bi-geo-alt me-2"></i>Top Locations</div>
          <div class="db-card-body">${renderAnalyticsBars(data.top_locations, 'projects')}</div>
        </div>
      </div>
    </div>

    <!-- Timeline -->
    <div class="row g-3">
      <div class="col-12">
        <div class="db-card">
          <div class="db-card-header"><i class="bi bi-calendar3 me-2"></i>Projects Saved Over Time</div>
          <div class="db-card-body">${renderAnalyticsTimeline(data.projects_by_month)}</div>
        </div>
      </div>
    </div>`;
}

const STATUS_COLORS = {
  'Won':        '#16a34a',
  'Active':     '#2563eb',
  'Submitted':  '#7c3aed',
  'Proposal':   '#0891b2',
  'Draft':      '#6b7280',
  'On Hold':    '#d97706',
  'Lost':       '#dc2626',
};
const PRIORITY_COLORS = {
  'Critical': '#dc2626',
  'High':     '#ea580c',
  'Medium':   '#d97706',
  'Low':      '#16a34a',
};
const MARGIN_COLORS = {
  'Below 20%': '#dc2626',
  '20–35%':    '#d97706',
  '35–50%':    '#2563eb',
  '50%+':      '#16a34a',
};

function renderStatusBars(items) {
  if (!Array.isArray(items) || !items.length)
    return `<div class="db-empty"><i class="bi bi-inbox"></i>No data yet</div>`;
  const total = items.reduce((s, i) => s + Number(i.value || 0), 0) || 1;
  const maxVal = Math.max(...items.map(i => Number(i.value || 0)), 1);
  return items.map(item => {
    const v = Number(item.value || 0);
    const color = STATUS_COLORS[item.label] || '#8b5cf6';
    const pct = Math.round((v / total) * 100);
    const width = Math.max((v / maxVal) * 100, v > 0 ? 6 : 0);
    return `
      <div class="db-status-row">
        <div class="db-status-dot" style="background:${color}"></div>
        <span class="db-status-label">${esc(item.label)}</span>
        <div class="db-status-track">
          <div class="db-status-fill" style="width:${width}%;background:${color}"></div>
        </div>
        <span class="db-status-count">${v}</span>
        <span class="db-status-pct">${pct}%</span>
      </div>`;
  }).join('');
}

function renderStagePipeline(items) {
  if (!Array.isArray(items) || !items.length)
    return `<div class="db-empty"><i class="bi bi-inbox"></i>No data yet</div>`;
  const maxVal = Math.max(...items.map(i => Number(i.value || 0)), 1);
  const palette = ['#6d28d9','#7c3aed','#8b5cf6','#a78bfa','#0891b2','#2563eb','#16a34a','#dc2626','#6b7280'];
  return items.map((item, idx) => {
    const v = Number(item.value || 0);
    const width = Math.max((v / maxVal) * 100, v > 0 ? 6 : 0);
    const color = palette[idx % palette.length];
    return `
      <div class="db-stage-row">
        <span class="db-stage-label">${esc(item.label)}</span>
        <div class="db-stage-track">
          <div class="db-stage-fill" style="width:${width}%;background:${color}">
            ${v > 0 ? `<span class="db-stage-val">${v}</span>` : ''}
          </div>
        </div>
      </div>`;
  }).join('');
}

function renderMarginBars(items) {
  if (!Array.isArray(items) || !items.length)
    return `<div class="db-empty"><i class="bi bi-inbox"></i>No data yet</div>`;
  const maxVal = Math.max(...items.map(i => Number(i.value || 0)), 1);
  return items.map(item => {
    const v = Number(item.value || 0);
    const color = MARGIN_COLORS[item.label] || '#8b5cf6';
    const width = Math.max((v / maxVal) * 100, v > 0 ? 6 : 0);
    return `
      <div class="db-bar-row">
        <div class="db-bar-head">
          <span class="db-bar-label" style="color:${color}">${esc(item.label)}</span>
          <span class="db-bar-val">${v} projects</span>
        </div>
        <div class="db-bar-track"><div class="db-bar-fill" style="width:${width}%;background:${color}"></div></div>
      </div>`;
  }).join('');
}

function renderPriorityBars(items) {
  if (!Array.isArray(items) || !items.length)
    return `<div class="db-empty"><i class="bi bi-inbox"></i>No data yet</div>`;
  const maxVal = Math.max(...items.map(i => Number(i.value || 0)), 1);
  return items.map(item => {
    const v = Number(item.value || 0);
    const color = PRIORITY_COLORS[item.label] || '#8b5cf6';
    const width = Math.max((v / maxVal) * 100, v > 0 ? 6 : 0);
    return `
      <div class="db-bar-row">
        <div class="db-bar-head">
          <span class="db-bar-label" style="color:${color}">${esc(item.label)}</span>
          <span class="db-bar-val">${v} projects</span>
        </div>
        <div class="db-bar-track"><div class="db-bar-fill" style="width:${width}%;background:${color}"></div></div>
      </div>`;
  }).join('');
}

function renderAnalyticsBars(items, unit = 'count') {
  if (!Array.isArray(items) || !items.length)
    return `<div class="db-empty"><i class="bi bi-inbox"></i>No data yet</div>`;
  const maxVal = Math.max(...items.map(i => Number(i.value || 0)), 1);
  const fmt = v => {
    const n = Number(v || 0);
    if (unit === 'hours') return n.toLocaleString('en-US', { maximumFractionDigits: 1 }) + ' hrs';
    if (unit === 'revenue') {
      if (n >= 1_000_000) return '$' + (n / 1_000_000).toFixed(1) + 'M';
      if (n >= 1_000) return '$' + (n / 1_000).toFixed(0) + 'K';
      return '$' + n.toLocaleString('en-US', { maximumFractionDigits: 0 });
    }
    return n.toLocaleString('en-US');
  };
  return items.map(item => {
    const v = Number(item.value || 0);
    const width = Math.max((v / maxVal) * 100, v > 0 ? 6 : 0);
    return `
      <div class="db-bar-row">
        <div class="db-bar-head">
          <span class="db-bar-label" title="${esc(item.label)}">${esc(item.label)}</span>
          <span class="db-bar-val">${fmt(v)}</span>
        </div>
        <div class="db-bar-track"><div class="db-bar-fill" style="width:${width}%"></div></div>
      </div>`;
  }).join('');
}

function renderAnalyticsTimeline(items) {
  if (!Array.isArray(items) || !items.length)
    return `<div class="db-empty"><i class="bi bi-inbox"></i>No saved project history yet</div>`;
  const maxVal = Math.max(...items.map(i => Number(i.value || 0)), 1);
  return `
    <div class="db-timeline">
      ${items.map(item => {
        const v = Number(item.value || 0);
        const h = Math.max((v / maxVal) * 100, v > 0 ? 8 : 0);
        const label = item.label.length === 7 ? item.label.slice(0, 4) + '\'' + item.label.slice(5) : esc(item.label);
        return `
          <div class="db-timeline-col">
            <div class="db-timeline-count">${v || ''}</div>
            <div class="db-timeline-wrap"><div class="db-timeline-bar" style="height:${h}%"></div></div>
            <div class="db-timeline-label">${label}</div>
          </div>`;
      }).join('')}
    </div>`;
}

const ALL_PROJECTS_COLUMNS_STORAGE_KEY = 'pnl.allProjects.visibleColumns';
const ALL_PROJECTS_DEFAULT_COLUMNS = [
  'customer',
  'project',
  'location',
  'duration',
  'proposal_date',
  'input_cost',
  'markup',
  'revenue',
  'gross_margin',
  'saved_at',
  'saved_by',
];
const ALL_PROJECTS_COLUMN_GROUPS = [
  { label: 'Basics',     keys: ['customer', 'project', 'reference', 'business_unit', 'location', 'duration', 'proposal_date', 'project_description', 'customer_first_touch_point'] },
  { label: 'Pipeline',   keys: ['status', 'stage', 'priority', 'project_owner', 'account_manager', 'sales_spoc', 'delivery_manager', 'technical_lead', 'expected_start_date', 'expected_end_date', 'next_follow_up_date', 'opportunity_id', 'next_action'] },
  { label: 'Commercial', keys: ['partner', 'project_type', 'industry', 'delivery_model', 'billing_type', 'currency', 'payment_terms'] },
  { label: 'Financial',  keys: ['resource_count', 'total_hours', 'avg_rate', 'input_cost', 'add_on_cost', 'travel_cost', 'infra_cost', 'third_party_cost', 'discount_pct', 'markup', 'revenue', 'profit_amount', 'gross_margin'] },
  { label: 'Notes',      keys: ['internal_notes', 'risks', 'dependencies'] },
  { label: 'Audit',      keys: ['since_save', 'saved_at', 'saved_by'] },
];
let _allProjectsPickerOpen = false;
let _allProjectsDraftColumns = null;
let _allProjectsSort = null;
let _allProjectsSearch = null;
let _allProjectsSearchTimer = null;
let _allProjectsDraftDraggedColumn = null;
let _allProjectsListCache = null;
let _allProjectsFilters = { business_unit: [], location: [], partner: [], sales_spoc: [] };
let _allProjectsOpenFilter = null;

function getAllProjectsColumnDefs(formatters) {
  const { fmt, pct, pctNumber, num, shortDateTime, daysAgo } = formatters;
  return [
    { key: 'customer', label: 'Customer', headerClass: '', sortValue: p => p.customer || '', cell: p => `<td class="fw-semibold">${esc(p.customer || '')}</td>` },
    { key: 'project', label: 'Project', headerClass: '', sortValue: p => p.name || '', cell: p => `<td>${esc(p.name)}</td>` },
    { key: 'reference', label: 'Reference', headerClass: '', sortValue: p => p.reference || '', cell: p => `<td class="small">${esc(p.reference || '')}</td>` },
    { key: 'business_unit', label: 'Business Unit', headerClass: '', sortValue: p => p.business_unit || '', cell: p => `<td class="small">${esc(p.business_unit || '')}</td>` },
    {
      key: 'status',
      label: 'Status',
      headerClass: '',
      sortValue: p => p.status || '',
      cell: p => `<td><span class="badge text-bg-${p.status === 'Won' ? 'success' : p.status === 'Lost' ? 'danger' : p.status === 'On Hold' ? 'warning' : 'secondary'}">${esc(p.status || '')}</span></td>`
    },
    { key: 'stage', label: 'Stage', headerClass: '', sortValue: p => p.stage || '', cell: p => `<td class="small">${esc(p.stage || '')}</td>` },
    { key: 'priority', label: 'Priority', headerClass: '', sortValue: p => p.priority || '', cell: p => `<td class="small">${esc(p.priority || '')}</td>` },
    { key: 'project_owner', label: 'Owner', headerClass: '', sortValue: p => p.project_owner || '', cell: p => `<td class="small">${esc(p.project_owner || '')}</td>` },
    { key: 'account_manager', label: 'Account Manager', headerClass: '', sortValue: p => p.account_manager || '', cell: p => `<td class="small">${esc(p.account_manager || '')}</td>` },
    { key: 'sales_spoc', label: 'Sales SPOC', headerClass: '', sortValue: p => p.sales_spoc || '', cell: p => `<td class="small">${esc(p.sales_spoc || '')}</td>` },
    { key: 'delivery_manager', label: 'Delivery Manager', headerClass: '', sortValue: p => p.delivery_manager || '', cell: p => `<td class="small">${esc(p.delivery_manager || '')}</td>` },
    { key: 'location', label: 'Location', headerClass: '', sortValue: p => p.location || '', cell: p => `<td class="text-muted small">${esc(p.location || '')}</td>` },
    { key: 'duration', label: 'Duration', headerClass: 'text-center', sortValue: p => Number(p.duration || 0), cell: p => `<td class="text-center small">${p.duration ? p.duration + ' mo' : ''}</td>` },
    { key: 'proposal_date', label: 'Proposal Date', headerClass: '', sortValue: p => p.proposal_date || '', cell: p => `<td class="small text-muted">${esc(p.proposal_date || '')}</td>` },
    { key: 'expected_start_date', label: 'Start Date', headerClass: '', sortValue: p => p.expected_start_date || '', cell: p => `<td class="small text-muted">${esc(p.expected_start_date || '')}</td>` },
    { key: 'expected_end_date', label: 'End Date', headerClass: '', sortValue: p => p.expected_end_date || '', cell: p => `<td class="small text-muted">${esc(p.expected_end_date || '')}</td>` },
    { key: 'next_follow_up_date', label: 'Follow-Up', headerClass: '', sortValue: p => p.next_follow_up_date || '', cell: p => `<td class="small">${esc(p.next_follow_up_date || '')}</td>` },
    { key: 'opportunity_id', label: 'Opportunity ID', headerClass: '', sortValue: p => p.opportunity_id || '', cell: p => `<td class="small">${esc(p.opportunity_id || '')}</td>` },
    { key: 'partner', label: 'Partner', headerClass: '', sortValue: p => p.partner || '', cell: p => `<td class="small">${esc(p.partner || '')}</td>` },
    { key: 'project_type', label: 'Type', headerClass: '', sortValue: p => p.project_type || '', cell: p => `<td class="small">${esc(p.project_type || '')}</td>` },
    { key: 'industry', label: 'Industry', headerClass: '', sortValue: p => p.industry || '', cell: p => `<td class="small">${esc(p.industry || '')}</td>` },
    { key: 'delivery_model', label: 'Delivery', headerClass: '', sortValue: p => p.delivery_model || '', cell: p => `<td class="small">${esc(p.delivery_model || '')}</td>` },
    { key: 'billing_type', label: 'Billing', headerClass: '', sortValue: p => p.billing_type || '', cell: p => `<td class="small">${esc(p.billing_type || '')}</td>` },
    { key: 'currency', label: 'Currency', headerClass: '', sortValue: p => p.currency || '', cell: p => `<td class="small">${esc(p.currency || 'USD')}</td>` },
    { key: 'resource_count', label: 'Resources', headerClass: 'text-end', sortValue: p => Number(p.resource_count || 0), cell: p => `<td class="text-end small">${num(p.resource_count)}</td>` },
    { key: 'total_hours', label: 'Hours', headerClass: 'text-end', sortValue: p => Number(p.total_hours || 0), cell: p => `<td class="text-end small">${num(p.total_hours)}</td>` },
    { key: 'avg_rate', label: 'Avg Rate', headerClass: 'text-end', sortValue: p => Number(p.avg_rate || 0), cell: p => `<td class="text-end small">${p.avg_rate ? fmt(p.avg_rate) : ''}</td>` },
    { key: 'input_cost', label: 'Input Cost', headerClass: 'text-end', sortValue: p => Number(p.costs?.input_cost || 0), cell: p => `<td class="text-end small">${p.costs?.input_cost ? fmt(p.costs.input_cost) : ''}</td>` },
    { key: 'add_on_cost', label: 'Add-On Cost', headerClass: 'text-end', sortValue: p => Number(p.add_on_cost || 0), cell: p => `<td class="text-end small">${p.add_on_cost ? fmt(p.add_on_cost) : ''}</td>` },
    { key: 'discount_pct', label: 'Discount %', headerClass: 'text-end', sortValue: p => Number(p.discount_pct || 0), cell: p => `<td class="text-end small">${p.discount_pct ? pctNumber(p.discount_pct) : ''}</td>` },
    { key: 'markup', label: 'MarkUp', headerClass: 'text-end', sortValue: p => Number(p.costs?.markup || 0), cell: p => `<td class="text-end small">${p.costs?.markup ? fmt(p.costs.markup) : ''}</td>` },
    { key: 'revenue', label: 'Revenue', headerClass: 'text-end', sortValue: p => Number(p.costs?.sell_cost || 0), cell: p => `<td class="text-end small">${p.costs?.sell_cost ? fmt(p.costs.sell_cost) : ''}</td>` },
    { key: 'profit_amount', label: 'Profit', headerClass: 'text-end', sortValue: p => Number(p.profit_amount || 0), cell: p => `<td class="text-end small">${p.profit_amount ? fmt(p.profit_amount) : ''}</td>` },
    {
      key: 'gross_margin',
      label: 'Gross Margin',
      headerClass: 'text-end',
      sortValue: p => Number(p.costs?.gross_margin || 0),
      cell: p => {
        const margin = (p.costs?.gross_margin || 0) * 100;
        const marginColor = margin >= 35 ? 'text-success fw-bold' : margin >= 20 ? 'text-warning fw-bold' : 'text-danger fw-bold';
        return `<td class="text-end small ${p.costs?.gross_margin ? marginColor : ''}">${p.costs?.gross_margin ? pct(p.costs.gross_margin) : ''}</td>`;
      }
    },
    { key: 'technical_lead',             label: 'Technical Lead',    headerClass: '', sortValue: p => p.technical_lead || '',             cell: p => `<td class="small">${esc(p.technical_lead || '')}</td>` },
    { key: 'payment_terms',              label: 'Payment Terms',     headerClass: '', sortValue: p => p.payment_terms || '',              cell: p => `<td class="small">${esc(p.payment_terms || '')}</td>` },
    { key: 'customer_first_touch_point', label: 'First Touch',       headerClass: '', sortValue: p => p.customer_first_touch_point || '', cell: p => `<td class="small">${esc(p.customer_first_touch_point || '')}</td>` },
    { key: 'project_description',        label: 'Description',       headerClass: '', sortValue: p => p.project_description || '',        cell: p => `<td class="small" style="max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(p.project_description || '')}">${esc(p.project_description || '')}</td>` },
    { key: 'next_action',                label: 'Next Action',       headerClass: '', sortValue: p => p.next_action || '',                cell: p => `<td class="small" style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(p.next_action || '')}">${esc(p.next_action || '')}</td>` },
    { key: 'internal_notes',             label: 'Internal Notes',    headerClass: '', sortValue: p => p.internal_notes || '',             cell: p => `<td class="small" style="max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(p.internal_notes || '')}">${esc(p.internal_notes || '')}</td>` },
    { key: 'risks',                      label: 'Risks',             headerClass: '', sortValue: p => p.risks || '',                      cell: p => `<td class="small" style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(p.risks || '')}">${esc(p.risks || '')}</td>` },
    { key: 'dependencies',               label: 'Dependencies',      headerClass: '', sortValue: p => p.dependencies || '',               cell: p => `<td class="small" style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(p.dependencies || '')}">${esc(p.dependencies || '')}</td>` },
    { key: 'travel_cost',      label: 'Travel Cost',      headerClass: 'text-end', sortValue: p => Number(p.travel_cost || 0),      cell: p => `<td class="text-end small">${p.travel_cost ? fmt(p.travel_cost) : ''}</td>` },
    { key: 'infra_cost',       label: 'Infra Cost',       headerClass: 'text-end', sortValue: p => Number(p.infra_cost || 0),       cell: p => `<td class="text-end small">${p.infra_cost ? fmt(p.infra_cost) : ''}</td>` },
    { key: 'third_party_cost', label: '3rd Party Cost',   headerClass: 'text-end', sortValue: p => Number(p.third_party_cost || 0), cell: p => `<td class="text-end small">${p.third_party_cost ? fmt(p.third_party_cost) : ''}</td>` },
    { key: 'since_save', label: 'Since Save', headerClass: 'text-center', sortValue: p => p.saved_at || '', cell: p => `<td class="text-center small text-muted">${daysAgo(p.saved_at)}</td>` },
    { key: 'saved_at', label: 'Saved At', headerClass: '', sortValue: p => p.saved_at || '', cell: p => `<td class="small text-muted">${shortDateTime(p.saved_at)}</td>` },
    { key: 'saved_by', label: 'Saved By', headerClass: '', sortValue: p => p.saved_by || '', cell: p => `<td class="small text-muted">${esc(p.saved_by || '')}</td>` },
  ];
}

function loadVisibleAllProjectsColumns() {
  try {
    const raw = localStorage.getItem(ALL_PROJECTS_COLUMNS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (Array.isArray(parsed) && parsed.length) return parsed;
  } catch {}
  return [...ALL_PROJECTS_DEFAULT_COLUMNS];
}

function saveVisibleAllProjectsColumns(columns) {
  localStorage.setItem(ALL_PROJECTS_COLUMNS_STORAGE_KEY, JSON.stringify(columns));
}

function loadAllProjectsSort() {
  if (_allProjectsSort) return _allProjectsSort;
  try {
    const raw = localStorage.getItem(ALL_PROJECTS_SORT_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed?.key && parsed?.direction) {
      _allProjectsSort = parsed;
      return parsed;
    }
  } catch {}
  _allProjectsSort = { key: 'saved_at', direction: 'desc' };
  return _allProjectsSort;
}

function saveAllProjectsSort(sortState) {
  _allProjectsSort = sortState;
  localStorage.setItem(ALL_PROJECTS_SORT_STORAGE_KEY, JSON.stringify(sortState));
}

function loadAllProjectsSearch() {
  if (_allProjectsSearch !== null) return _allProjectsSearch;
  try {
    _allProjectsSearch = localStorage.getItem(ALL_PROJECTS_SEARCH_STORAGE_KEY) || '';
  } catch {
    _allProjectsSearch = '';
  }
  return _allProjectsSearch;
}

function saveAllProjectsSearch(value) {
  _allProjectsSearch = String(value || '');
  localStorage.setItem(ALL_PROJECTS_SEARCH_STORAGE_KEY, _allProjectsSearch);
}

function toggleAllProjectsColumnPicker() {
  _allProjectsPickerOpen = !_allProjectsPickerOpen;
  if (_allProjectsPickerOpen) {
    _allProjectsDraftColumns = [...loadVisibleAllProjectsColumns()];
  } else {
    _allProjectsDraftColumns = null;
  }
  loadAllProjects();
}

function closeAllProjectsColumnPicker() {
  _allProjectsPickerOpen = false;
  _allProjectsDraftColumns = null;
  loadAllProjects();
}

function updateAllProjectsDraftColumnSelection(columnKey, checked) {
  const defs = getAllProjectsColumnDefs({ fmt: () => '', pct: () => '', pctNumber: () => '', num: () => '', shortDateTime: () => '', daysAgo: () => '' });
  const validKeys = new Set(defs.map(def => def.key));
  const selected = (_allProjectsDraftColumns || loadVisibleAllProjectsColumns()).filter(key => validKeys.has(key));
  // Preserve user-defined order: only append when adding, filter when removing
  let next = checked ? [...selected, columnKey] : selected.filter(key => key !== columnKey);
  if (!next.length) next = [...ALL_PROJECTS_DEFAULT_COLUMNS];
  _allProjectsDraftColumns = next;
  updateAllProjectsPickerState();
}

function applyAllProjectsColumnSelection() {
  saveVisibleAllProjectsColumns(_allProjectsDraftColumns || [...ALL_PROJECTS_DEFAULT_COLUMNS]);
  _allProjectsPickerOpen = false;
  _allProjectsDraftColumns = null;
  loadAllProjects();
}

function resetAllProjectsColumns() {
  saveVisibleAllProjectsColumns([...ALL_PROJECTS_DEFAULT_COLUMNS]);
  _allProjectsDraftColumns = _allProjectsPickerOpen ? [...ALL_PROJECTS_DEFAULT_COLUMNS] : null;
  loadAllProjects();
}

function moveAllProjectsDraftColumn(columnKey, direction) {
  const selected = [...(_allProjectsDraftColumns || loadVisibleAllProjectsColumns())];
  const index = selected.indexOf(columnKey);
  const nextIndex = index + direction;
  if (index === -1 || nextIndex < 0 || nextIndex >= selected.length) return;
  [selected[index], selected[nextIndex]] = [selected[nextIndex], selected[index]];
  _allProjectsDraftColumns = selected;
  updateAllProjectsPickerState();
}

function removeAllProjectsDraftColumn(columnKey) {
  const selected = (_allProjectsDraftColumns || loadVisibleAllProjectsColumns()).filter(key => key !== columnKey);
  _allProjectsDraftColumns = selected.length ? selected : [...ALL_PROJECTS_DEFAULT_COLUMNS];
  updateAllProjectsPickerState();
}

function addAllProjectsDraftColumn(columnKey) {
  const selected = [...(_allProjectsDraftColumns || loadVisibleAllProjectsColumns())];
  if (!selected.includes(columnKey)) selected.push(columnKey);
  _allProjectsDraftColumns = selected;
  updateAllProjectsPickerState();
}

function beginAllProjectsDraftDrag(event, columnKey) {
  _allProjectsDraftDraggedColumn = columnKey;
  try {
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', columnKey);
  } catch {}
}

function clearAllProjectsDraftDropTargets() {
  document.querySelectorAll('.all-projects-selected-row.is-drop-target').forEach(el => {
    el.classList.remove('is-drop-target', 'drop-before', 'drop-after');
  });
}

function endAllProjectsDraftDrag() {
  _allProjectsDraftDraggedColumn = null;
  clearAllProjectsDraftDropTargets();
}

function allowAllProjectsDraftDrop(event, columnKey) {
  if (!_allProjectsDraftDraggedColumn || _allProjectsDraftDraggedColumn === columnKey) return;
  event.preventDefault();
  const row = event.currentTarget;
  if (!row) return;
  clearAllProjectsDraftDropTargets();
  const rect = row.getBoundingClientRect();
  const placeAfter = event.clientY > rect.top + (rect.height / 2);
  row.classList.add('is-drop-target', placeAfter ? 'drop-after' : 'drop-before');
}

function leaveAllProjectsDraftDrop(event) {
  const row = event.currentTarget;
  if (!row) return;
  row.classList.remove('is-drop-target', 'drop-before', 'drop-after');
}

function dropAllProjectsDraftColumn(event, targetKey) {
  event.preventDefault();
  const draggedKey = _allProjectsDraftDraggedColumn;
  if (!draggedKey || draggedKey === targetKey) {
    endAllProjectsDraftDrag();
    return;
  }
  const selected = [...(_allProjectsDraftColumns || loadVisibleAllProjectsColumns())];
  const filtered = selected.filter(key => key !== draggedKey);
  let insertAt = filtered.indexOf(targetKey);
  const row = event.currentTarget;
  if (row) {
    const rect = row.getBoundingClientRect();
    const placeAfter = event.clientY > rect.top + (rect.height / 2);
    if (placeAfter) insertAt += 1;
  }
  if (insertAt < 0) insertAt = filtered.length;
  filtered.splice(insertAt, 0, draggedKey);
  _allProjectsDraftColumns = filtered;
  endAllProjectsDraftDrag();
  updateAllProjectsPickerState();
}

function renderAllProjectsSelectedColumns(columnDefs, draftKeys) {
  const rows = draftKeys
    .map((key, index) => {
      const def = columnDefs.find(item => item.key === key);
      if (!def) return '';
      return `
        <div
          class="all-projects-selected-row"
          draggable="true"
          ondragstart="beginAllProjectsDraftDrag(event, '${esc(def.key)}')"
          ondragend="endAllProjectsDraftDrag()"
          ondragover="allowAllProjectsDraftDrop(event, '${esc(def.key)}')"
          ondragleave="leaveAllProjectsDraftDrop(event)"
          ondrop="dropAllProjectsDraftColumn(event, '${esc(def.key)}')">
          <div class="all-projects-selected-main">
            <span class="all-projects-selected-index">${String(index + 1).padStart(2, '0')}</span>
            <span class="all-projects-selected-handle" title="Drag to reorder">
              <i class="bi bi-grip-vertical"></i>
            </span>
            <span class="all-projects-selected-label">${esc(def.label)}</span>
          </div>
          <div class="all-projects-selected-actions">
            <button type="button" class="all-projects-selected-btn" title="Move ${esc(def.label)} up" ${index === 0 ? 'disabled' : ''}
              onclick="moveAllProjectsDraftColumn('${esc(def.key)}', -1)">
              <i class="bi bi-arrow-up"></i>
            </button>
            <button type="button" class="all-projects-selected-btn" title="Move ${esc(def.label)} down" ${index === draftKeys.length - 1 ? 'disabled' : ''}
              onclick="moveAllProjectsDraftColumn('${esc(def.key)}', 1)">
              <i class="bi bi-arrow-down"></i>
            </button>
            <button type="button" class="all-projects-selected-btn is-danger" title="Remove ${esc(def.label)}"
              onclick="removeAllProjectsDraftColumn('${esc(def.key)}')">
              <i class="bi bi-x-lg"></i>
            </button>
          </div>
        </div>
      `;
    })
    .join('');
  return rows || `<div class="all-projects-picker-empty">No visible columns selected.</div>`;
}

function renderAllProjectsColumnPicker(columnDefs, draftKeys) {
  const selectedPanel = `
    <div class="all-projects-picker-panel">
      <div class="all-projects-picker-panel-title">Visible Columns</div>
      <div class="all-projects-picker-panel-subtitle">Drag rows to reorder quickly, or use the arrows for small adjustments.</div>
      <div class="all-projects-selected-list">
        ${renderAllProjectsSelectedColumns(columnDefs, draftKeys)}
      </div>
    </div>
  `;
  const availablePanels = ALL_PROJECTS_COLUMN_GROUPS.map(group => {
    const defs = group.keys
      .map(key => columnDefs.find(def => def.key === key))
      .filter(Boolean);
    if (!defs.length) return '';
    return `
      <div class="all-projects-picker-group">
        <div class="all-projects-picker-title">${esc(group.label)}</div>
        <div class="all-projects-picker-options">
          ${defs.map(def => `
            <button type="button" class="all-projects-option ${draftKeys.includes(def.key) ? 'is-active' : ''}"
              ${draftKeys.includes(def.key) ? 'disabled' : ''}
              onclick="addAllProjectsDraftColumn('${esc(def.key)}')">
              <span>${esc(def.label)}</span>
              <i class="bi ${draftKeys.includes(def.key) ? 'bi-check2' : 'bi-plus-lg'}"></i>
            </button>
          `).join('')}
        </div>
      </div>
    `;
  }).join('');
  return `
    <div class="all-projects-picker-panel all-projects-picker-panel-primary">
      ${selectedPanel}
    </div>
    <div class="all-projects-picker-panel-stack">
      ${availablePanels}
    </div>
  `;
}

function updateAllProjectsPickerState() {
  const panel = document.getElementById('all-projects-column-picker');
  if (!panel || !_allProjectsPickerOpen) return;
  const defs = getAllProjectsColumnDefs({ fmt: () => '', pct: () => '', pctNumber: () => '', num: () => '', shortDateTime: () => '', daysAgo: () => '' });
  const draftKeys = _allProjectsDraftColumns || loadVisibleAllProjectsColumns();
  const body = document.getElementById('all-projects-picker-body');
  const count = document.getElementById('all-projects-picker-count');
  if (body) body.innerHTML = renderAllProjectsColumnPicker(defs, draftKeys);
  if (count) count.textContent = `${draftKeys.length} selected • choose multiple columns, then apply once`;
}

function updateAllProjectsSort(columnKey) {
  const current = loadAllProjectsSort();
  const direction = current.key === columnKey && current.direction === 'asc' ? 'desc' : 'asc';
  saveAllProjectsSort({ key: columnKey, direction });
  loadAllProjects();
}

function updateAllProjectsSearch(value) {
  saveAllProjectsSearch(value);
  const input = document.querySelector('.all-projects-search input');
  if (input && input.value !== value) input.value = value;
  if (_allProjectsListCache) {
    refilterAllProjects();
  } else {
    loadAllProjects();
  }
}

function _highlightSearchTerm(container, term) {
  const trimmed = term.trim();
  if (!trimmed) return;
  const re = new RegExp(trimmed.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) textNodes.push(node);
  for (const textNode of textNodes) {
    const text = textNode.textContent;
    re.lastIndex = 0;
    if (!re.test(text)) continue;
    re.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let lastIdx = 0;
    let match;
    while ((match = re.exec(text)) !== null) {
      if (match.index > lastIdx) frag.appendChild(document.createTextNode(text.slice(lastIdx, match.index)));
      const mark = document.createElement('mark');
      mark.className = 'ap-search-hl';
      mark.textContent = match[0];
      frag.appendChild(mark);
      lastIdx = match.index + match[0].length;
    }
    if (lastIdx < text.length) frag.appendChild(document.createTextNode(text.slice(lastIdx)));
    textNode.parentNode.replaceChild(frag, textNode);
  }
}

function refilterAllProjects() {
  if (!_allProjectsListCache) return;
  const list = _allProjectsListCache;
  const fmt  = v => '$' + (v||0).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
  const pct  = v => ((v||0)*100).toFixed(1) + '%';
  const pctNumber = v => `${Number(v || 0).toFixed(1)}%`;
  const num = v => Number(v || 0).toLocaleString('en-US', { maximumFractionDigits: 1 });
  const shortDateTime = v => (v || '').replace('T',' ').slice(0,16);
  const daysAgo = value => {
    if (!value) return '';
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return '';
    const diff = Math.max(0, Math.floor((Date.now() - dt.getTime()) / 86400000));
    return `${diff}d`;
  };

  const columnDefs = getAllProjectsColumnDefs({ fmt, pct, pctNumber, num, shortDateTime, daysAgo });
  const visibleKeys = loadVisibleAllProjectsColumns();
  const visibleColumns = columnDefs.filter(def => visibleKeys.includes(def.key));
  const searchQuery = loadAllProjectsSearch();
  const filteredList = filterAllProjectsList(list, searchQuery);
  const sortedList = sortAllProjectsList(filteredList, columnDefs);

  const tbody = document.querySelector('.all-projects-table tbody');
  if (tbody) {
    tbody.innerHTML = sortedList.length ? sortedList.map((p, i) => `
      <tr onclick="loadProjectAndSwitch('${esc(p.id)}','${esc(p.name)}')" title="Click to open">
        <td class="text-center text-muted small">${i+1}</td>
        ${visibleColumns.map(def => def.cell(p)).join('')}
        <td class="text-center" onclick="event.stopPropagation()">
          <button class="btn btn-sm btn-outline-danger py-0 px-1" title="Delete project"
            onclick="deleteProjectFromAllProjects('${esc(p.id)}','${esc(p.name)}',this)">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      </tr>`).join('') : `
      <tr>
        <td colspan="${visibleColumns.length + 2}" class="text-center py-5">
          <div class="all-projects-empty-state">
            <div class="all-projects-empty-icon"><i class="bi bi-search"></i></div>
            <div class="all-projects-empty-title">No projects match these filters</div>
            <div class="all-projects-empty-copy">Try adjusting your search or filter selections.</div>
            <button class="btn btn-outline-secondary btn-sm mt-3" onclick="clearAllProjectsFilters()">
              <i class="bi bi-arrow-counterclockwise me-1"></i>Clear All Filters
            </button>
          </div>
        </td>
      </tr>`;
    if (searchQuery) _highlightSearchTerm(tbody, searchQuery);
  }

  // Update count badge
  const badge = document.getElementById('all-projects-count-badge');
  if (badge) badge.textContent = `${sortedList.length} / ${list.length}`;

  // Show/hide clear-all button
  const clearBtn = document.getElementById('all-projects-clear-filters');
  if (clearBtn) {
    const hasFilter = searchQuery || Object.values(_allProjectsFilters).some(arr => arr.length > 0);
    clearBtn.classList.toggle('d-none', !hasFilter);
  }

  // Refresh cascading dropdown options
  const filterDefs = [
    { field: 'business_unit' },
    { field: 'location' },
    { field: 'partner' },
    { field: 'sales_spoc' },
  ];
  filterDefs.forEach(({ field }) => {
    const dropdown = document.getElementById(`ap-filter-dropdown-${field}`);
    if (!dropdown) return;
    const optionsList = _filterExcluding(list, searchQuery, field);
    const vals = _uniqueVals(optionsList, field);
    const selected = _allProjectsFilters[field];
    dropdown.innerHTML = vals.length
      ? vals.map(v => `
          <label class="ap-filter-option">
            <input type="checkbox" ${selected.includes(v) ? 'checked' : ''}
              onchange="toggleAllProjectsFilterValue('${field}', '${esc(v)}', this.checked)">
            <span>${v === '' ? '<em class="text-muted">(Blank)</em>' : esc(v)}</span>
          </label>`).join('')
      : '<div class="ap-filter-empty">No values</div>';
  });
}

function queueAllProjectsSearch(value) {
  saveAllProjectsSearch(value);
  if (_allProjectsListCache) {
    refilterAllProjects();
    return;
  }
  if (_allProjectsSearchTimer) clearTimeout(_allProjectsSearchTimer);
  _allProjectsSearchTimer = setTimeout(() => {
    _allProjectsSearchTimer = null;
    loadAllProjects();
  }, 180);
}

function compareAllProjectsValues(a, b) {
  const aEmpty = a === null || a === undefined || a === '';
  const bEmpty = b === null || b === undefined || b === '';
  if (aEmpty && bEmpty) return 0;
  if (aEmpty) return 1;
  if (bEmpty) return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' });
}

function sortAllProjectsList(list, columnDefs) {
  const sortState = loadAllProjectsSort();
  const def = columnDefs.find(item => item.key === sortState.key);
  if (!def?.sortValue) return [...list];
  const direction = sortState.direction === 'desc' ? -1 : 1;
  return [...list].sort((left, right) => direction * compareAllProjectsValues(def.sortValue(left), def.sortValue(right)));
}

function _matchesSearch(project, term) {
  if (!term) return true;
  const haystack = [
    project.customer, project.name, project.reference,
    project.business_unit, project.status, project.stage,
    project.project_owner, project.account_manager, project.sales_spoc,
    project.delivery_manager, project.location, project.partner,
    project.project_type, project.industry, project.saved_by,
    project.opportunity_id,
  ].join(' ').toLowerCase();
  return haystack.includes(term);
}

function filterAllProjectsList(list, query) {
  const term = String(query || '').trim().toLowerCase();
  const f = _allProjectsFilters;
  return list.filter(p => {
    if (!_matchesSearch(p, term)) return false;
    if (f.business_unit.length && !f.business_unit.includes(p.business_unit || '')) return false;
    if (f.location.length   && !f.location.includes(p.location || ''))         return false;
    if (f.partner.length    && !f.partner.includes(p.partner || ''))            return false;
    if (f.sales_spoc.length && !f.sales_spoc.includes(p.sales_spoc || ''))     return false;
    return true;
  });
}

// Returns the list with all filters applied EXCEPT for `excludeField` — used to
// build cascading dropdown options so each filter only shows values possible
// given the current selections in all other filters.
function _filterExcluding(list, query, excludeField) {
  const term = String(query || '').trim().toLowerCase();
  const f = _allProjectsFilters;
  return list.filter(p => {
    if (!_matchesSearch(p, term)) return false;
    if (excludeField !== 'business_unit' && f.business_unit.length && !f.business_unit.includes(p.business_unit || '')) return false;
    if (excludeField !== 'location'      && f.location.length      && !f.location.includes(p.location || ''))           return false;
    if (excludeField !== 'partner'       && f.partner.length       && !f.partner.includes(p.partner || ''))             return false;
    if (excludeField !== 'sales_spoc'    && f.sales_spoc.length    && !f.sales_spoc.includes(p.sales_spoc || ''))       return false;
    return true;
  });
}

function toggleAllProjectsFilterValue(field, value, checked) {
  const current = _allProjectsFilters[field];
  _allProjectsFilters[field] = checked
    ? [...current, value]
    : current.filter(v => v !== value);
  _syncFilterBadge(field);
  refilterAllProjects();
}

function toggleAllProjectsFilterDropdown(field) {
  if (_allProjectsOpenFilter === field) {
    _closeAllProjectsFilterDropdowns();
    return;
  }
  _closeAllProjectsFilterDropdowns();
  _allProjectsOpenFilter = field;
  const dropdown = document.getElementById(`ap-filter-dropdown-${field}`);
  const btn = document.getElementById(`ap-filter-btn-${field}`);
  if (dropdown) dropdown.classList.remove('d-none');
  if (btn) btn.classList.add('is-active');
}

function _closeAllProjectsFilterDropdowns() {
  _allProjectsOpenFilter = null;
  document.querySelectorAll('.ap-filter-dropdown').forEach(el => el.classList.add('d-none'));
  document.querySelectorAll('.ap-filter-btn').forEach(el => {
    const field = el.id.replace('ap-filter-btn-', '');
    if ((_allProjectsFilters[field] || []).length === 0) el.classList.remove('is-active');
  });
}

function _allProjectsOutsideClick(e) {
  if (!e.target.closest('.ap-filter-wrap')) {
    _closeAllProjectsFilterDropdowns();
  }
}

function _syncFilterBadge(field) {
  const count = _allProjectsFilters[field].length;
  const badge = document.getElementById(`ap-filter-badge-${field}`);
  const btn = document.getElementById(`ap-filter-btn-${field}`);
  if (badge) { badge.textContent = count; badge.classList.toggle('d-none', count === 0); }
  if (btn) btn.classList.toggle('is-active', count > 0);
}

function clearAllProjectsFilters() {
  _allProjectsFilters = { business_unit: [], location: [], partner: [], sales_spoc: [] };
  saveAllProjectsSearch('');
  _closeAllProjectsFilterDropdowns();
  const input = document.querySelector('.all-projects-search input');
  if (input) input.value = '';
  // Uncheck all checkboxes in filter dropdowns
  document.querySelectorAll('.ap-filter-option input[type="checkbox"]').forEach(cb => { cb.checked = false; });
  ['business_unit','location','partner','sales_spoc'].forEach(f => _syncFilterBadge(f));
  refilterAllProjects();
}

function _uniqueVals(list, field) {
  const vals = [...new Set(list.map(p => p[field] || ''))].sort((a, b) => {
    if (a === '') return 1;
    if (b === '') return -1;
    return a.localeCompare(b);
  });
  return vals;
}

function _renderFilterDropdown(field, label, optionsList) {
  const vals = _uniqueVals(optionsList, field);
  const selected = _allProjectsFilters[field];
  const count = selected.length;
  const options = vals.map(v => `
    <label class="ap-filter-option">
      <input type="checkbox" ${selected.includes(v) ? 'checked' : ''}
        onchange="toggleAllProjectsFilterValue('${field}', '${esc(v)}', this.checked)">
      <span>${v === '' ? '<em class="text-muted">(Blank)</em>' : esc(v)}</span>
    </label>`).join('');
  return `
    <div class="ap-filter-wrap">
      <button class="ap-filter-btn ${count > 0 ? 'is-active' : ''}" id="ap-filter-btn-${field}"
        onclick="toggleAllProjectsFilterDropdown('${field}')">
        ${label}
        <span class="ap-filter-badge ${count === 0 ? 'd-none' : ''}" id="ap-filter-badge-${field}">${count}</span>
        <i class="bi bi-chevron-down ap-filter-chevron"></i>
      </button>
      <div class="ap-filter-dropdown d-none" id="ap-filter-dropdown-${field}">
        ${vals.length ? options : '<div class="ap-filter-empty">No values</div>'}
      </div>
    </div>`;
}

async function loadAllProjects() {
  _allProjectsListCache = null;
  const container = document.getElementById('all-projects-container');
  if (!container) return;
  container.innerHTML = `<div class="text-center text-muted py-5"><i class="bi bi-hourglass-split me-1"></i>Loading…</div>`;

  let list;
  try {
    const res = await fetch('/api/projects?summary=true', { cache: 'no-store' });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    list = await res.json();
    if (!Array.isArray(list)) throw new Error('Unexpected response');
  } catch (e) {
    container.innerHTML = `<div class="text-center text-danger py-5"><i class="bi bi-exclamation-triangle me-1"></i>Could not load projects: ${e.message}</div>`;
    return;
  }
  _allProjectsListCache = list;

  // Close filter dropdowns when clicking outside
  document.removeEventListener('click', _allProjectsOutsideClick);
  document.addEventListener('click', _allProjectsOutsideClick);

  if (!list.length) {
    container.innerHTML = `<div class="text-center text-muted py-5">
      <i class="bi bi-inbox fs-1 d-block mb-2"></i>No saved projects yet. Use <strong>Save → Save As…</strong> to create one.
    </div>`;
    return;
  }

  const fmt  = v => '$' + (v||0).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
  const pct  = v => ((v||0)*100).toFixed(1) + '%';
  const pctNumber = v => `${Number(v || 0).toFixed(1)}%`;
  const num = v => Number(v || 0).toLocaleString('en-US', { maximumFractionDigits: 1 });
  const shortDateTime = v => (v || '').replace('T',' ').slice(0,16);
  const daysAgo = value => {
    if (!value) return '';
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return '';
    const diff = Math.max(0, Math.floor((Date.now() - dt.getTime()) / 86400000));
    return `${diff}d`;
  };

  const columnDefs = getAllProjectsColumnDefs({ fmt, pct, pctNumber, num, shortDateTime, daysAgo });
  const visibleKeys = loadVisibleAllProjectsColumns();
  const visibleColumns = columnDefs.filter(def => visibleKeys.includes(def.key));
  const draftKeys = _allProjectsDraftColumns || [...visibleKeys];
  const sortState = loadAllProjectsSort();
  const searchQuery = loadAllProjectsSearch();
  const filteredList = filterAllProjectsList(list, searchQuery);
  const sortedList = sortAllProjectsList(filteredList, columnDefs);
  const activeSortDef = columnDefs.find(def => def.key === sortState.key);
  const activeSortLabel = activeSortDef ? `${activeSortDef.label} (${sortState.direction === 'asc' ? 'Ascending' : 'Descending'})` : 'Custom';

  container.innerHTML = `
    <div class="all-projects-shell">
      <div class="all-projects-header mb-3">
        <div class="all-projects-header-left">
          <div class="all-projects-eyebrow">Portfolio View</div>
          <div class="all-projects-hero-title">
            All Saved Projects
            <span class="all-projects-count-badge" id="all-projects-count-badge">${sortedList.length} / ${list.length}</span>
          </div>
        </div>
        <div class="all-projects-header-actions">
          <button class="btn btn-sm btn-outline-secondary" onclick="toggleAllProjectsColumnPicker()">
            <i class="bi bi-sliders me-1"></i>${_allProjectsPickerOpen ? 'Hide Layout' : 'Customize Layout'}
          </button>
          <button class="btn btn-sm btn-outline-secondary" onclick="resetAllProjectsColumns()">Reset Default</button>
          <button class="btn btn-sm btn-outline-secondary" onclick="loadAllProjects()">
            <i class="bi bi-arrow-repeat me-1"></i>Refresh
          </button>
        </div>
      </div>
      <div class="all-projects-filterbar mb-3">
        <div class="all-projects-search">
          <i class="bi bi-search"></i>
          <input
            type="search"
            class="form-control"
            placeholder="Search customer, project, reference, owner…"
            value="${esc(searchQuery)}"
            oninput="queueAllProjectsSearch(this.value)"
          />
        </div>
        ${_renderFilterDropdown('business_unit', 'Business Unit', _filterExcluding(list, searchQuery, 'business_unit'))}
        ${_renderFilterDropdown('location',      'Location',      _filterExcluding(list, searchQuery, 'location'))}
        ${_renderFilterDropdown('partner',       'Partner',       _filterExcluding(list, searchQuery, 'partner'))}
        ${_renderFilterDropdown('sales_spoc',    'Sales SPOC',    _filterExcluding(list, searchQuery, 'sales_spoc'))}
        <button id="all-projects-clear-filters" class="btn btn-sm btn-outline-danger ${(searchQuery || Object.values(_allProjectsFilters).some(arr => arr.length > 0)) ? '' : 'd-none'}" onclick="clearAllProjectsFilters()">
          <i class="bi bi-x-lg me-1"></i>Clear
        </button>
      </div>
      <div id="all-projects-column-picker" class="all-projects-picker ${_allProjectsPickerOpen ? '' : 'd-none'} mb-3">
        <div class="all-projects-picker-header">
          <div>
            <div class="all-projects-picker-headline">Table Layout Manager</div>
            <div id="all-projects-picker-count" class="all-projects-picker-count">${draftKeys.length} selected • choose multiple columns, then apply once</div>
          </div>
          <div class="d-flex align-items-center gap-2 flex-wrap">
            <button class="btn btn-outline-secondary btn-sm" onclick="closeAllProjectsColumnPicker()">
              <i class="bi bi-x-lg me-1"></i>Close
            </button>
            <button class="btn btn-primary btn-sm" onclick="applyAllProjectsColumnSelection()">
              <i class="bi bi-check2 me-1"></i>Apply
            </button>
          </div>
        </div>
        <div id="all-projects-picker-body" class="all-projects-picker-grid">
          ${renderAllProjectsColumnPicker(columnDefs, draftKeys)}
        </div>
      </div>
    </div>
    <div class="table-responsive all-projects-table-wrap">
      <table class="table table-bordered table-hover align-middle all-projects-table" style="cursor:pointer">
        <thead style="background:var(--ax-deep);color:#fff">
          <tr>
            <th class="text-center" style="width:48px">S.No</th>
            ${visibleColumns.map(def => `
              <th class="${def.headerClass || ''}">
                <button type="button" class="all-projects-sort-btn ${sortState.key === def.key ? 'is-active' : ''}" onclick="updateAllProjectsSort('${esc(def.key)}')">
                  <span>${esc(def.label)}</span>
                  <i class="bi ${sortState.key === def.key ? (sortState.direction === 'asc' ? 'bi-sort-up' : 'bi-sort-down') : 'bi-arrow-down-up'}"></i>
                </button>
              </th>
            `).join('')}
            <th class="text-center" style="width:56px"></th>
          </tr>
        </thead>
        <tbody>
          ${sortedList.length ? sortedList.map((p, i) => `
            <tr onclick="loadProjectAndSwitch('${esc(p.id)}','${esc(p.name)}')" title="Click to open">
              <td class="text-center text-muted small">${i+1}</td>
              ${visibleColumns.map(def => def.cell(p)).join('')}
              <td class="text-center" onclick="event.stopPropagation()">
                <button class="btn btn-sm btn-outline-danger py-0 px-1" title="Delete project"
                  onclick="deleteProjectFromAllProjects('${esc(p.id)}','${esc(p.name)}',this)">
                  <i class="bi bi-trash"></i>
                </button>
              </td>
            </tr>`).join('') : `
            <tr>
              <td colspan="${visibleColumns.length + 2}" class="text-center py-5">
                <div class="all-projects-empty-state">
                  <div class="all-projects-empty-icon"><i class="bi bi-search"></i></div>
                  <div class="all-projects-empty-title">No projects match these filters</div>
                  <div class="all-projects-empty-copy">Try adjusting your search or filter selections.</div>
                  <button class="btn btn-outline-secondary btn-sm mt-3" onclick="clearAllProjectsFilters()">
                    <i class="bi bi-arrow-counterclockwise me-1"></i>Clear All Filters
                  </button>
                </div>
              </td>
            </tr>`}
        </tbody>
      </table>
    </div>`;
}

async function deleteProjectFromAllProjects(id, name, btn) {
  if (!confirm(`Delete "${name}"?\n\nThis cannot be undone.`)) return;
  const row = btn.closest('tr');
  if (row) { row.style.transition = 'opacity 0.25s'; row.style.opacity = '0.3'; row.style.pointerEvents = 'none'; }
  const res = await fetch(`/api/projects/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    if (row) { row.style.opacity = '1'; row.style.pointerEvents = ''; }
    showToast('Delete failed', 'danger');
    return;
  }
  showToast(`"${name}" deleted`, 'success');
  loadAllProjects();
}

async function loadProjectAndSwitch(id, name) {
  const res = await fetch(`/api/projects/${id}`);
  if (!res.ok) { showToast('Could not load project', 'danger'); return; }
  appData = await res.json();
  appData.project = normalizeProject(appData.project || {});
  _currentPid = id;
  populateAll();
  updateProjectBadge(name);
  document.querySelector('[href="#tab-project"]')?.click();
  showToast(`Loaded: ${name}`, 'success');
}

async function loadProjectsList() {
  const res  = await fetch('/api/projects');
  const list = await res.json();
  const el   = document.getElementById('projects-list');

  if (!list.length) {
    el.innerHTML = `<div class="text-center text-muted py-4">
      <i class="bi bi-inbox me-1"></i>No saved projects yet. Save the current project above.
    </div>`;
    return;
  }

  el.innerHTML = `
    <table class="table table-bordered table-hover align-middle">
      <thead class="table-dark">
        <tr><th>Project Name</th><th>Customer</th><th>Saved At</th><th style="width:160px"></th></tr>
      </thead>
      <tbody>
        ${list.map(p => `
          <tr id="proj-row-${esc(p.id)}">
            <td class="fw-semibold">
              <span id="proj-name-${esc(p.id)}">${esc(p.name)}</span>
              <input type="text" class="form-control form-control-sm d-none mt-1" id="proj-name-input-${esc(p.id)}" value="${esc(p.name)}" placeholder="Project name"/>
            </td>
            <td>
              <span id="proj-cust-${esc(p.id)}">${esc(p.customer || '—')}</span>
              <input type="text" class="form-control form-control-sm d-none mt-1" id="proj-cust-input-${esc(p.id)}" value="${esc(p.customer || '')}" placeholder="Customer name"/>
            </td>
            <td class="text-muted small">${p.saved_at ? p.saved_at.replace('T',' ') : ''}</td>
            <td class="text-center">
              <button class="btn btn-primary btn-sm" onclick="loadProject('${esc(p.id)}','${esc(p.name)}')">
                <i class="bi bi-folder2-open me-1"></i>Open
              </button>
              <button class="btn btn-outline-secondary btn-sm" onclick="startRename('${esc(p.id)}')" id="proj-rename-btn-${esc(p.id)}" title="Rename">
                <i class="bi bi-pencil"></i>
              </button>
              <button class="btn btn-success btn-sm d-none" onclick="confirmRename('${esc(p.id)}')" id="proj-save-btn-${esc(p.id)}" title="Save name">
                <i class="bi bi-check-lg"></i>
              </button>
              <button class="btn btn-outline-danger btn-sm" onclick="deleteProject('${esc(p.id)}')">
                <i class="bi bi-trash3"></i>
              </button>
            </td>
          </tr>`).join('')}
      </tbody>
    </table>`;
}

async function saveAsProject() {
  collectAll();
  const customer = appData.project?.customer?.trim();
  if (!customer) {
    const el = document.getElementById('proj_customer');
    el?.classList.add('is-invalid');
    el?.focus();
    bootstrap.Modal.getInstance(document.getElementById('saveAsModal'))?.hide(); bootstrap.Modal.getInstance(document.getElementById('projectsModal'))?.hide();
    showToast('Customer Name is required before saving.', 'danger');
    return;
  }
  const nameInput = document.getElementById('save_project_name').value.trim();
  const name = nameInput || customer || 'Untitled';
  const payload = { ...appData, _meta: { name } };
  const res  = await fetch('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const json = await res.json();
  if (res.ok) {
    document.getElementById('save_project_name').value = '';
    _currentPid = json.id;
    updateProjectBadge(json.name);
    loadProjectsList();
    loadAllProjects();
    bootstrap.Modal.getInstance(document.getElementById('saveAsModal'))?.hide();
    showToast(`Saved as "${json.name}"`, 'success');
  } else {
    showToast('Save failed: ' + (json.error || ''), 'danger');
  }
}

async function loadProject(id, name) {
  const res  = await fetch(`/api/projects/${id}`);
  if (!res.ok) { showToast('Could not load project', 'danger'); return; }
  appData = await res.json();
  _currentPid = id;
  populateAll();
  updateProjectBadge(name);
  bootstrap.Modal.getInstance(document.getElementById('saveAsModal'))?.hide();
  bootstrap.Modal.getInstance(document.getElementById('projectsModal'))?.hide();
  showToast(`Loaded: ${name}`, 'success');
}

async function deleteProject(id) {
  if (!confirm('Delete this saved project?')) return;
  await fetch(`/api/projects/${id}`, { method: 'DELETE' });
  loadProjectsList();
  loadAllProjects();
}

function startRename(id) {
  document.getElementById(`proj-name-${id}`)?.classList.add('d-none');
  document.getElementById(`proj-name-input-${id}`)?.classList.remove('d-none');
  document.getElementById(`proj-cust-${id}`)?.classList.add('d-none');
  document.getElementById(`proj-cust-input-${id}`)?.classList.remove('d-none');
  document.getElementById(`proj-rename-btn-${id}`)?.classList.add('d-none');
  document.getElementById(`proj-save-btn-${id}`)?.classList.remove('d-none');
  document.getElementById(`proj-name-input-${id}`)?.focus();
}

async function confirmRename(id) {
  const newName     = document.getElementById(`proj-name-input-${id}`)?.value.trim();
  const newCustomer = document.getElementById(`proj-cust-input-${id}`)?.value.trim();
  if (!newName) { showToast('Project name cannot be empty', 'danger'); return; }

  const r1 = await fetch(`/api/projects/${id}/rename`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: newName, customer: newCustomer })
  });
  if (r1.ok) {
    showToast(`Saved`, 'success');
    loadProjectsList();
  } else {
    showToast('Save failed', 'danger');
  }
}

function newProject() {
  if (!confirm('Start a new blank project? Unsaved changes will be lost.')) return;
  const catalog  = appData.role_catalog;
  const rateCard = appData.rate_card;
  _currentPid    = null;
  _targetMargin  = 0.40;
  appData = {
    project: buildDefaultProject(),
    resources: [], pnl_roles: [], releases: [],
    rate_card: rateCard, role_catalog: catalog,
    business_units: normalizeBusinessUnits(appData.business_units || []),
    attachments: { customer_po: false, cloud4c_quote: false, partner_proposal: false },
    funding: { marketing: {currency:'USD',value:null}, management: {currency:'USD',value:null}, discount: {currency:'USD',value:null} },
    approvals: { prepared_by: '', reviewed_by: '', approved_by: '' },
    export_filename: '', target_margin: 0.40, fx_rate: _usdToInr
  };
  populateAll();
  updateProjectBadge(null);
  bootstrap.Modal.getInstance(document.getElementById('saveAsModal'))?.hide();
  bootstrap.Modal.getInstance(document.getElementById('projectsModal'))?.hide();
  showToast('New project ready', 'primary');
}

function updateProjectBadge(name) {
  const badge = document.getElementById('current_project_badge');
  const pill  = document.getElementById('active_project_pill');
  const lbl   = document.getElementById('proj-savebar-label');
  if (!name) {
    pill?.classList.add('d-none');
    if (lbl) lbl.textContent = 'New project — fill in details below';
    return;
  }
  if (badge) badge.textContent = name;
  pill?.classList.remove('d-none');
  if (lbl) lbl.textContent = name;
}

// Load projects list when Open modal opens
// Pre-fill name when Save As modal opens
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('projectsModal')
    ?.addEventListener('show.bs.modal', () => loadProjectsList());

  document.getElementById('saveAsModal')
    ?.addEventListener('show.bs.modal', () => {
      const customer = appData.project?.customer || '';
      const nameEl = document.getElementById('save_project_name');
      if (nameEl) nameEl.value = customer ? `${customer} PnL` : '';
    });

  // Refresh + hide project badge when switching to All Projects tab
  document.querySelector('[href="#tab-all-projects"]')
    ?.addEventListener('click', () => { updateProjectBadge(null); loadAllProjects(); });
});

// ============================================================
// FUNDING & APPROVALS
// ============================================================
function populateFundingApprovals() {
  const att = appData.attachments || {};
  const elPo = document.getElementById('att_customer_po');
  const elC4c = document.getElementById('att_cloud4c');
  const elPart = document.getElementById('att_partner');
  if (elPo) elPo.checked = !!att.customer_po;
  if (elC4c) elC4c.checked = !!att.cloud4c_quote;
  if (elPart) elPart.checked = !!att.partner_proposal;

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
  // Attachments — elements may be absent if that tab has been removed from the UI
  const elPo   = document.getElementById('att_customer_po');
  const elC4c  = document.getElementById('att_cloud4c');
  const elPart = document.getElementById('att_partner');
  appData.attachments = {
    customer_po:       elPo   ? elPo.checked   : (appData.attachments?.customer_po   || false),
    cloud4c_quote:     elC4c  ? elC4c.checked  : (appData.attachments?.cloud4c_quote || false),
    partner_proposal:  elPart ? elPart.checked : (appData.attachments?.partner_proposal || false)
  };

  // Funding — only collect if elements exist; otherwise preserve current appData values
  const hasFundEl = !!document.getElementById('fund_mkt_method');
  if (hasFundEl) {
    const getFund = prefix => ({
      method:    getVal(`fund_${prefix}_method`),
      reference: getVal(`fund_${prefix}_ref`),
      currency:  getVal(`fund_${prefix}_currency`) || 'USD',
      value:     parseFloat(getVal(`fund_${prefix}_value`)) || null
    });
    appData.funding = {
      marketing:  getFund('mkt'),
      management: getFund('mgmt'),
      discount:   getFund('disc')
    };
  }

  // Approvals — only collect if elements exist
  const hasApprEl = !!document.getElementById('appr_prepared_by');
  if (hasApprEl) {
    appData.approvals = {
      prepared_by: getVal('appr_prepared_by'),
      reviewed_by: getVal('appr_reviewed_by'),
      approved_by: getVal('appr_approved_by')
    };
  }
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

async function saveExportSettings() {
  collectExportSettings();
  appData.target_margin = _targetMargin;
  await fetch('/api/data', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(appData)
  });
  showToast('Export settings saved!', 'success');
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
  collectRateCard();
  collectFundingApprovals();
  collectExportSettings();
  appData.target_margin = _targetMargin;
  appData.fx_rate = _usdToInr;
}

async function saveAll() {
  collectAll();
  const customer = appData.project?.customer?.trim();
  if (!customer) {
    const el = document.getElementById('proj_customer');
    el?.classList.add('is-invalid');
    el?.focus();
    document.querySelector('[href="#tab-project"]')?.click();
    showToast('Customer Name is required.', 'danger');
    return;
  }

  if (_currentPid) {
    // Update existing project file
    try {
      const res = await fetch(`/api/projects/${_currentPid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(appData)
      });
      const json = await res.json();
      if (res.ok) {
        showToast('Project updated!', 'success');
        _refreshAllProjectsIfVisible();
      } else {
        showToast('Save failed: ' + (json.error || ''), 'danger');
      }
    } catch (e) {
      showToast('Error: ' + e.message, 'danger');
    }
  } else {
    // No project loaded — open Save As modal
    bootstrap.Modal.getOrCreateInstance(document.getElementById('saveAsModal')).show();
  }
}

function _refreshAllProjectsIfVisible() {
  // Always refresh All Projects data so it's up-to-date when user switches to it
  loadAllProjects();
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


// ============================================================
// VERSION COMPARISON
// ============================================================
async function loadCompareProjects() {
  const res = await fetch('/api/projects');
  const projects = await res.json();
  ['cmp_pid1','cmp_pid2'].forEach(id => {
    const sel = document.getElementById(id);
    sel.innerHTML = '<option value="">-- select project --</option>';
    projects.forEach(p => {
      sel.innerHTML += `<option value="${esc(p.id)}">${esc(p.name)} (${esc(p.saved_at?.slice(0,10) || '')})</option>`;
    });
  });
  document.getElementById('compare_result').classList.add('d-none');
}

async function runCompare() {
  const pid1 = document.getElementById('cmp_pid1').value;
  const pid2 = document.getElementById('cmp_pid2').value;
  if (!pid1 || !pid2) { alert('Please select both projects.'); return; }
  if (pid1 === pid2) { alert('Please select two different projects.'); return; }

  const res = await fetch('/api/compare', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ pid1, pid2 })
  });
  if (!res.ok) { const e = await res.json(); alert('Error: ' + (e.error||res.status)); return; }
  const data = await res.json();

  // Cost rows
  const costRows = document.getElementById('cmp_cost_rows');
  costRows.innerHTML = '';
  const costKeys = [
    ['input_cost',   'Input Cost',   true],
    ['sell_cost',    'Sell Cost',    true],
    ['markup',       'Markup',       true],
    ['gross_margin', 'Gross Margin', false],
  ];
  costKeys.forEach(([k, label, isMoney]) => {
    const c = data.costs[k];
    if (!c) return;
    const fmt = v => isMoney ? fmtMoney(v) : (v*1).toFixed(1) + '%';
    // gross_margin comes back as %, not fraction
    const fmtGm = v => (v*1).toFixed(1) + '%';
    const fv1 = k === 'gross_margin' ? fmtGm(c.v1) : fmt(c.v1);
    const fv2 = k === 'gross_margin' ? fmtGm(c.v2) : fmt(c.v2);
    const fd  = k === 'gross_margin' ? fmtGm(c.delta) : fmt(c.delta);
    const dClass = c.delta > 0 ? 'text-success' : c.delta < 0 ? 'text-danger' : '';
    const pct = c.pct != null ? `${c.pct > 0 ? '+' : ''}${c.pct}%` : '—';
    costRows.innerHTML += `<tr>
      <td class="fw-bold">${esc(label)}</td>
      <td>${fv1}</td><td>${fv2}</td>
      <td class="${dClass}">${c.delta >= 0 ? '+' : ''}${fd}</td>
      <td class="${dClass}">${pct}</td>
    </tr>`;
  });

  // Resource rows
  const resRows = document.getElementById('cmp_res_rows');
  resRows.innerHTML = '';
  const changes = data.resource_changes || [];
  changes.forEach(r => {
    const badge = r.status === 'added'   ? '<span class="badge bg-success">Added</span>'
                : r.status === 'removed' ? '<span class="badge bg-danger">Removed</span>'
                :                          '<span class="badge bg-warning text-dark">Changed</span>';
    const dHours = (r.hours_delta ?? 0);
    const dClass = dHours > 0 ? 'text-success' : dHours < 0 ? 'text-danger' : '';
    resRows.innerHTML += `<tr>
      <td>${esc(r.role)}</td>
      <td>${badge}</td>
      <td>${r.hours_v1 ?? '—'}</td>
      <td>${r.hours_v2 ?? '—'}</td>
      <td class="${dClass}">${dHours > 0 ? '+' : ''}${dHours !== undefined ? dHours : '—'}</td>
      <td>${esc(r.level_v1 || '—')}</td>
      <td>${esc(r.level_v2 || '—')}</td>
    </tr>`;
  });

  const noChanges = document.getElementById('cmp_no_changes');
  noChanges.classList.toggle('d-none', data.has_changes !== false);
  document.getElementById('compare_result').classList.remove('d-none');
}


// ============================================================
// ORDER BOOKINGS & COMMITS
// ============================================================

let _bookingsData = [];
let _bookingsMeta = { custom_fields: [], column_labels: {} };

const BK_BUILTIN_COLS = [
  { key: 'booking_type',           defaultLabel: 'Type' },
  { key: 'opf_number',             defaultLabel: 'OPF Number' },
  { key: 'opf_date',               defaultLabel: 'OPF Date' },
  { key: 'cdd',                    defaultLabel: 'CDD' },
  { key: 'bu',                     defaultLabel: 'BU' },
  { key: 'customer_name',          defaultLabel: 'Customer Name' },
  { key: 'otc',                    defaultLabel: 'OTC (USD)' },
  { key: 'mrc',                    defaultLabel: 'MRC (USD/mo)' },
  { key: 'billed_pct',             defaultLabel: 'Billed %' },
  { key: 'milestones',             defaultLabel: 'Milestones' },
  { key: 'c4c_invoice_raised',     defaultLabel: 'C4C Invoice Raised' },
  { key: 'c4c_amount_received',    defaultLabel: 'C4C Amt Received' },
  { key: 'c4c_pending_billing',    defaultLabel: 'C4C Pending Billing' },
  { key: 'ax_invoice_raised',      defaultLabel: 'AX Invoice Raised' },
  { key: 'ax_amount_received',     defaultLabel: 'AX Amt Received' },
  { key: 'ax_pending_collection',  defaultLabel: 'AX Pending Collection' },
  { key: 'updates',                defaultLabel: 'Updates' },
  { key: 'billing_team_comments',  defaultLabel: 'Billing Team Comments' },
  { key: 'pmo',                    defaultLabel: 'PMO' },
];

function bkLabel(key) {
  return _bookingsMeta.column_labels[key] || BK_BUILTIN_COLS.find(c => c.key === key)?.defaultLabel || key;
}

async function loadBookingsOverview() {
  const [dataRes, metaRes] = await Promise.all([
    fetch('/api/bookings'),
    fetch('/api/bookings/meta/custom-fields'),
  ]);
  _bookingsData = await dataRes.json();
  _bookingsMeta = await metaRes.json();
  applyBookingsColumnLabels();
  populateBookingsBuFilter();
  renderBookingsTable();
}

function applyBookingsColumnLabels() {
  document.querySelectorAll('.bk-label[data-field]').forEach(el => {
    const key = el.dataset.field;
    if (_bookingsMeta.column_labels[key]) el.textContent = _bookingsMeta.column_labels[key];
  });
}

function populateBookingsBuFilter() {
  const bus = [...new Set(_bookingsData.map(r => r.bu).filter(Boolean))].sort();
  const sel = document.getElementById('bk-filter-bu');
  sel.innerHTML = '<option value="">All BUs</option>' + bus.map(b => `<option>${esc(b)}</option>`).join('');
}

function renderBookingsKpis(rows) {
  if (!rows) rows = getFilteredBookings();
  const otcRows = rows.filter(r => r.booking_type === 'OTC');
  const mrcRows = rows.filter(r => r.booking_type === 'MRC');
  const totalOtc       = otcRows.reduce((s, r) => s + (r.otc || 0), 0);
  const totalMrc       = mrcRows.reduce((s, r) => s + (r.mrc || 0), 0);
  const totalC4cBilled = rows.reduce((s, r) => s + (r.c4c_invoice_raised || 0), 0);
  const totalAxBilled  = rows.reduce((s, r) => s + (r.ax_invoice_raised || 0), 0);
  const strip = document.getElementById('bookings-kpi-strip');
  strip.innerHTML = [
    { label: 'OTC Entries',   value: otcRows.length,                                 icon: 'bi-receipt',        color: 'primary' },
    { label: 'MRC Entries',   value: mrcRows.length,                                 icon: 'bi-arrow-repeat',   color: 'info' },
    { label: 'Total OTC',     value: '$' + (totalOtc / 1000).toFixed(1) + 'k',       icon: 'bi-currency-dollar',color: 'success' },
    { label: 'Total MRC/mo',  value: '$' + (totalMrc / 1000).toFixed(1) + 'k',       icon: 'bi-calendar-month', color: 'warning' },
    { label: 'C4C Billed',    value: '$' + (totalC4cBilled / 1000).toFixed(1) + 'k', icon: 'bi-buildings',      color: 'secondary' },
    { label: 'AX Billed',     value: '$' + (totalAxBilled / 1000).toFixed(1) + 'k',  icon: 'bi-building',       color: 'secondary' },
  ].map(k => `
    <div class="col-md-2 col-sm-4 col-6">
      <div class="card text-center py-2">
        <div class="card-body py-1 px-2">
          <div class="text-muted small mb-1"><i class="bi ${k.icon} me-1"></i>${k.label}</div>
          <div class="fw-bold fs-5 text-${k.color}">${k.value}</div>
        </div>
      </div>
    </div>`).join('');
}

function getFilteredBookings() {
  const type   = document.getElementById('bk-filter-type')?.value || '';
  const bu     = document.getElementById('bk-filter-bu')?.value || '';
  const search = (document.getElementById('bk-filter-search')?.value || '').toLowerCase();
  return _bookingsData.filter(r => {
    if (type   && r.booking_type !== type)   return false;
    if (bu     && r.bu !== bu)               return false;
    if (search && !`${r.opf_number} ${r.customer_name} ${r.updates}`.toLowerCase().includes(search)) return false;
    return true;
  });
}

function renderBookingsTable() {
  const rows = getFilteredBookings();
  renderBookingsKpis(rows);
  const wrap = document.getElementById('bookings-table-wrap');
  if (!rows.length) {
    wrap.innerHTML = '<div class="text-center text-muted py-5"><i class="bi bi-inbox me-1"></i>No entries found. Click <strong>Add Entry</strong> to get started.</div>';
    return;
  }

  const typeFilter = document.getElementById('bk-filter-type')?.value || '';
  const showOtc  = !typeFilter || typeFilter === 'OTC';
  const showMrc  = !typeFilter || typeFilter === 'MRC';
  const showType = !typeFilter;
  const customCols = (_bookingsMeta.custom_fields || []).map(cf => ({ key: `cf_${cf.key}`, label: cf.label, custom: true, cfKey: cf.key }));

  // Money formatter
  const fmtMoney = v => {
    if (v == null || v === '') return '<td class="text-end text-muted small">—</td>';
    const n = Number(v);
    if (isNaN(n)) return `<td class="text-end">${esc(String(v))}</td>`;
    return `<td class="text-end fw-medium">$${n.toLocaleString('en-US', {maximumFractionDigits:0})}</td>`;
  };
  const fmtPct = v => {
    if (v == null || v === '') return '<td class="text-end text-muted small">—</td>';
    if (typeof v === 'string' && v.includes('%')) return `<td class="text-end">${esc(v)}</td>`;
    const n = Number(v);
    if (isNaN(n)) return `<td class="text-end">${esc(String(v))}</td>`;
    const pct = n <= 1 ? (n * 100).toFixed(0) : n.toFixed(0);
    const color = n >= (n <= 1 ? 1 : 100) ? 'text-success' : n > (n <= 1 ? 0.5 : 50) ? 'text-warning' : 'text-danger';
    return `<td class="text-end ${color} fw-medium">${pct}%</td>`;
  };
  const fmtText = (v, opts={}) => {
    if (v == null || v === '') return '<td class="text-muted small">—</td>';
    const s = esc(String(v));
    if (opts.truncate) return `<td style="max-width:${opts.maxWidth||160}px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${s}">${s}</td>`;
    return `<td>${s}</td>`;
  };
  const typeBadge = t => t === 'OTC'
    ? '<span class="badge text-bg-primary">OTC</span>'
    : '<span class="badge text-bg-info text-dark">MRC</span>';

  const fmtRow = r => {
    let cells = '';
    if (showType) cells += `<td class="text-center">${typeBadge(r.booking_type)}</td>`;
    cells += fmtText(r.opf_number);
    cells += fmtText(r.opf_date);
    cells += fmtText(r.cdd);
    cells += fmtText(r.bu);
    cells += fmtText(r.customer_name);
    if (showOtc) cells += fmtMoney(r.otc);
    if (showMrc) cells += fmtMoney(r.mrc);
    cells += fmtPct(r.billed_pct);
    cells += fmtText(r.milestones);
    // Cloud 4C group
    cells += fmtMoney(r.c4c_invoice_raised);
    cells += fmtMoney(r.c4c_amount_received);
    cells += fmtMoney(r.c4c_pending_billing);
    // AutomatonsX group
    cells += fmtMoney(r.ax_invoice_raised);
    cells += fmtMoney(r.ax_amount_received);
    cells += fmtMoney(r.ax_pending_collection);
    // Updates + billing comments + PMO + custom
    cells += fmtText(r.updates, { truncate: true, maxWidth: 200 });
    cells += fmtText(r.billing_team_comments, { truncate: true, maxWidth: 200 });
    cells += fmtText(r.pmo);
    customCols.forEach(c => { cells += `<td>${esc((r.extra_fields || {})[c.cfKey] ?? '')}</td>`; });
    cells += `<td class="text-center text-nowrap">
      <button class="btn btn-outline-primary btn-sm py-0 px-1 me-1" onclick="showBookingsEntry('${esc(r.id)}')" title="Edit"><i class="bi bi-pencil"></i></button>
      <button class="btn btn-outline-danger btn-sm py-0 px-1" onclick="deleteBookingEntry('${esc(r.id)}')" title="Delete"><i class="bi bi-trash"></i></button>
    </td>`;
    return `<tr>${cells}</tr>`;
  };

  // Column counts for group colspan calc
  const mainColCount = (showType ? 1 : 0) + 6 + (showOtc ? 1 : 0) + (showMrc ? 1 : 0) + 2; // type?, opf#, date, cdd, bu, customer, otc?, mrc?, billed%, milestones
  const c4cCount  = 3;
  const axCount   = 3;
  const tailCount = 1 + customCols.length + 1; // updates + custom + actions

  // Build header row 1 — fixed cols use rowspan=2, group headers use colspan
  const th = (label, extra='') => `<th rowspan="2" class="align-middle" ${extra}>${label}</th>`;
  let hdr1 = '';
  if (showType) hdr1 += th('Type', 'style="width:56px"');
  hdr1 += th(bkLabel('opf_number'));
  hdr1 += th(bkLabel('opf_date'),      'style="width:90px"');
  hdr1 += th(bkLabel('cdd'),           'style="width:90px"');
  hdr1 += th(bkLabel('bu'),            'style="width:60px"');
  hdr1 += th(bkLabel('customer_name'), 'style="min-width:140px"');
  if (showOtc) hdr1 += th(bkLabel('otc'),  'style="width:100px"');
  if (showMrc) hdr1 += th(bkLabel('mrc'),  'style="width:100px"');
  hdr1 += th(bkLabel('billed_pct'),    'style="width:72px"');
  hdr1 += th(bkLabel('milestones'),    'style="width:70px"');
  hdr1 += `<th colspan="${c4cCount}" class="text-center align-middle" style="background:#1a5fa8;color:#fff;font-weight:700;letter-spacing:.02em">Cloud 4C Services</th>`;
  hdr1 += `<th colspan="${axCount}"  class="text-center align-middle" style="background:#c97d00;color:#fff;font-weight:700;letter-spacing:.02em">AutomatonsX</th>`;
  hdr1 += th(bkLabel('updates'),                'style="min-width:160px"');
  hdr1 += th(bkLabel('billing_team_comments'), 'style="min-width:160px"');
  hdr1 += th(bkLabel('pmo'),                   'style="width:90px"');
  customCols.forEach(c => { hdr1 += th(esc(c.label)); });
  hdr1 += `<th rowspan="2" style="width:72px"></th>`;

  // Header row 2 — only sub-headers for the two groups
  const subTh = label => `<th class="text-center small" style="font-weight:600">${label}</th>`;
  const hdr2 =
    subTh('Invoice Raised<br>from C4C') +
    subTh('Amount Received<br>from Customer') +
    subTh('Pending Billing<br>from C4C') +
    subTh('Invoice Raised<br>from AX') +
    subTh('Amount Received<br>C4C → AX') +
    subTh('Pending<br>Collection');

  wrap.innerHTML = `
    <table class="table table-bordered table-hover table-sm align-middle" style="font-size:0.81rem">
      <thead class="sticky-top" style="top:0;z-index:10">
        <tr style="background:#212529;color:#fff">${hdr1}</tr>
        <tr style="background:#343a40;color:#dee2e6">${hdr2}</tr>
      </thead>
      <tbody>
        ${rows.map(fmtRow).join('')}
      </tbody>
    </table>`;
}

function clearBookingsFilters() {
  document.getElementById('bk-filter-type').value   = '';
  document.getElementById('bk-filter-bu').value     = '';
  document.getElementById('bk-filter-search').value = '';
  renderBookingsTable();
}

function showBookingsOverview() {
  document.getElementById('bookings-sub-entry').classList.add('d-none');
  document.getElementById('bookings-sub-overview').classList.remove('d-none');
}

async function showBookingsEntry(id) {
  document.getElementById('bookings-sub-overview').classList.add('d-none');
  document.getElementById('bookings-sub-entry').classList.remove('d-none');
  renderBookingsCustomFieldsEntry();

  if (!id) {
    document.getElementById('bk-entry-id').value    = '';
    document.getElementById('bk-entry-title').textContent = 'New Booking';
    clearBookingsForm();
    toggleBookingTypeFields();
    return;
  }

  const res = await fetch(`/api/bookings/${id}`);
  const d   = await res.json();
  document.getElementById('bk-entry-id').value = d.id;
  document.getElementById('bk-entry-title').textContent = `Edit: ${d.opf_number || d.customer_name || d.id}`;

  const sv = (elId, val) => { const el = document.getElementById(elId); if (el) el.value = val ?? ''; };
  sv('bk_booking_type',          d.booking_type || 'OTC');
  sv('bk_opf_number',            d.opf_number);
  sv('bk_opf_date',              d.opf_date ? d.opf_date.slice(0,10) : '');
  sv('bk_cdd',                   d.cdd ? d.cdd.slice(0,10) : '');
  sv('bk_bu',                    d.bu);
  sv('bk_customer_name',         d.customer_name);
  sv('bk_otc',                   d.otc);
  sv('bk_mrc',                   d.mrc);
  sv('bk_billed_pct',            d.billed_pct);
  sv('bk_milestones',            d.milestones);
  sv('bk_c4c_invoice_raised',    d.c4c_invoice_raised);
  sv('bk_c4c_amount_received',   d.c4c_amount_received);
  sv('bk_c4c_pending_billing',   d.c4c_pending_billing);
  sv('bk_ax_invoice_raised',        d.ax_invoice_raised);
  sv('bk_ax_amount_received',       d.ax_amount_received);
  sv('bk_ax_pending_collection',    d.ax_pending_collection);
  sv('bk_updates',                  d.updates);
  sv('bk_billing_team_comments',    d.billing_team_comments);
  sv('bk_pmo',                      d.pmo);

  const extra = d.extra_fields || {};
  (_bookingsMeta.custom_fields || []).forEach(cf => {
    const el = document.getElementById(`bk_cf_${cf.key}`);
    if (el) el.value = extra[cf.key] ?? '';
  });
  toggleBookingTypeFields();
}

function clearBookingsForm() {
  const ids = ['bk_opf_number','bk_opf_date','bk_cdd','bk_bu','bk_customer_name',
               'bk_otc','bk_mrc','bk_billed_pct','bk_milestones','bk_c4c_invoice_raised',
               'bk_c4c_amount_received','bk_c4c_pending_billing','bk_ax_invoice_raised',
               'bk_ax_amount_received','bk_ax_pending_collection','bk_updates',
               'bk_billing_team_comments','bk_pmo'];
  ids.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  const bt = document.getElementById('bk_booking_type');
  if (bt) bt.value = 'OTC';
}

function toggleBookingTypeFields() {
  const type = document.getElementById('bk_booking_type').value;
  document.getElementById('bk-otc-fields').classList.toggle('d-none', type !== 'OTC');
  document.getElementById('bk-mrc-fields').classList.toggle('d-none', type !== 'MRC');
  document.getElementById('bk-ax-pending-coll-wrap').classList.toggle('d-none', type !== 'MRC');
}

async function saveBookingEntry() {
  const id = document.getElementById('bk-entry-id').value;
  const extra = {};
  (_bookingsMeta.custom_fields || []).forEach(cf => {
    const el = document.getElementById(`bk_cf_${cf.key}`);
    if (el) extra[cf.key] = el.value;
  });

  const g = elId => { const el = document.getElementById(elId); return el?.value || null; };
  const payload = {
    booking_type:          document.getElementById('bk_booking_type').value,
    opf_number:            g('bk_opf_number'),
    opf_date:              g('bk_opf_date'),
    cdd:                   g('bk_cdd'),
    bu:                    g('bk_bu'),
    customer_name:         g('bk_customer_name'),
    otc:                   g('bk_otc'),
    mrc:                   g('bk_mrc'),
    billed_pct:            g('bk_billed_pct'),
    milestones:            g('bk_milestones'),
    c4c_invoice_raised:    g('bk_c4c_invoice_raised'),
    c4c_amount_received:   g('bk_c4c_amount_received'),
    c4c_pending_billing:   g('bk_c4c_pending_billing'),
    ax_invoice_raised:     g('bk_ax_invoice_raised'),
    ax_amount_received:    g('bk_ax_amount_received'),
    ax_pending_collection:  g('bk_ax_pending_collection'),
    updates:                g('bk_updates'),
    billing_team_comments:  g('bk_billing_team_comments'),
    pmo:                    g('bk_pmo'),
    extra_fields:           extra,
  };

  const url    = id ? `/api/bookings/${id}` : '/api/bookings';
  const method = id ? 'PUT' : 'POST';
  const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!res.ok) { showToast('Save failed', 'danger'); return; }
  showToast('Booking saved');
  await loadBookingsOverview();
  showBookingsOverview();
}

async function deleteBookingEntry(id) {
  if (!confirm('Delete this booking entry?')) return;
  await fetch(`/api/bookings/${id}`, { method: 'DELETE' });
  showToast('Deleted', 'warning');
  await loadBookingsOverview();
}

// ── Bookings Column Settings ──────────────────────────────────

function renderBookingsCustomFieldsEntry() {
  const container = document.getElementById('bk-custom-fields-entry');
  if (!container) return;
  container.innerHTML = (_bookingsMeta.custom_fields || []).map(cf => `
    <div class="mb-3">
      <label class="form-label small fw-semibold">${esc(cf.label)}</label>
      <input type="${cf.type === 'number' ? 'number' : cf.type === 'date' ? 'date' : 'text'}"
             class="form-control" id="bk_cf_${esc(cf.key)}"/>
    </div>`).join('');
}

async function openBookingsColumnSettings() {
  const res  = await fetch('/api/bookings/meta/custom-fields');
  _bookingsMeta = await res.json();

  const renameList = document.getElementById('bk-col-rename-list');
  renameList.innerHTML = '<div class="row g-2">' +
    BK_BUILTIN_COLS.map(c => `
      <div class="col-md-4">
        <label class="form-label small text-muted mb-0">${esc(c.defaultLabel)}</label>
        <input type="text" class="form-control form-control-sm" id="bk_rename_${c.key}"
               value="${esc(_bookingsMeta.column_labels[c.key] || '')}"
               placeholder="${esc(c.defaultLabel)}"/>
      </div>`).join('') +
    '</div>';

  renderBookingsCustomColList();
  new bootstrap.Modal(document.getElementById('bookingsColumnModal')).show();
}

function renderBookingsCustomColList() {
  const list   = document.getElementById('bk-custom-col-list');
  const fields = _bookingsMeta.custom_fields || [];
  if (!fields.length) {
    list.innerHTML = '<div class="text-muted small mb-2">No custom columns yet.</div>';
    return;
  }
  list.innerHTML = fields.map((cf, i) => `
    <div class="d-flex gap-2 mb-2 align-items-center">
      <input type="text" class="form-control form-control-sm" placeholder="Column Label"
             value="${esc(cf.label)}" id="bk_cf_label_${i}"/>
      <select class="form-select form-select-sm" style="max-width:120px" id="bk_cf_type_${i}">
        <option value="text"   ${cf.type==='text'  ?'selected':''}>Text</option>
        <option value="number" ${cf.type==='number'?'selected':''}>Number</option>
        <option value="date"   ${cf.type==='date'  ?'selected':''}>Date</option>
      </select>
      <button class="btn btn-outline-danger btn-sm py-0 px-1" onclick="removeBookingsCustomField(${i})">
        <i class="bi bi-trash"></i>
      </button>
    </div>`).join('');
}

function addBookingsCustomField() {
  if (!_bookingsMeta.custom_fields) _bookingsMeta.custom_fields = [];
  _bookingsMeta.custom_fields.push({ key: 'cf_' + Date.now(), label: 'New Column', type: 'text' });
  renderBookingsCustomColList();
}

function removeBookingsCustomField(i) {
  _bookingsMeta.custom_fields.splice(i, 1);
  renderBookingsCustomColList();
}

async function saveBookingsColumnSettings() {
  const labels = {};
  BK_BUILTIN_COLS.forEach(c => {
    const val = document.getElementById(`bk_rename_${c.key}`)?.value?.trim();
    if (val) labels[c.key] = val;
  });
  const fields = (_bookingsMeta.custom_fields || []).map((cf, i) => ({
    key:   cf.key,
    label: document.getElementById(`bk_cf_label_${i}`)?.value?.trim() || cf.label,
    type:  document.getElementById(`bk_cf_type_${i}`)?.value || 'text',
  }));

  await fetch('/api/bookings/meta/custom-fields', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ column_labels: labels, custom_fields: fields }),
  });
  showToast('Column settings saved');
  bootstrap.Modal.getInstance(document.getElementById('bookingsColumnModal'))?.hide();
  await loadBookingsOverview();
}

async function importBookings(input) {
  const file = input.files[0];
  if (!file) return;
  input.value = '';   // reset so same file can be re-imported

  const wrap = document.getElementById('bookings-table-wrap');
  wrap.innerHTML = '<div class="text-center text-muted py-5"><i class="bi bi-hourglass-split me-1"></i>Importing…</div>';

  const fd = new FormData();
  fd.append('file', file);

  try {
    const res = await fetch('/api/bookings/import', { method: 'POST', body: fd });
    const body = await res.json();
    if (!res.ok) {
      showToast(body.error || 'Import failed', 'danger');
      renderBookingsTable();
      return;
    }
    let msg = `Imported ${body.imported_count} booking row${body.imported_count !== 1 ? 's' : ''}.`;
    if (body.warnings?.length) msg += ` (${body.warnings.length} warning${body.warnings.length > 1 ? 's' : ''})`;
    showToast(msg, 'success');
    await loadBookingsOverview();
  } catch (e) {
    showToast('Import error: ' + e.message, 'danger');
    renderBookingsTable();
  }
}


// ============================================================
// FUNNEL REPORT
// ============================================================

let _funnelData = [];
let _funnelMeta = { custom_fields: [], column_labels: {} };

const FN_BUILTIN_COLS = [
  { key: 'reporting_manager',  defaultLabel: 'Reporting Manager' },
  { key: 'opportunity_owner',  defaultLabel: 'Opportunity Owner' },
  { key: 'region',             defaultLabel: 'Region' },
  { key: 'account_name',       defaultLabel: 'Account Name' },
  { key: 'description',        defaultLabel: 'Description' },
  { key: 'opportunity_name',   defaultLabel: 'Opportunity Name' },
  { key: 'closing_month',      defaultLabel: 'Closing Month' },
  { key: 'ageing_days',        defaultLabel: 'Ageing Days' },
  { key: 'stage',              defaultLabel: 'Stage' },
  { key: 'fq',                 defaultLabel: 'FQ' },
  { key: 'final_product',      defaultLabel: 'Final Product' },
  { key: 'net_forecasting',    defaultLabel: 'Net Forecasting' },
  { key: 'acv_usd_k',          defaultLabel: 'ACV (USD k)' },
  { key: 'otc_usd_k',          defaultLabel: 'OTC (USD k)' },
  { key: 'mrc_usd_k',          defaultLabel: 'MRC (USD k)' },
  { key: 'tcv_usd',            defaultLabel: 'TCV (USD)' },
  { key: 'updates',            defaultLabel: 'Updates' },
];

function fnLabel(key) {
  return _funnelMeta.column_labels[key] || FN_BUILTIN_COLS.find(c => c.key === key)?.defaultLabel || key;
}

async function loadFunnelOverview() {
  const [dataRes, metaRes] = await Promise.all([
    fetch('/api/funnel'),
    fetch('/api/funnel/meta/custom-fields'),
  ]);
  _funnelData = await dataRes.json();
  _funnelMeta = await metaRes.json();
  applyFunnelColumnLabels();
  populateFunnelFilters();
  renderFunnelTable();
}

function applyFunnelColumnLabels() {
  document.querySelectorAll('.fn-label[data-field]').forEach(el => {
    const key = el.dataset.field;
    if (_funnelMeta.column_labels[key]) el.textContent = _funnelMeta.column_labels[key];
  });
}

function populateFunnelFilters() {
  const regions  = [...new Set(_funnelData.map(r => r.region).filter(Boolean))].sort();
  const stages   = [...new Set(_funnelData.map(r => r.stage).filter(Boolean))].sort();
  const products = [...new Set(_funnelData.map(r => r.final_product).filter(Boolean))].sort();
  const fqs      = [...new Set(_funnelData.map(r => r.fq).filter(Boolean))].sort();

  const fill = (id, items) => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const cur   = sel.value;
    const first = sel.options[0]?.outerHTML || '';
    sel.innerHTML = first + items.map(v => `<option ${v===cur?'selected':''}>${esc(v)}</option>`).join('');
  };
  fill('fn-filter-region',  regions);
  fill('fn-filter-stage',   stages);
  fill('fn-filter-product', products);
  fill('fn-filter-fq',      fqs);
}

function renderFunnelKpis(rows) {
  if (!rows) rows = getFilteredFunnel();
  const totalAcv = rows.reduce((s, r) => s + (r.acv_usd_k || 0), 0);
  const totalOtc = rows.reduce((s, r) => s + (r.otc_usd_k || 0), 0);
  const stageCounts = {};
  rows.forEach(r => { if (r.stage) stageCounts[r.stage] = (stageCounts[r.stage] || 0) + 1; });
  const topStage = Object.entries(stageCounts).sort((a,b) => b[1]-a[1])[0];

  const strip = document.getElementById('funnel-kpi-strip');
  strip.innerHTML = [
    { label: 'Total Opportunities', value: rows.length,                             icon: 'bi-briefcase',      color: 'primary' },
    { label: 'Total ACV (USD k)',   value: '$' + totalAcv.toFixed(0) + 'k',          icon: 'bi-graph-up',       color: 'success' },
    { label: 'Total OTC (USD k)',   value: '$' + totalOtc.toFixed(0) + 'k',          icon: 'bi-currency-dollar',color: 'warning' },
    { label: 'Top Stage',           value: topStage ? `${topStage[0]} (${topStage[1]})` : '—', icon: 'bi-bar-chart-steps', color: 'info' },
  ].map(k => `
    <div class="col-md-3 col-sm-6">
      <div class="card text-center py-2">
        <div class="card-body py-1 px-2">
          <div class="text-muted small mb-1"><i class="bi ${k.icon} me-1"></i>${k.label}</div>
          <div class="fw-bold fs-5 text-${k.color}">${k.value}</div>
        </div>
      </div>
    </div>`).join('');
}

function getFilteredFunnel() {
  const region  = document.getElementById('fn-filter-region')?.value  || '';
  const stage   = document.getElementById('fn-filter-stage')?.value   || '';
  const product = document.getElementById('fn-filter-product')?.value || '';
  const fq      = document.getElementById('fn-filter-fq')?.value      || '';
  const search  = (document.getElementById('fn-filter-search')?.value || '').toLowerCase();
  return _funnelData.filter(r => {
    if (region  && r.region        !== region)  return false;
    if (stage   && r.stage         !== stage)   return false;
    if (product && r.final_product !== product) return false;
    if (fq      && r.fq            !== fq)      return false;
    if (search  && !`${r.account_name} ${r.opportunity_name} ${r.opportunity_owner} ${r.updates}`.toLowerCase().includes(search)) return false;
    return true;
  });
}

const STAGE_COLORS = {
  'Identified': 'secondary', 'Qualified': 'primary', 'Proposal Sent': 'info',
  'Negotiation': 'warning',  'Closed Won': 'success', 'Closed Lost': 'danger',
  'Pipeline': 'dark',
};
const FORECAST_COLORS = {
  'Pipeline': 'secondary', 'Upside': 'warning', 'Best Case': 'info', 'Commit': 'success',
};

function renderFunnelTable() {
  const rows = getFilteredFunnel();
  renderFunnelKpis(rows);
  const wrap = document.getElementById('funnel-table-wrap');
  if (!rows.length) {
    wrap.innerHTML = '<div class="text-center text-muted py-5"><i class="bi bi-inbox me-1"></i>No entries found. Click <strong>Add Entry</strong> to get started.</div>';
    return;
  }

  const NUM_KEYS = ['acv_usd_k','otc_usd_k','mrc_usd_k','tcv_usd'];
  const cols = [
    { key: 'account_name',      label: fnLabel('account_name') },
    { key: 'opportunity_name',  label: fnLabel('opportunity_name') },
    { key: 'opportunity_owner', label: fnLabel('opportunity_owner') },
    { key: 'region',            label: fnLabel('region') },
    { key: 'stage',             label: fnLabel('stage') },
    { key: 'fq',                label: fnLabel('fq') },
    { key: 'final_product',     label: fnLabel('final_product') },
    { key: 'net_forecasting',   label: fnLabel('net_forecasting') },
    { key: 'acv_usd_k',         label: fnLabel('acv_usd_k') },
    { key: 'otc_usd_k',         label: fnLabel('otc_usd_k') },
    { key: 'updates',           label: fnLabel('updates') },
    ...(_funnelMeta.custom_fields || []).map(cf => ({ key: `cf_${cf.key}`, label: cf.label, custom: true, cfKey: cf.key })),
  ];

  const renderCell = (r, c) => {
    if (c.custom) return `<td>${esc((r.extra_fields || {})[c.cfKey] ?? '')}</td>`;
    const v = r[c.key];
    if (c.key === 'stage') {
      const color = STAGE_COLORS[v] || 'secondary';
      return `<td><span class="badge text-bg-${color}">${esc(v || '—')}</span></td>`;
    }
    if (c.key === 'net_forecasting') {
      const color = FORECAST_COLORS[v] || 'secondary';
      return `<td><span class="badge text-bg-${color}">${esc(v || '—')}</span></td>`;
    }
    if (v == null || v === '') return '<td><span class="text-muted">—</span></td>';
    if (NUM_KEYS.includes(c.key)) return `<td class="text-end">${Number(v).toLocaleString('en-US',{minimumFractionDigits:1,maximumFractionDigits:1})}</td>`;
    if (c.key === 'updates') return `<td style="max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(v)}">${esc(v)}</td>`;
    return `<td>${esc(String(v))}</td>`;
  };

  wrap.innerHTML = `
    <table class="table table-bordered table-hover table-sm align-middle" style="font-size:0.82rem">
      <thead class="table-dark sticky-top">
        <tr>
          ${cols.map(c => `<th>${esc(c.label)}</th>`).join('')}
          <th style="width:80px"></th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(r => `
          <tr>
            ${cols.map(c => renderCell(r, c)).join('')}
            <td>
              <button class="btn btn-outline-primary btn-sm py-0 px-1 me-1" onclick="showFunnelEntry('${esc(r.id)}')" title="Edit"><i class="bi bi-pencil"></i></button>
              <button class="btn btn-outline-danger btn-sm py-0 px-1" onclick="deleteFunnelEntry('${esc(r.id)}')" title="Delete"><i class="bi bi-trash"></i></button>
            </td>
          </tr>`).join('')}
      </tbody>
    </table>`;
}

function clearFunnelFilters() {
  ['fn-filter-region','fn-filter-stage','fn-filter-product','fn-filter-fq'].forEach(id => {
    const el = document.getElementById(id); if (el) el.value = '';
  });
  const s = document.getElementById('fn-filter-search'); if (s) s.value = '';
  renderFunnelTable();
}

function showFunnelOverview() {
  document.getElementById('funnel-sub-entry').classList.add('d-none');
  document.getElementById('funnel-sub-overview').classList.remove('d-none');
}

async function showFunnelEntry(id) {
  document.getElementById('funnel-sub-overview').classList.add('d-none');
  document.getElementById('funnel-sub-entry').classList.remove('d-none');
  renderFunnelCustomFieldsEntry();

  if (!id) {
    document.getElementById('fn-entry-id').value = '';
    document.getElementById('fn-entry-title').textContent = 'New Funnel Entry';
    clearFunnelForm();
    return;
  }

  const res = await fetch(`/api/funnel/${id}`);
  const d   = await res.json();
  document.getElementById('fn-entry-id').value = d.id;
  document.getElementById('fn-entry-title').textContent = `Edit: ${d.account_name || d.opportunity_name || d.id}`;

  const sv = (elId, val) => { const el = document.getElementById(elId); if (el) el.value = val ?? ''; };
  sv('fn_record_id',         d.record_id);
  sv('fn_account_name',      d.account_name);
  sv('fn_description',       d.description);
  sv('fn_opportunity_name',  d.opportunity_name);
  sv('fn_region',            d.region);
  sv('fn_reporting_manager', d.reporting_manager);
  sv('fn_opportunity_owner', d.opportunity_owner);
  sv('fn_stage',             d.stage);
  sv('fn_fq',                d.fq);
  sv('fn_final_product',     d.final_product);
  sv('fn_net_forecasting',   d.net_forecasting);
  sv('fn_closing_month',     d.closing_month);
  sv('fn_ageing_days',       d.ageing_days);
  sv('fn_created_time',      d.created_time ? d.created_time.slice(0,10) : '');
  sv('fn_acv_usd_k',         d.acv_usd_k);
  sv('fn_otc_usd_k',         d.otc_usd_k);
  sv('fn_mrc_usd_k',         d.mrc_usd_k);
  sv('fn_tcv_usd',           d.tcv_usd);
  sv('fn_updates',           d.updates);

  const extra = d.extra_fields || {};
  (_funnelMeta.custom_fields || []).forEach(cf => {
    const el = document.getElementById(`fn_cf_${cf.key}`);
    if (el) el.value = extra[cf.key] ?? '';
  });
}

function clearFunnelForm() {
  document.querySelectorAll('#funnel-sub-entry input, #funnel-sub-entry textarea, #funnel-sub-entry select').forEach(el => {
    if (el.id === 'fn-entry-id') return;
    el.value = '';
  });
}

async function saveFunnelEntry() {
  const id = document.getElementById('fn-entry-id').value;
  const extra = {};
  (_funnelMeta.custom_fields || []).forEach(cf => {
    const el = document.getElementById(`fn_cf_${cf.key}`);
    if (el) extra[cf.key] = el.value;
  });

  const g = elId => document.getElementById(elId)?.value || null;
  const payload = {
    record_id:         g('fn_record_id'),
    account_name:      g('fn_account_name'),
    description:       g('fn_description'),
    opportunity_name:  g('fn_opportunity_name'),
    region:            g('fn_region'),
    reporting_manager: g('fn_reporting_manager'),
    opportunity_owner: g('fn_opportunity_owner'),
    stage:             g('fn_stage'),
    fq:                g('fn_fq'),
    final_product:     g('fn_final_product'),
    net_forecasting:   g('fn_net_forecasting'),
    closing_month:     g('fn_closing_month'),
    ageing_days:       g('fn_ageing_days'),
    created_time:      g('fn_created_time'),
    acv_usd_k:         g('fn_acv_usd_k'),
    otc_usd_k:         g('fn_otc_usd_k'),
    mrc_usd_k:         g('fn_mrc_usd_k'),
    tcv_usd:           g('fn_tcv_usd'),
    updates:           g('fn_updates'),
    extra_fields:      extra,
  };

  const url    = id ? `/api/funnel/${id}` : '/api/funnel';
  const method = id ? 'PUT' : 'POST';
  const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!res.ok) { showToast('Save failed', 'danger'); return; }
  showToast('Funnel entry saved');
  await loadFunnelOverview();
  showFunnelOverview();
}

async function deleteFunnelEntry(id) {
  if (!confirm('Delete this funnel entry?')) return;
  await fetch(`/api/funnel/${id}`, { method: 'DELETE' });
  showToast('Deleted', 'warning');
  await loadFunnelOverview();
}

// ── Funnel Column Settings ────────────────────────────────────

function renderFunnelCustomFieldsEntry() {
  const container = document.getElementById('fn-custom-fields-entry');
  if (!container) return;
  container.innerHTML = (_funnelMeta.custom_fields || []).map(cf => `
    <div class="mb-3">
      <label class="form-label small fw-semibold">${esc(cf.label)}</label>
      <input type="${cf.type === 'number' ? 'number' : cf.type === 'date' ? 'date' : 'text'}"
             class="form-control" id="fn_cf_${esc(cf.key)}"/>
    </div>`).join('');
}

async function openFunnelColumnSettings() {
  const res = await fetch('/api/funnel/meta/custom-fields');
  _funnelMeta = await res.json();

  const renameList = document.getElementById('fn-col-rename-list');
  renameList.innerHTML = '<div class="row g-2">' +
    FN_BUILTIN_COLS.map(c => `
      <div class="col-md-4">
        <label class="form-label small text-muted mb-0">${esc(c.defaultLabel)}</label>
        <input type="text" class="form-control form-control-sm" id="fn_rename_${c.key}"
               value="${esc(_funnelMeta.column_labels[c.key] || '')}"
               placeholder="${esc(c.defaultLabel)}"/>
      </div>`).join('') +
    '</div>';

  renderFunnelCustomColList();
  new bootstrap.Modal(document.getElementById('funnelColumnModal')).show();
}

function renderFunnelCustomColList() {
  const list   = document.getElementById('fn-custom-col-list');
  const fields = _funnelMeta.custom_fields || [];
  if (!fields.length) {
    list.innerHTML = '<div class="text-muted small mb-2">No custom columns yet.</div>';
    return;
  }
  list.innerHTML = fields.map((cf, i) => `
    <div class="d-flex gap-2 mb-2 align-items-center">
      <input type="text" class="form-control form-control-sm" placeholder="Column Label"
             value="${esc(cf.label)}" id="fn_cf_label_${i}"/>
      <select class="form-select form-select-sm" style="max-width:120px" id="fn_cf_type_${i}">
        <option value="text"   ${cf.type==='text'  ?'selected':''}>Text</option>
        <option value="number" ${cf.type==='number'?'selected':''}>Number</option>
        <option value="date"   ${cf.type==='date'  ?'selected':''}>Date</option>
      </select>
      <button class="btn btn-outline-danger btn-sm py-0 px-1" onclick="removeFunnelCustomField(${i})">
        <i class="bi bi-trash"></i>
      </button>
    </div>`).join('');
}

function addFunnelCustomField() {
  if (!_funnelMeta.custom_fields) _funnelMeta.custom_fields = [];
  _funnelMeta.custom_fields.push({ key: 'cf_' + Date.now(), label: 'New Column', type: 'text' });
  renderFunnelCustomColList();
}

function removeFunnelCustomField(i) {
  _funnelMeta.custom_fields.splice(i, 1);
  renderFunnelCustomColList();
}

async function saveFunnelColumnSettings() {
  const labels = {};
  FN_BUILTIN_COLS.forEach(c => {
    const val = document.getElementById(`fn_rename_${c.key}`)?.value?.trim();
    if (val) labels[c.key] = val;
  });
  const fields = (_funnelMeta.custom_fields || []).map((cf, i) => ({
    key:   cf.key,
    label: document.getElementById(`fn_cf_label_${i}`)?.value?.trim() || cf.label,
    type:  document.getElementById(`fn_cf_type_${i}`)?.value || 'text',
  }));

  await fetch('/api/funnel/meta/custom-fields', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ column_labels: labels, custom_fields: fields }),
  });
  showToast('Column settings saved');
  bootstrap.Modal.getInstance(document.getElementById('funnelColumnModal'))?.hide();
  await loadFunnelOverview();
}

async function importFunnel(input) {
  const file = input.files[0];
  if (!file) return;
  input.value = '';

  const wrap = document.getElementById('funnel-table-wrap');
  wrap.innerHTML = '<div class="text-center text-muted py-5"><i class="bi bi-hourglass-split me-1"></i>Importing…</div>';

  const fd = new FormData();
  fd.append('file', file);

  try {
    const res = await fetch('/api/funnel/import', { method: 'POST', body: fd });
    const body = await res.json();
    if (!res.ok) {
      showToast(body.error || 'Import failed', 'danger');
      renderFunnelTable();
      return;
    }
    let msg = `Imported ${body.imported_count} funnel row${body.imported_count !== 1 ? 's' : ''}.`;
    if (body.warnings?.length) msg += ` (${body.warnings.length} warning${body.warnings.length > 1 ? 's' : ''})`;
    showToast(msg, 'success');
    await loadFunnelOverview();
  } catch (e) {
    showToast('Import error: ' + e.message, 'danger');
    renderFunnelTable();
  }
}
