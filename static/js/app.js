// ============================================================
// PnL Application — Frontend Logic
// ============================================================

let appData = {};
let currentUser = {};

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
    'proj_status','proj_stage','proj_priority','proj_owner','proj_account_manager',
    'proj_sales_spoc','proj_delivery_manager','proj_technical_lead','proj_start_date',
    'proj_end_date','proj_opportunity_id','proj_type','proj_industry','proj_delivery_model',
    'proj_billing_type','proj_currency','proj_discount_pct','proj_travel_cost',
    'proj_infra_cost','proj_third_party_cost','proj_internal_notes','proj_risks',
    'proj_dependencies','proj_next_action','proj_follow_up_date'
  ]);
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

async function loadExchangeRate() {
  const inlineEl = document.getElementById('fx_rate_inline');
  if (inlineEl) inlineEl.placeholder = 'Fetching…';
  try {
    const res = await fetch('https://open.er-api.com/v6/latest/USD');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const fx = await res.json();
    _usdToInr = fx.rates.INR;
    if (inlineEl) inlineEl.value = _usdToInr.toFixed(2);
    renderRateCard();
    updateSummary();
  } catch (e) {
    if (inlineEl) inlineEl.placeholder = 'Unavailable — enter manually';
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
          onchange="setRate(${i},this.value,'${esc(selectedCat)}'); renderResources(); updateSummary(); renderRateChart(); saveSettings();"/></td>
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

function saveSettings() {
  fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      rate_card:    appData.rate_card,
      role_catalog: appData.role_catalog
    })
  });
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

      const catalog  = appData.role_catalog;
      const rateCard = appData.rate_card;
      _currentPid   = null;
      _targetMargin = 0.40;
      appData = {
        project: buildDefaultProject({
          customer: json.project?.customer || '',
          location: json.project?.location || '',
          reference: json.project?.reference || '',
          proposal_date: json.project?.proposal_date || '',
          duration_months: json.project?.duration_months || null,
          project_description: json.project?.description || '',
          partner: json.project?.partner || 'AutomatonsX',
          payment_terms: json.project?.payment_terms || 'As per proposal',
        }),
        resources: (json.resources || []).map(r => ({
          role: r.role, level: r.level, hours: r.hours, group: ''
        })),
        pnl_roles: [], releases: [],
        rate_card: rateCard, role_catalog: catalog,
        attachments: {customer_po:false, cloud4c_quote:false, partner_proposal:false},
        funding: {marketing:{currency:'USD',value:null}, management:{currency:'USD',value:null}, discount:{currency:'USD',value:null}},
        approvals: {prepared_by:'', reviewed_by:'', approved_by:''},
        export_filename: '', target_margin: 0.40, fx_rate: _usdToInr,
      };
      populateAll();
      updateProjectBadge(null);
      document.querySelector('[href="#tab-project"]')?.click();
      const warn = json.warnings?.length ? ` (${json.warnings.join('; ')})` : '';
      showToast(`Imported: ${json.resources?.length || 0} resources${warn}`, 'success');
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
  const fmtMoneyShort = v => '$' + Number(v || 0).toLocaleString('en-US', { maximumFractionDigits: 0 });
  const fmtNum = v => Number(v || 0).toLocaleString('en-US', { maximumFractionDigits: 1 });
  const fmtPct = v => ((Number(v || 0)) * 100).toFixed(1) + '%';

  container.innerHTML = `
    <div class="row g-3 mb-3">
      <div class="col-6 col-lg-3"><div class="analytics-kpi"><div class="analytics-kpi-label">Saved Projects</div><div class="analytics-kpi-value">${fmtNum(k.projects)}</div></div></div>
      <div class="col-6 col-lg-3"><div class="analytics-kpi"><div class="analytics-kpi-label">Total Resources</div><div class="analytics-kpi-value">${fmtNum(k.resources)}</div></div></div>
      <div class="col-6 col-lg-3"><div class="analytics-kpi"><div class="analytics-kpi-label">Total Hours</div><div class="analytics-kpi-value">${fmtNum(k.hours)}</div></div></div>
      <div class="col-6 col-lg-3"><div class="analytics-kpi"><div class="analytics-kpi-label">Avg Margin</div><div class="analytics-kpi-value">${fmtPct(k.avg_margin)}</div></div></div>
      <div class="col-6 col-lg-4"><div class="analytics-kpi analytics-kpi-accent"><div class="analytics-kpi-label">Portfolio Input Cost</div><div class="analytics-kpi-value">${fmtMoneyShort(k.input_cost)}</div></div></div>
      <div class="col-6 col-lg-4"><div class="analytics-kpi analytics-kpi-accent"><div class="analytics-kpi-label">Portfolio Revenue</div><div class="analytics-kpi-value">${fmtMoneyShort(k.revenue)}</div></div></div>
      <div class="col-12 col-lg-4"><div class="analytics-kpi analytics-kpi-soft"><div class="analytics-kpi-label">Avg Resources / Project</div><div class="analytics-kpi-value">${fmtNum(k.avg_resources_per_project)}</div></div></div>
    </div>
    <div class="row g-3">
      <div class="col-xl-6"><div class="card analytics-card"><div class="card-header fw-bold"><i class="bi bi-geo-alt me-1"></i>Top Locations</div><div class="card-body">${renderAnalyticsBars(data.top_locations, 'projects')}</div></div></div>
      <div class="col-xl-6"><div class="card analytics-card"><div class="card-header fw-bold"><i class="bi bi-person-workspace me-1"></i>Projects by Owner</div><div class="card-body">${renderAnalyticsBars(data.projects_by_owner, 'projects')}</div></div></div>
      <div class="col-xl-6"><div class="card analytics-card"><div class="card-header fw-bold"><i class="bi bi-briefcase me-1"></i>Top Customers</div><div class="card-body">${renderAnalyticsBars(data.top_customers, 'projects')}</div></div></div>
      <div class="col-xl-6"><div class="card analytics-card"><div class="card-header fw-bold"><i class="bi bi-diagram-3 me-1"></i>Resource Groups by Hours</div><div class="card-body">${renderAnalyticsBars(data.top_groups_by_hours, 'hours')}</div></div></div>
      <div class="col-xl-6"><div class="card analytics-card"><div class="card-header fw-bold"><i class="bi bi-people me-1"></i>Top Roles by Hours</div><div class="card-body">${renderAnalyticsBars(data.top_roles_by_hours, 'hours')}</div></div></div>
      <div class="col-xl-6"><div class="card analytics-card"><div class="card-header fw-bold"><i class="bi bi-speedometer2 me-1"></i>Margin Distribution</div><div class="card-body">${renderAnalyticsBars(data.margin_buckets, 'projects')}</div></div></div>
      <div class="col-12"><div class="card analytics-card"><div class="card-header fw-bold"><i class="bi bi-calendar3 me-1"></i>Projects Saved Over Time</div><div class="card-body">${renderAnalyticsTimeline(data.projects_by_month)}</div></div></div>
    </div>`;
}

