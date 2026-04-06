// ============================================================
// PnL Application — Frontend Logic
// ============================================================

let appData = {};
let currentUser = {};

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
  const res = await fetch('/api/data');
  if (!res.ok) { window.location.href = '/login'; return; }
  appData = await res.json();
  populateAll();
  loadExchangeRate();

  // Clear validation state when user types in customer field
  document.getElementById('proj_customer')?.addEventListener('input', function() {
    this.classList.remove('is-invalid');
  });
});

function populateAll() {
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
    placeholder: '',
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
  const levels    = (appData.rate_card || []).map(r => r.level);
  const catalog   = appData.role_catalog || [];

  const tbody = document.getElementById('resources-tbody');
  tbody.innerHTML = '';

  let totalHours = 0, totalCost = 0;

  resources.forEach((res, i) => {
    const rate = rateMap[res.level] || 0;
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
      <td class="text-center">
        <button class="btn btn-outline-danger btn-icon" onclick="removeResource(${i})" title="Remove">
          <i class="bi bi-trash3"></i>
        </button>
      </td>`;
    tbody.appendChild(tr);
  });

  document.getElementById('tot_hours').textContent = totalHours;
  document.getElementById('tot_cost').textContent  = fmtMoney(totalCost);
}

function updateResourceCost(i, hoursVal) {
  const hours = parseFloat(hoursVal) || 0;
  appData.resources[i].hours = hours;

  const rateMap = {};
  (appData.rate_card || []).forEach(r => { rateMap[r.level] = r.rate; });
  const rate = rateMap[appData.resources[i].level] || 0;
  const cost = hours * rate;

  const costEl = document.getElementById(`res_cost_${i}`);
  if (costEl) costEl.textContent = fmtMoney(cost);

  // Recalculate totals
  let totalHours = 0, totalCost = 0;
  (appData.resources || []).forEach(r => {
    totalHours += (r.hours || 0);
    totalCost  += (r.hours || 0) * (rateMap[r.level] || 0);
  });
  document.getElementById('tot_hours').textContent = totalHours;
  document.getElementById('tot_cost').textContent  = fmtMoney(totalCost);
  updateSummary();
}

function onResGroupChange(i, groupName) {
  const catalog = appData.role_catalog || [];
  const group   = catalog.find(g => g.group === groupName);
  const roles   = group?.roles || [];
  appData.resources[i].group = groupName;
  appData.resources[i].role  = roles[0] || '';

  // Repopulate just the role select without full re-render
  const roleEl = document.getElementById(`res_role_${i}`);
  if (roleEl) {
    roleEl.innerHTML = roles.map(r =>
      `<option value="${esc(r)}">${esc(r)}</option>`
    ).join('');
  }
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
  const rows = document.querySelectorAll('#ratecard-tbody tr');
  rows.forEach((row, i) => {
    if (!appData.rate_card[i]) return;
    const levelInput = row.querySelector('input[type="text"]');
    const rateInput  = row.querySelector('input[type="number"]');
    if (levelInput) appData.rate_card[i].level = levelInput.value.trim();
    if (rateInput)  appData.rate_card[i].rate  = parseFloat(rateInput.value) || 0;
  });
}

let _usdToInr = null;

async function loadExchangeRate() {
  try {
    // Call directly from browser — avoids PythonAnywhere outbound restrictions
    const res = await fetch('https://open.er-api.com/v6/latest/USD');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const fx = await res.json();
    _usdToInr = fx.rates.INR;
    const updated = fx.time_last_update_utc
      ? fx.time_last_update_utc.replace(/ \+0000$/, ' UTC') : '';
    document.getElementById('fx-rate-label').textContent =
      `1 USD = ₹${_usdToInr.toFixed(2)}  ·  ${updated}`;
    document.getElementById('fx-badge').classList.remove('d-none');
    document.getElementById('inr-col-header').classList.remove('d-none');
    renderRateCard();
  } catch (e) {
    document.getElementById('fx-rate-label').textContent = 'Rate unavailable';
    document.getElementById('fx-badge').classList.remove('d-none');
  }
}

function renderRateCard() {
  sortRateCard();
  const rc = appData.rate_card || [];
  const tbody = document.getElementById('ratecard-tbody');
  tbody.innerHTML = '';
  const showInr = _usdToInr !== null;

  rc.forEach((item, i) => {
    const inrVal = showInr ? Math.round(item.rate * _usdToInr) : null;
    const inrCell = showInr
      ? `<td class="text-end text-muted small">₹${inrVal.toLocaleString('en-IN')}</td>`
      : '';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="text-center text-muted small">${i + 1}</td>
      <td><input type="text" class="form-control form-control-sm" value="${esc(item.level)}"
          oninput="appData.rate_card[${i}].level=this.value; renderRateChart(); saveSettings();"/></td>
      <td><input type="number" class="form-control form-control-sm text-end" value="${item.rate}" min="0" step="0.5"
          onchange="appData.rate_card[${i}].rate=parseFloat(this.value)||0; sortRateCard(); renderRateCard(); renderResources(); updateSummary(); saveSettings();"/></td>
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

function sortRateCard() {
  appData.rate_card.sort((a, b) => (a.rate || 0) - (b.rate || 0));
}

function addRateLevel() {
  if (!appData.rate_card) appData.rate_card = [];
  const nextNum = appData.rate_card.length + 1;
  appData.rate_card.push({ level: `L${nextNum}`, rate: 0 });
  sortRateCard();
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
// PROJECTS — save / load / delete
// ============================================================
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
              <input type="text" class="form-control form-control-sm d-none mt-1" id="proj-name-input-${esc(p.id)}" value="${esc(p.name)}"/>
            </td>
            <td>${esc(p.customer || '—')}</td>
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
    updateProjectBadge(json.name);
    loadProjectsList();
    showToast(`Saved as "${json.name}"`, 'success');
  } else {
    showToast('Save failed', 'danger');
  }
}

async function loadProject(id, name) {
  const res  = await fetch(`/api/projects/${id}`);
  if (!res.ok) { showToast('Could not load project', 'danger'); return; }
  appData = await res.json();
  populateAll();
  updateProjectBadge(name);
  bootstrap.Modal.getInstance(document.getElementById('saveAsModal'))?.hide(); bootstrap.Modal.getInstance(document.getElementById('projectsModal'))?.hide();
  showToast(`Loaded: ${name}`, 'success');
}

async function deleteProject(id) {
  if (!confirm('Delete this saved project?')) return;
  await fetch(`/api/projects/${id}`, { method: 'DELETE' });
  loadProjectsList();
}

function startRename(id) {
  document.getElementById(`proj-name-${id}`)?.classList.add('d-none');
  document.getElementById(`proj-name-input-${id}`)?.classList.remove('d-none');
  document.getElementById(`proj-rename-btn-${id}`)?.classList.add('d-none');
  document.getElementById(`proj-save-btn-${id}`)?.classList.remove('d-none');
  document.getElementById(`proj-name-input-${id}`)?.focus();
}

async function confirmRename(id) {
  const newName = document.getElementById(`proj-name-input-${id}`)?.value.trim();
  if (!newName) { showToast('Name cannot be empty', 'danger'); return; }
  // Load, update _meta.name, re-save to the same file via a PATCH-like POST
  const res = await fetch(`/api/projects/${id}`);
  if (!res.ok) { showToast('Could not load project', 'danger'); return; }
  const data = await res.json();
  data._meta = { ...(data._meta || {}), name: newName };
  // Save with the existing id by posting to a rename endpoint
  const r2 = await fetch(`/api/projects/${id}/rename`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: newName })
  });
  if (r2.ok) {
    showToast(`Renamed to "${newName}"`, 'success');
    loadProjectsList();
  } else {
    showToast('Rename failed', 'danger');
  }
}

function newProject() {
  if (!confirm('Start a new blank project? Unsaved changes will be lost.')) return;
  // Reset to blank slate keeping role catalog and rate card
  const catalog  = appData.role_catalog;
  const rateCard = appData.rate_card;
  appData = {
    project: { company: 'AutomatonsX', customer: '', location: '', reference: '',
                proposal_date: '', customer_first_touch_point: '', project_description: '',
                partner: 'AutomatonsX', payment_terms: 'As per proposal', duration_months: null },
    resources: [], pnl_roles: [], releases: [],
    rate_card: rateCard, role_catalog: catalog,
    attachments: { customer_po: false, cloud4c_quote: false, partner_proposal: false },
    funding: { marketing: {currency:'USD',value:null}, management: {currency:'USD',value:null}, discount: {currency:'USD',value:null} },
    approvals: { prepared_by: '', reviewed_by: '', approved_by: '' },
    export_filename: ''
  };
  populateAll();
  updateProjectBadge('New Project');
  bootstrap.Modal.getInstance(document.getElementById('saveAsModal'))?.hide(); bootstrap.Modal.getInstance(document.getElementById('projectsModal'))?.hide();
  showToast('New project ready', 'primary');
}

function updateProjectBadge(name) {
  const el = document.getElementById('current_project_badge');
  if (!name) { el.classList.add('d-none'); return; }
  el.textContent = name;
  el.classList.remove('d-none');
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
});

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
  collectRateCard();
  collectFundingApprovals();
  collectExportSettings();
}

async function saveAll() {
  collectAll();
  const customer = appData.project?.customer?.trim();
  if (!customer) {
    const el = document.getElementById('proj_customer');
    el?.classList.add('is-invalid');
    el?.focus();
    // Switch to Project Info tab
    document.querySelector('[href="#tab-project"]')?.click();
    showToast('Customer Name is required.', 'danger');
    return;
  }
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