function renderAnalyticsBars(items, unit = 'count') {
  if (!Array.isArray(items) || !items.length) {
    return `<div class="text-center text-muted py-4"><i class="bi bi-inbox me-1"></i>No data yet</div>`;
  }
  const maxValue = Math.max(...items.map(item => Number(item.value || 0)), 1);
  const fmt = value => {
    const n = Number(value || 0);
    if (unit === 'hours') return `${n.toLocaleString('en-US', { maximumFractionDigits: 1 })} hrs`;
    return `${n.toLocaleString('en-US')} ${unit}`;
  };
  return items.map(item => {
    const value = Number(item.value || 0);
    const width = Math.max((value / maxValue) * 100, value > 0 ? 8 : 0);
    return `
      <div class="analytics-bar-row">
        <div class="analytics-bar-head">
          <span class="analytics-bar-label" title="${esc(item.label)}">${esc(item.label)}</span>
          <span class="analytics-bar-value">${fmt(value)}</span>
        </div>
        <div class="analytics-bar-track"><div class="analytics-bar-fill" style="width:${width}%"></div></div>
      </div>`;
  }).join('');
}

function renderAnalyticsTimeline(items) {
  if (!Array.isArray(items) || !items.length) {
    return `<div class="text-center text-muted py-4"><i class="bi bi-inbox me-1"></i>No saved project history yet</div>`;
  }
  const maxValue = Math.max(...items.map(item => Number(item.value || 0)), 1);
  return `
    <div class="analytics-timeline">
      ${items.map(item => {
        const value = Number(item.value || 0);
        const height = Math.max((value / maxValue) * 100, value > 0 ? 10 : 0);
        return `
          <div class="analytics-timeline-item">
            <div class="analytics-timeline-count">${value}</div>
            <div class="analytics-timeline-bar-wrap"><div class="analytics-timeline-bar" style="height:${height}%"></div></div>
            <div class="analytics-timeline-label">${esc(item.label)}</div>
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

function getAllProjectsColumnDefs(formatters) {
  const { fmt, pct, pctNumber, num, shortDateTime, daysAgo } = formatters;
  return [
    { key: 'customer', label: 'Customer', headerClass: '', cell: p => `<td class="fw-semibold">${esc(p.customer || '')}</td>` },
    { key: 'project', label: 'Project', headerClass: '', cell: p => `<td>${esc(p.name)}</td>` },
    { key: 'reference', label: 'Reference', headerClass: '', cell: p => `<td class="small">${esc(p.reference || '')}</td>` },
    {
      key: 'status',
      label: 'Status',
      headerClass: '',
      cell: p => `<td><span class="badge text-bg-${p.status === 'Won' ? 'success' : p.status === 'Lost' ? 'danger' : p.status === 'On Hold' ? 'warning' : 'secondary'}">${esc(p.status || '')}</span></td>`
    },
    { key: 'stage', label: 'Stage', headerClass: '', cell: p => `<td class="small">${esc(p.stage || '')}</td>` },
    { key: 'priority', label: 'Priority', headerClass: '', cell: p => `<td class="small">${esc(p.priority || '')}</td>` },
    { key: 'project_owner', label: 'Owner', headerClass: '', cell: p => `<td class="small">${esc(p.project_owner || '')}</td>` },
    { key: 'account_manager', label: 'Account Manager', headerClass: '', cell: p => `<td class="small">${esc(p.account_manager || '')}</td>` },
    { key: 'sales_spoc', label: 'Sales SPOC', headerClass: '', cell: p => `<td class="small">${esc(p.sales_spoc || '')}</td>` },
    { key: 'delivery_manager', label: 'Delivery Manager', headerClass: '', cell: p => `<td class="small">${esc(p.delivery_manager || '')}</td>` },
    { key: 'location', label: 'Location', headerClass: '', cell: p => `<td class="text-muted small">${esc(p.location || '')}</td>` },
    { key: 'duration', label: 'Duration', headerClass: 'text-center', cell: p => `<td class="text-center small">${p.duration ? p.duration + ' mo' : ''}</td>` },
    { key: 'proposal_date', label: 'Proposal Date', headerClass: '', cell: p => `<td class="small text-muted">${esc(p.proposal_date || '')}</td>` },
    { key: 'expected_start_date', label: 'Start Date', headerClass: '', cell: p => `<td class="small text-muted">${esc(p.expected_start_date || '')}</td>` },
    { key: 'expected_end_date', label: 'End Date', headerClass: '', cell: p => `<td class="small text-muted">${esc(p.expected_end_date || '')}</td>` },
    { key: 'next_follow_up_date', label: 'Follow-Up', headerClass: '', cell: p => `<td class="small">${esc(p.next_follow_up_date || '')}</td>` },
    { key: 'opportunity_id', label: 'Opportunity ID', headerClass: '', cell: p => `<td class="small">${esc(p.opportunity_id || '')}</td>` },
    { key: 'partner', label: 'Partner', headerClass: '', cell: p => `<td class="small">${esc(p.partner || '')}</td>` },
    { key: 'project_type', label: 'Type', headerClass: '', cell: p => `<td class="small">${esc(p.project_type || '')}</td>` },
    { key: 'industry', label: 'Industry', headerClass: '', cell: p => `<td class="small">${esc(p.industry || '')}</td>` },
    { key: 'delivery_model', label: 'Delivery', headerClass: '', cell: p => `<td class="small">${esc(p.delivery_model || '')}</td>` },
    { key: 'billing_type', label: 'Billing', headerClass: '', cell: p => `<td class="small">${esc(p.billing_type || '')}</td>` },
    { key: 'currency', label: 'Currency', headerClass: '', cell: p => `<td class="small">${esc(p.currency || 'USD')}</td>` },
    { key: 'resource_count', label: 'Resources', headerClass: 'text-end', cell: p => `<td class="text-end small">${num(p.resource_count)}</td>` },
    { key: 'total_hours', label: 'Hours', headerClass: 'text-end', cell: p => `<td class="text-end small">${num(p.total_hours)}</td>` },
    { key: 'avg_rate', label: 'Avg Rate', headerClass: 'text-end', cell: p => `<td class="text-end small">${p.avg_rate ? fmt(p.avg_rate) : ''}</td>` },
    { key: 'input_cost', label: 'Input Cost', headerClass: 'text-end', cell: p => `<td class="text-end small">${p.costs?.input_cost ? fmt(p.costs.input_cost) : ''}</td>` },
    { key: 'add_on_cost', label: 'Add-On Cost', headerClass: 'text-end', cell: p => `<td class="text-end small">${p.add_on_cost ? fmt(p.add_on_cost) : ''}</td>` },
    { key: 'discount_pct', label: 'Discount %', headerClass: 'text-end', cell: p => `<td class="text-end small">${p.discount_pct ? pctNumber(p.discount_pct) : ''}</td>` },
    { key: 'markup', label: 'MarkUp', headerClass: 'text-end', cell: p => `<td class="text-end small">${p.costs?.markup ? fmt(p.costs.markup) : ''}</td>` },
    { key: 'revenue', label: 'Revenue', headerClass: 'text-end', cell: p => `<td class="text-end small">${p.costs?.sell_cost ? fmt(p.costs.sell_cost) : ''}</td>` },
    { key: 'profit_amount', label: 'Profit', headerClass: 'text-end', cell: p => `<td class="text-end small">${p.profit_amount ? fmt(p.profit_amount) : ''}</td>` },
    {
      key: 'gross_margin',
      label: 'Gross Margin',
      headerClass: 'text-end',
      cell: p => {
        const margin = (p.costs?.gross_margin || 0) * 100;
        const marginColor = margin >= 35 ? 'text-success fw-bold' : margin >= 20 ? 'text-warning fw-bold' : 'text-danger fw-bold';
        return `<td class="text-end small ${p.costs?.gross_margin ? marginColor : ''}">${p.costs?.gross_margin ? pct(p.costs.gross_margin) : ''}</td>`;
      }
    },
    { key: 'since_save', label: 'Since Save', headerClass: 'text-center', cell: p => `<td class="text-center small text-muted">${daysAgo(p.saved_at)}</td>` },
    { key: 'saved_at', label: 'Saved At', headerClass: '', cell: p => `<td class="small text-muted">${shortDateTime(p.saved_at)}</td>` },
    { key: 'saved_by', label: 'Saved By', headerClass: '', cell: p => `<td class="small text-muted">${esc(p.saved_by || '')}</td>` },
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

function toggleAllProjectsColumnPicker() {
  const panel = document.getElementById('all-projects-column-picker');
  const icon = document.getElementById('all-projects-column-toggle-icon');
  if (!panel) return;
  panel.classList.toggle('d-none');
  if (icon) icon.className = panel.classList.contains('d-none') ? 'bi bi-chevron-down ms-1' : 'bi bi-chevron-up ms-1';
}

function updateAllProjectsColumnSelection(columnKey, checked) {
  const defs = getAllProjectsColumnDefs({ fmt: () => '', pct: () => '', pctNumber: () => '', num: () => '', shortDateTime: () => '', daysAgo: () => '' });
  const validKeys = new Set(defs.map(def => def.key));
  const selected = loadVisibleAllProjectsColumns().filter(key => validKeys.has(key));
  let next = checked ? [...selected, columnKey] : selected.filter(key => key !== columnKey);
  if (!next.length) next = [...ALL_PROJECTS_DEFAULT_COLUMNS];
  next = defs.map(def => def.key).filter(key => next.includes(key));
  saveVisibleAllProjectsColumns(next);
  loadAllProjects();
}

function resetAllProjectsColumns() {
  saveVisibleAllProjectsColumns([...ALL_PROJECTS_DEFAULT_COLUMNS]);
  loadAllProjects();
}

async function loadAllProjects() {
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

  container.innerHTML = `
    <div class="card border-0 shadow-sm mb-3">
      <div class="card-body py-2 px-3">
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
          <div class="small text-muted">The original All Projects columns stay as the default. Add the new metadata columns only when you want them.</div>
          <div class="d-flex align-items-center gap-2">
            <button class="btn btn-outline-secondary btn-sm" onclick="toggleAllProjectsColumnPicker()">
              <i class="bi bi-layout-three-columns me-1"></i>Choose Columns <i id="all-projects-column-toggle-icon" class="bi bi-chevron-down ms-1"></i>
            </button>
            <button class="btn btn-outline-secondary btn-sm" onclick="resetAllProjectsColumns()">Reset Default</button>
          </div>
        </div>
        <div id="all-projects-column-picker" class="d-none mt-3">
          <div class="row g-2">
            ${columnDefs.map(def => `
              <div class="col-sm-6 col-lg-4 col-xl-3">
                <label class="form-check small mb-0">
                  <input class="form-check-input" type="checkbox" ${visibleKeys.includes(def.key) ? 'checked' : ''}
                    onchange="updateAllProjectsColumnSelection('${esc(def.key)}', this.checked)">
                  <span class="form-check-label">${esc(def.label)}</span>
                </label>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    </div>
    <div class="table-responsive">
      <table class="table table-bordered table-hover align-middle" style="cursor:pointer">
        <thead style="background:var(--ax-deep);color:#fff">
          <tr>
            <th class="text-center" style="width:48px">S.No</th>
            ${visibleColumns.map(def => `<th class="${def.headerClass || ''}">${esc(def.label)}</th>`).join('')}
            <th class="text-center" style="width:56px"></th>
          </tr>
        </thead>
        <tbody>
          ${list.map((p, i) => {
            return `<tr onclick="loadProjectAndSwitch('${esc(p.id)}','${esc(p.name)}')" title="Click to open">
              <td class="text-center text-muted small">${i+1}</td>
              ${visibleColumns.map(def => def.cell(p)).join('')}
              <td class="text-center" onclick="event.stopPropagation()">
                <button class="btn btn-sm btn-outline-danger py-0 px-1" title="Delete project"
                  onclick="deleteProjectFromAllProjects('${esc(p.id)}','${esc(p.name)}',this)">
                  <i class="bi bi-trash"></i>
                </button>
              </td>
            </tr>`;
          }).join('')}
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
  if (!name) {
    pill?.classList.add('d-none');
    return;
  }
  if (badge) badge.textContent = name;
  pill?.classList.remove('d-none');
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
