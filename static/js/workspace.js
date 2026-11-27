// Project workspace (DESIGN.md 5.3): tabs on the left, the Price build-up on the right.
// All numbers come from the server engine (POST /api/pnl/calculate); nothing is computed here.
(function () {
  'use strict';
  const { esc, toast, dialog, errorMessage } = window.axUI;
  const AX = window.AX || { thresholds: { good: 20, warn: 10 }, user: {} };
  const icon = n => (document.getElementById('ax-icon-' + n) || {}).innerHTML || '';
  const root = document.getElementById('ax-ws');
  if (!root) return;

  const W = {
    pid: root.dataset.pid || '', p: null, meta: {}, opts: null, cat: null, result: null, errors: {},
    tab: 'resources', dirty: false, versions: [], publishedVersion: null, publishedCard: null,
    liveFx: null, liveFxAt: null, folders: [], customerError: '', calcSeq: 0, saving: false,
  };

  // ── helpers ───────────────────────────────────────────────────────────
  const money = n => (n == null || isNaN(n)) ? '' : (n < 0 ? '−$' : '$') + Math.abs(Math.round(n)).toLocaleString('en-US');
  const moneyK = n => n >= 1e6 ? '$' + (n / 1e6).toFixed(2) + 'M' : '$' + (n / 1e3).toFixed(1) + 'k';
  const pct = n => (n == null || isNaN(n)) ? '' : (Math.round(n * 10) / 10).toFixed(1) + '%';
  const inr = n => '₹' + Math.round(n).toLocaleString('en-IN');
  const num = v => { const n = parseFloat(v); return Number.isFinite(n) ? n : 0; };
  const health = v => v >= AX.thresholds.good ? 'good' : v >= AX.thresholds.warn ? 'warn' : 'bad';
  const fmtDate = v => {
    if (!v) return '';
    const d = new Date(String(v).replace(' ', 'T'));
    return isNaN(d) ? esc(v) : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  };
  const fmtDateTime = v => {
    const d = new Date(String(v || '').replace(' ', 'T'));
    return isNaN(d) ? esc(v || '') : d.toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  };
  const legacy = () => (W.p.calc_mode || 'legacy') === 'legacy';
  const P = () => W.p.project;
  const get = path => path.split('.').reduce((o, k) => (o == null ? undefined : o[k]), W.p);
  function set(path, value) {
    const keys = path.split('.');
    let o = W.p;
    keys.slice(0, -1).forEach(k => { if (o[k] == null || typeof o[k] !== 'object') o[k] = {}; o = o[k]; });
    o[keys[keys.length - 1]] = value;
  }
  async function api(url, opts = {}) {
    const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts });
    if (!res.ok) { const e = new Error(await errorMessage(res)); e.status = res.status; throw e; }
    return res.json();
  }
  const options = (list, value, blank) => {
    const vals = [...list];
    if (value && !vals.includes(value)) vals.push(value);          // keep a stored value that isn't in the list
    return (blank !== undefined ? `<option value="">${esc(blank)}</option>` : '') +
      vals.map(v => `<option value="${esc(v)}" ${v === value ? 'selected' : ''}>${esc(v)}</option>`).join('');
  };

  // ── catalog: roles and levels ─────────────────────────────────────────
  async function loadCatalog(settings, rolesPromise) {
    try {
      const r = await rolesPromise;
      const lv = Object.fromEntries(r.levels.map(l => [l.id, l.code]));
      W.cat = r.categories.map(c => ({
        name: c.name, active: c.active,
        roles: r.roles.filter(x => x.category_id === c.id)
          .map(x => ({ id: x.id, name: x.name, active: x.active, level: lv[x.default_level_id] || '' })),
      }));
      W.levelOrder = r.levels.map(l => l.code);
    } catch {
      // Databases without the rate-card tables: the role catalog from settings
      W.cat = (settings.role_catalog || []).map(g => ({ name: g.group, active: true,
        roles: (g.roles || []).map(n => ({ id: null, name: n, active: true, level: '' })) }));
      W.levelOrder = (settings.rate_card || []).map(e => e.level);
    }
  }
  const category = name => W.cat.find(c => c.name === name);
  function rateFor(level, cat) {
    const e = (W.p.rate_card || []).find(x => x.level === level);
    if (!e) return null;
    if (e.rates && typeof e.rates === 'object' && Object.keys(e.rates).length) {
      return e.rates[cat] != null ? e.rates[cat] : null;
    }
    return e.rate != null ? e.rate : null;
  }
  const ratedLevels = cat => (W.p.rate_card || []).map(e => e.level).filter(l => rateFor(l, cat) != null);
  function defaultLine() {
    const c = W.cat.find(x => x.active && x.roles.some(r => r.active)) || W.cat[0] || { name: '', roles: [] };
    const role = c.roles.find(r => r.active) || c.roles[0] || { name: '', level: '' };
    const levels = ratedLevels(c.name);
    return { group: c.name, role: role.name, role_id: role.id, level: levels.includes(role.level) ? role.level : (levels[0] || ''), hours: 0 };
  }

  // ── load ──────────────────────────────────────────────────────────────
  function normalise(p) {
    p.project = p.project || {};
    p.resources = (p.resources || []).filter(r => r && typeof r === 'object');
    p.one_time_costs = (p.one_time_costs || []).filter(x => x && typeof x === 'object').map(x => {
      const lic = !!x.exclude_from_margin || x.category === 'license';
      const out = { ...x, label: x.label || '', amount: num(x.amount), category: lic ? 'license' : 'one_time', exclude_from_margin: lic };
      if (lic && !out.license_type) {
        const l = String(x.label || '').toLowerCase();
        out.license_type = l === 'ai subscriptions' ? 'AI' : l === 'other project management licenses' ? 'Project management' : 'Other';
      }
      return out;
    });
    const t = p.addon_treatment || {};
    p.addon_treatment = {};
    for (const k of ['travel', 'infra', 'third_party']) {
      p.addon_treatment[k] = ['margin', 'pass'].includes(t[k]) ? t[k] : W.opts.addon_defaults[k];
    }
    if (p.cloud4c_margin == null && p.ax_margin == null) {
      p.cloud4c_margin = typeof p.target_margin === 'number' ? p.target_margin : 0.40;
      p.ax_margin = 0;
    }
    p.cloud4c_margin = num(p.cloud4c_margin);
    p.ax_margin = num(p.ax_margin);
    p.calc_mode = p.calc_mode || 'legacy';
    const pr = p.project;
    pr.status = pr.status || 'Draft';
    if (String(pr.status).toLowerCase() === 'on hold') pr.status = 'On hold';
    return p;
  }

  async function load() {
    // Everything the page needs, requested at once (each request costs a round trip to the database).
    const rolesP = api('/api/roles?usage=0');
    rolesP.catch(() => {});
    const projectP = W.pid ? api(`/api/projects/${encodeURIComponent(W.pid)}`) : null;
    const versionsP = W.pid ? api(`/api/projects/${encodeURIComponent(W.pid)}/versions`).catch(() => []) : null;
    projectP && projectP.catch(() => {});
    const [opts, settings] = await Promise.all([api('/api/workspace/options'), api('/api/data')]);
    W.opts = opts;
    W.publishedVersion = settings.rate_card_version || null;
    W.publishedCard = settings.rate_card || [];
    await loadCatalog(settings, rolesP);
    if (W.pid) {
      const p = await projectP;
      W.meta = p._meta || {};
      if (p.published_rate_card_version) W.publishedVersion = p.published_rate_card_version;
      delete p.published_rate_card_version;
      W.p = normalise(p);
      W.versions = await versionsP;
    } else {
      W.p = normalise({
        _meta: { name: '', folder: '' },
        project: { company: 'AutomatonsX', customer: '', status: 'Draft', stage: 'Qualification', priority: 'Medium',
          currency: 'USD', delivery_model: 'Offshore', billing_type: 'Time and material', business_unit: '' },
        resources: [], one_time_costs: [],
        cloud4c_margin: 0.40, ax_margin: 0.20, fx_rate: null,
        rate_card: W.publishedCard, rate_card_version: W.publishedVersion,
        calc_mode: 'v2',                         // DESIGN.md 7.3: new projects use the new calculation
      });
      W.tab = 'details';
      W.dirty = true;
    }
    if (W.pid && new URLSearchParams(location.search).has('scenario')) await applyScenario(false);
    fetch('/api/projects/folders').then(r => r.ok ? r.json() : []).then(f => { W.folders = f; }).catch(() => {});
    liveFx(!W.p.fx_rate);
    render();
    calc();
  }

  async function loadVersions() {
    if (!W.pid) { W.versions = []; return; }
    try { W.versions = await api(`/api/projects/${encodeURIComponent(W.pid)}/versions`); } catch { W.versions = []; }
  }

  async function liveFx(apply) {
    const tries = [
      async () => { const r = await fetch('/api/exchange-rate', { cache: 'no-store' }); if (!r.ok) throw 0; return Number((await r.json()).usd_to_inr); },
      async () => { const r = await fetch('https://open.er-api.com/v6/latest/USD', { cache: 'no-store' }); if (!r.ok) throw 0; return Number((await r.json()).rates?.INR); },
    ];
    for (const t of tries) {
      try {
        const v = await t();
        if (Number.isFinite(v) && v > 0) {
          W.liveFx = Math.round(v * 100) / 100;
          W.liveFxAt = new Date();
          if (apply) { W.p.fx_rate = W.liveFx; calc(); }
          renderLedger();
          return;
        }
      } catch { /* next source */ }
    }
  }

  // ── calculation ───────────────────────────────────────────────────────
  // Lever limits (DESIGN.md 5.3) checked here in both calculation modes; the engine also
  // enforces them for the new calculation. Errors show under the lever, not in a toast.
  function leverErrors() {
    const e = {}, max = W.opts.limits.margin_max, dmax = W.opts.limits.discount_max;
    const c4c = num(W.p.cloud4c_margin) * 100, ax = num(W.p.ax_margin) * 100, d = num(P().discount_pct);
    if (c4c < 0 || c4c > max) e.cloud4c_margin = `Cloud4C margin must be between 0% and ${max}%.`;
    if (ax < 0 || ax > max) e.ax_margin = `AX margin must be between 0% and ${max}%.`;
    if (!e.cloud4c_margin && !e.ax_margin && c4c + ax >= max) e.ax_margin = `Cloud4C and AX margin together must stay below ${max}%.`;
    if (!legacy() && (d < 0 || d > dmax)) e.discount_pct = `Discount must be between 0% and ${dmax}%.`;
    if (W.p.fx_rate !== null && W.p.fx_rate !== '' && W.p.fx_rate !== undefined && num(W.p.fx_rate) <= 0) e.fx_rate = 'The exchange rate must be above 0.';
    return e;
  }

  let calcTimer = null;
  function calc() {
    clearTimeout(calcTimer);
    const local = leverErrors();
    if (Object.keys(local).length) { W.calcSeq++; W.errors = local; renderLedger(); return; }
    calcTimer = setTimeout(async () => {
      const seq = ++W.calcSeq;
      try {
        const res = await fetch('/api/pnl/calculate', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ snapshot: snapshot() }),
        });
        const body = await res.json().catch(() => ({}));
        if (seq !== W.calcSeq) return;                         // a newer request is on its way
        if (res.status === 422) { W.errors = body.errors || {}; }
        else if (res.ok) { W.errors = {}; W.result = body.result; }
        else { W.errors = { _: body.error || 'The price could not be calculated.' }; }
      } catch {
        if (seq === W.calcSeq) W.errors = { _: "The price couldn't be calculated: the server didn't answer." };
      }
      renderLedger();
      paintLineCosts();
    }, 180);
  }
  function snapshot() {
    const s = JSON.parse(JSON.stringify(W.p));
    s.target_margin = num(s.cloud4c_margin) + num(s.ax_margin);   // kept for older readers
    return s;
  }

  // ── dirty state and navigation guard ──────────────────────────────────
  function markDirty(recalc = true) {
    W.dirty = true;
    const d = document.getElementById('ax-ws-dirty');
    if (d) d.hidden = false;
    if (recalc) calc();
  }
  window.addEventListener('beforeunload', e => { if (W.dirty && W.p) { e.preventDefault(); e.returnValue = ''; } });
  document.addEventListener('click', async e => {
    const a = e.target.closest('a[href]');
    if (!a || !W.dirty || a.target === '_blank' || e.metaKey || e.ctrlKey) return;
    const href = a.getAttribute('href');
    if (!href || a.hasAttribute('download') || /^(#|javascript:|blob:|data:|mailto:)/.test(href)) return;
    e.preventDefault();
    e.stopPropagation();
    const ok = await dialog({ title: 'Leave without saving?', body: '<p>Your changes to this project have not been saved as a version.</p>',
      confirmLabel: 'Leave without saving', cancelLabel: 'Stay', danger: true });
    if (ok) { W.dirty = false; window.location.href = href; }
  }, true);
  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
    if (e.key === 'Escape') closeDrawer();
  });

  // ── render: frame ─────────────────────────────────────────────────────
  function wsName() {
    const pr = P();
    return (W.meta.name || W.p._meta?.name || '').trim() || (pr.customer ? `${pr.customer} PnL` : 'New project');
  }

  function headHtml() {
    const pr = P();
    const n = W.versions.length;
    const latest = W.versions[0];
    const name = wsName();
    return `
      <div class="ax-ws-head">
        <div style="min-width:0;flex:1">
          <div class="ax-crumb"><a href="/">Projects</a> / ${esc(pr.customer || 'New project')}</div>
          <h1 class="ax-h1">${esc(name)}</h1>
          <div class="ax-ws-meta">
            <span class="ax-pill ax-pill--${String(pr.status || 'Draft').toLowerCase().replace(/\s+/g, '-')}">${esc(pr.status || 'Draft')}</span>
            ${pr.customer ? `<span>${esc(pr.customer)}</span>` : ''}${pr.stage ? `<span>${esc(pr.stage)}</span>` : ''}
            <span>${n ? `Version ${latest.version_no || n}, saved ${fmtDate(latest.saved_at)} by ${esc(latest.saved_by || '')}` : 'Not saved yet'}</span>
            <span class="ax-dirty" id="ax-ws-dirty" ${W.dirty ? '' : 'hidden'}>Unsaved changes</span>
          </div>
        </div>
        <div class="ax-ws-actions">
          <button type="button" class="ax-btn" data-act="versions" ${W.pid ? '' : 'disabled title="Save the project first"'}>${icon('history')}Versions</button>
          <button type="button" class="ax-btn" data-act="export">${icon('download')}Export Excel</button>
          <button type="button" class="ax-btn" data-act="saveas" ${W.pid ? '' : 'disabled title="Save the project first"'}>${icon('copy')}Save as new</button>
          <button type="button" class="ax-btn ax-btn--primary" data-act="save">${icon('save')}Save version</button>
        </div>
      </div>`;
  }

  // Header only: used while typing so the rest of the page (and any click in progress) is untouched.
  function updateHeader() {
    const h = document.getElementById('ax-ws-headwrap');
    if (h) h.innerHTML = headHtml();
    document.title = `${wsName()} | AutomatonsX`;
  }

  function render() {
    const tabs = [['resources', 'Resources', W.p.resources.length], ['costs', 'Other costs', W.p.one_time_costs.length],
      ['details', 'Details', null], ['notes', 'Notes', null]];
    root.innerHTML = `
      <div id="ax-ws-headwrap">${headHtml()}</div>
      <div id="ax-ws-banners">${banners()}</div>
      <div class="ax-ws">
        <section class="ax-panel" style="min-width:0">
          <div class="ax-tabs" role="tablist" style="padding:0 12px;margin:0">${tabs.map(([k, l, c]) =>
            `<button type="button" role="tab" data-tab="${k}" class="${W.tab === k ? 'is-active' : ''}" aria-selected="${W.tab === k}">${l}${c !== null ? `<span class="ax-count">${c}</span>` : ''}</button>`).join('')}</div>
          <div id="ax-ws-tab">${tabBody()}</div>
        </section>
        <aside class="ax-ledger" id="ax-ledger" aria-label="Price build-up"></aside>
      </div>`;
    renderLedger();
    paintLineCosts();
    document.title = `${wsName()} | AutomatonsX`;
  }

  function banners() {
    let out = '';
    const pinned = W.p.rate_card_version, pub = W.publishedVersion;
    if (W.pid && pinned && pub && pinned < pub) {
      out += `<div class="ax-banner" role="status">${icon('alert')}<span>This project prices with rate card <b>v${pinned}</b>. Rate card <b>v${pub}</b> has been published. Rates only change if you choose to update.</span>
        <button type="button" class="ax-btn ax-btn--small" data-act="ratediff">Review changes</button></div>`;
    }
    if (legacy()) {
      out += `<div class="ax-banner ax-banner--warn" role="status">${icon('alert')}<span>This project uses the old calculation, which leaves out travel, infra, third-party costs and the discount.</span>
        <button type="button" class="ax-btn ax-btn--small" data-act="switchmode">Switch to the new calculation</button></div>`;
    }
    return out;
  }

  function tabBody() {
    return { resources: resourcesTab, costs: costsTab, details: detailsTab, notes: notesTab }[W.tab]();
  }
  function rerenderTab() {
    const el = document.getElementById('ax-ws-tab');
    if (el) el.innerHTML = tabBody();
    root.querySelectorAll('[data-tab]').forEach(b => {
      const on = b.dataset.tab === W.tab;
      b.classList.toggle('is-active', on); b.setAttribute('aria-selected', on);
    });
    const counts = { resources: W.p.resources.length, costs: W.p.one_time_costs.length };
    root.querySelectorAll('[data-tab] .ax-count').forEach(c => { c.textContent = counts[c.parentElement.dataset.tab]; });
    paintLineCosts();
  }

  // ── Resources ─────────────────────────────────────────────────────────
  function resourcesTab() {
    const rows = W.p.resources.map((r, i) => {
      const c = category(r.group);
      const cats = W.cat.filter(x => x.active || x.name === r.group).map(x => x.name);
      if (r.group && !cats.includes(r.group)) cats.push(r.group);
      const roles = (c ? c.roles.filter(x => x.active || x.name === r.role) : []).map(x => x.name);
      if (r.role && !roles.includes(r.role)) roles.push(r.role);
      const levels = ratedLevels(r.group);
      if (r.level && !levels.includes(r.level)) levels.push(r.level);
      const lvOpts = levels.map(l => {
        const rt = rateFor(l, r.group);
        return `<option value="${esc(l)}" ${l === r.level ? 'selected' : ''}>${esc(l)}${rt != null ? `  ($${rt}/h)` : '  (no rate)'}</option>`;
      }).join('');
      return `<tr data-i="${i}">
        <td><select class="ax-input ax-cell-in" data-line="group" aria-label="Category">${options(cats, r.group)}</select></td>
        <td><select class="ax-input ax-cell-in" data-line="role" aria-label="Role">${options(roles, r.role)}</select></td>
        <td><select class="ax-input ax-cell-in" data-line="level" aria-label="Level">${lvOpts}</select></td>
        <td class="r"><input class="ax-input ax-cell-in num" style="width:96px" type="number" min="0" step="1" data-line="hours" value="${r.hours ?? ''}" aria-label="Hours"></td>
        <td class="r ax-faint" data-rate="${i}"></td>
        <td class="r" data-cost="${i}"></td>
        <td class="r"><button type="button" class="ax-btn ax-btn--ghost ax-btn--small ax-btn--icon" data-del-line="${i}" aria-label="Remove line">${icon('x')}</button></td>
      </tr>`;
    }).join('');
    const pinned = W.p.rate_card_version ? `rate card v${W.p.rate_card_version}` : 'the rates stored with this project';
    return `<div class="ax-section">
      <div class="ax-section-head"><div><h2 class="ax-h2">Resource plan</h2>
        <p>Pick a role and level. The hourly rate comes from ${pinned} and can't be typed over.</p></div></div>
      ${W.p.resources.length ? `<div class="ax-table-wrap"><table class="ax-table">
        <thead><tr><th>Category</th><th>Role</th><th>Level</th><th class="r">Hours</th><th class="r">Rate</th><th class="r">Cost</th><th><span class="ax-sr">Remove</span></th></tr></thead>
        <tbody>${rows}</tbody>
        <tfoot><tr><td colspan="3">Total</td><td class="r" id="ax-tot-hours"></td><td></td><td class="r" id="ax-tot-cost"></td><td></td></tr></tfoot></table></div>`
        : `<div class="ax-empty"><b>No resources yet</b>Add the first role to start building the cost basis.</div>`}
      <div style="margin-top:12px"><button type="button" class="ax-btn" data-act="addline">${icon('plus')}Add resource</button></div>
    </div>`;
  }
  function paintLineCosts() {
    const lines = W.result ? W.result.lines : [];
    W.p.resources.forEach((r, i) => {
      const l = lines.find(x => x.index === i);
      const rate = root.querySelector(`[data-rate="${i}"]`), cost = root.querySelector(`[data-cost="${i}"]`);
      if (rate) rate.innerHTML = !l ? '' : l.rate ? `$${l.rate}/h` : '<span class="ax-health ax-health--bad" title="This level has no rate for this category">No rate</span>';
      if (cost) cost.innerHTML = l ? `<b class="num">${money(l.cost)}</b>` : '';
    });
    const th = document.getElementById('ax-tot-hours'), tc = document.getElementById('ax-tot-cost');
    if (th && W.result) th.textContent = Math.round(W.result.hours).toLocaleString('en-US') + ' h';
    if (tc && W.result) tc.textContent = money(W.result.resources);
  }

  // ── Other costs ───────────────────────────────────────────────────────
  function costsTab() {
    const one = W.p.one_time_costs.map((x, i) => ({ x, i })).filter(o => o.x.category !== 'license');
    const lic = W.p.one_time_costs.map((x, i) => ({ x, i })).filter(o => o.x.category === 'license');
    const amount = i => `<input class="ax-input ax-cell-in num" style="width:140px" type="number" min="0" step="0.01" data-cost-amount="${i}" value="${W.p.one_time_costs[i].amount ?? ''}" aria-label="Amount in USD">`;
    const del = i => `<button type="button" class="ax-btn ax-btn--ghost ax-btn--small ax-btn--icon" data-del-cost="${i}" aria-label="Remove">${icon('x')}</button>`;
    const addon = (k, label) => {
      const field = { travel: 'travel_cost', infra: 'infra_cost', third_party: 'third_party_cost' }[k];
      const t = W.p.addon_treatment[k];
      return `<tr><td><b>${label}</b></td>
        <td><div class="ax-seg" role="group" aria-label="${label} pricing">
          <button type="button" data-addon="${k}" data-mode="margin" class="${t === 'margin' ? 'is-on' : ''}" aria-pressed="${t === 'margin'}">Apply margin</button>
          <button type="button" data-addon="${k}" data-mode="pass" class="${t === 'pass' ? 'is-on' : ''}" aria-pressed="${t === 'pass'}">Pass through</button></div></td>
        <td class="r"><input class="ax-input ax-cell-in num" style="width:140px" type="number" min="0" step="0.01" data-path="project.${field}" data-number value="${P()[field] ?? ''}" aria-label="${label} amount in USD"></td></tr>`;
    };
    return `
      <div class="ax-section"><div class="ax-section-head"><div><h2 class="ax-h2">One-time costs</h2><p>Fixed amounts such as knowledge transfer or workshops. Margin is applied to these.</p></div></div>
        ${one.length ? `<table class="ax-table"><thead><tr><th>Item</th><th class="r">Amount (USD)</th><th><span class="ax-sr">Remove</span></th></tr></thead><tbody>
          ${one.map(({ x, i }) => `<tr><td><input class="ax-input ax-cell-in" data-cost-label="${i}" value="${esc(x.label)}" placeholder="For example, Knowledge transfer" aria-label="Item"></td><td class="r">${amount(i)}</td><td class="r">${del(i)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="ax-faint" style="margin:0">None added.</p>'}
        <button type="button" class="ax-btn ax-btn--small" style="margin-top:10px" data-act="addone">${icon('plus')}Add one-time cost</button></div>
      <div class="ax-section"><div class="ax-section-head"><div><h2 class="ax-h2">Licenses and subscriptions</h2><p>Passed through to the customer at cost. No margin is applied.</p></div></div>
        ${lic.length ? `<table class="ax-table"><thead><tr><th>Item</th><th>Type</th><th class="r">Amount (USD)</th><th><span class="ax-sr">Remove</span></th></tr></thead><tbody>
          ${lic.map(({ x, i }) => `<tr><td><input class="ax-input ax-cell-in" data-cost-label="${i}" value="${esc(x.label)}" placeholder="For example, Fabric F64 capacity" aria-label="Item"></td>
            <td><select class="ax-input ax-cell-in" data-cost-type="${i}" aria-label="Type">${options(W.opts.license_types, x.license_type)}</select></td>
            <td class="r">${amount(i)}</td><td class="r">${del(i)}</td></tr>`).join('')}
        </tbody></table>` : '<p class="ax-faint" style="margin:0">None added.</p>'}
        <button type="button" class="ax-btn ax-btn--small" style="margin-top:10px" data-act="addlicense">${icon('plus')}Add license</button></div>
      <div class="ax-section"><div class="ax-section-head"><div><h2 class="ax-h2">Travel, infra and third-party</h2>
          <p>${legacy() ? 'The old calculation leaves these out of the price. Switch to the new calculation to include them.' : 'Choose how each one is priced. Both options flow into the contract value.'}</p></div></div>
        <table class="ax-table"><thead><tr><th>Item</th><th>Pricing</th><th class="r">Amount (USD)</th></tr></thead><tbody>
          ${addon('travel', 'Travel')}${addon('infra', 'Infra')}${addon('third_party', 'Third-party')}</tbody></table></div>`;
  }

  // ── Details and Notes ─────────────────────────────────────────────────
  function field(label, path, opts = {}) {
    const v = get(path) ?? '';
    const id = 'f-' + path.replace(/\./g, '-');
    let input;
    if (opts.list) {
      input = `<select class="ax-input" id="${id}" data-path="${path}">${options(opts.list, v, opts.blank ?? '')}</select>`;
    } else if (opts.textarea) {
      input = `<textarea class="ax-input" id="${id}" data-path="${path}" rows="${opts.rows || 3}">${esc(v)}</textarea>`;
    } else {
      input = `<input class="ax-input${opts.number ? ' num' : ''}" id="${id}" data-path="${path}" type="${opts.type || 'text'}" ${opts.number ? 'data-number min="0"' : ''}
        ${opts.datalist ? `list="${opts.datalist}"` : ''} value="${esc(v)}" ${opts.required ? 'required aria-required="true"' : ''}
        ${opts.error ? `aria-invalid="true" aria-describedby="${id}-err"` : ''}>`;
    }
    return `<div class="ax-field ${opts.wide ? 'ax-wide' : ''}"><label for="${id}">${label}${opts.required ? ' <span class="ax-req" aria-hidden="true">*</span>' : ''}</label>${input}
      ${opts.error ? `<span class="ax-error" id="${id}-err">${esc(opts.error)}</span>` : opts.hint ? `<span class="ax-hint">${esc(opts.hint)}</span>` : ''}</div>`;
  }
  function detailsTab() {
    const o = W.opts;
    const people = o.people.map(p => p.name);
    return `
      <div class="ax-section"><div class="ax-section-head"><h2 class="ax-h2">Customer and opportunity</h2></div><div class="ax-grid2">
        ${field('Customer name', 'project.customer', { required: true, error: W.customerError })}
        ${field('Project name', '_meta.name', { hint: 'Leave empty to use the customer name.' })}
        ${field('Location', 'project.location', { list: o.countries, blank: 'Choose a country' })}
        ${field('Folder', '_meta.folder', { datalist: 'ax-folders' })}
        ${field('Opportunity ID', 'project.opportunity_id')}
        ${field('Reference', 'project.reference')}
        ${field('Partner', 'project.partner')}
        ${field('Company', 'project.company')}
        ${field('Industry', 'project.industry', { list: o.industries, blank: 'Choose an industry' })}
        ${field('Project type', 'project.project_type', { list: o.project_types, blank: 'Choose a type' })}
      </div><datalist id="ax-folders">${W.folders.map(f => `<option value="${esc(f)}">`).join('')}</datalist></div>
      <div class="ax-section"><div class="ax-section-head"><h2 class="ax-h2">Pipeline</h2></div><div class="ax-grid3">
        ${field('Status', 'project.status', { list: o.statuses })}
        ${field('Stage', 'project.stage', { list: o.stages, blank: 'Choose a stage' })}
        ${field('Priority', 'project.priority', { list: o.priorities })}
        ${field('Business unit', 'project.business_unit', { list: o.business_units, blank: 'Choose a unit' })}
        ${field('Delivery model', 'project.delivery_model', { list: o.delivery_models, blank: 'Choose a model' })}
        ${field('Billing type', 'project.billing_type', { list: o.billing_types, blank: 'Choose a type' })}
        ${field('Duration (months)', 'project.duration_months', { number: true, type: 'number' })}
        ${field('Proposal date', 'project.proposal_date', { type: 'date' })}
        ${field('Quote currency', 'project.currency', { list: o.currencies, hint: 'Prices are calculated in USD.' })}
        ${field('Expected start', 'project.expected_start_date', { type: 'date' })}
        ${field('Expected end', 'project.expected_end_date', { type: 'date' })}
      </div></div>
      <div class="ax-section"><div class="ax-section-head"><div><h2 class="ax-h2">People</h2><p>Picked from the user list so names stay the same across projects.</p></div></div><div class="ax-grid3">
        ${field('Project owner', 'project.project_owner', { list: people, blank: 'No owner' })}
        ${field('Account manager', 'project.account_manager', { list: people, blank: 'None' })}
        ${field('Sales SPOC', 'project.sales_spoc', { list: people, blank: 'None' })}
        ${field('Delivery manager', 'project.delivery_manager', { list: people, blank: 'None' })}
        ${field('Technical lead', 'project.technical_lead', { list: people, blank: 'None' })}
      </div></div>
      <div class="ax-section"><div class="ax-section-head"><h2 class="ax-h2">Commercial terms</h2></div><div class="ax-grid2">
        ${field('Payment terms', 'project.payment_terms', { hint: 'For example, 30 days from invoice' })}
      </div></div>`;
  }
  function notesTab() {
    return `<div class="ax-section"><div class="ax-grid2">
      ${field('Description', 'project.project_description', { textarea: true, wide: true })}
      ${field('Risks', 'project.risks', { textarea: true, rows: 4 })}
      ${field('Dependencies', 'project.dependencies', { textarea: true, rows: 4 })}
      ${field('Internal notes', 'project.internal_notes', { textarea: true, rows: 4, wide: true })}
      ${field('Next action', 'project.next_action')}
      ${field('Next follow-up', 'project.next_follow_up_date', { type: 'date' })}
      ${field('Customer first touch point', 'project.customer_first_touch_point')}
    </div></div>`;
  }

  // ── Price build-up ────────────────────────────────────────────────────
  function renderLedger() {
    const el = document.getElementById('ax-ledger');
    if (!el || !W.p) return;
    const r = W.result, E = W.errors || {};
    const lever = (label, key, unit, value, step, opts = {}) => `<div class="ax-lever${E[key] ? ' has-error' : ''}">
        <label for="lv-${key}">${label}</label>
        <div class="ax-lever-in"><input id="lv-${key}" type="number" min="0" step="${step}" data-lever="${key}" value="${value}"
          ${opts.disabled ? 'disabled' : ''} ${E[key] ? `aria-invalid="true" aria-describedby="lv-${key}-err"` : ''}><span>${unit}</span></div>
        ${E[key] ? `<span class="ax-error" id="lv-${key}-err">${esc(E[key])}</span>` : opts.hint ? `<span class="ax-hint">${opts.hint}</span>` : ''}</div>`;
    const fxHint = W.liveFx ? `Live ${W.liveFx.toFixed(2)}${W.p.fx_rate !== W.liveFx ? ` · <button type="button" class="ax-link" data-act="livefx">Use live rate</button>` : ''}` : '';
    const rows = !r ? '<div class="ax-empty">Calculating…</div>' : `
      <div class="ax-lr"><span class="op"></span><span>Resources<span class="sub">${Math.round(r.hours).toLocaleString('en-US')} hours</span></span><span class="v">${money(r.resources)}</span></div>
      <div class="ax-lr"><span class="op">+</span><span>One-time costs</span><span class="v">${money(r.one_time)}</span></div>
      ${r.addons_margin ? `<div class="ax-lr"><span class="op">+</span><span>Add-ons with margin</span><span class="v">${money(r.addons_margin)}</span></div>` : ''}
      <div class="ax-lr total"><span class="op">=</span><span>Cost basis</span><span class="v">${money(r.cost_basis)}</span></div>
      <div class="ax-lr"><span class="op">+</span><span>Cloud4C margin<span class="sub">${pct(r.c4c_pct)} of list price</span></span><span class="v">${money(r.c4c_amount)}</span></div>
      <div class="ax-lr"><span class="op">+</span><span>AX margin<span class="sub">${pct(r.ax_pct)} of list price</span></span><span class="v">${money(r.ax_amount)}</span></div>
      <div class="ax-lr total"><span class="op">=</span><span>List price<span class="sub">Gross margin ${pct(r.gross_pct)}</span></span><span class="v">${money(r.list_price)}</span></div>
      ${r.discount ? `<div class="ax-lr"><span class="op">−</span><span>Discount<span class="sub">${pct(r.discount_pct)}, taken from AX margin</span></span><span class="v">${money(-r.discount)}</span></div>` : ''}
      <div class="ax-lr"><span class="op">+</span><span>Pass-through<span class="sub">Licenses ${money(r.licenses)}${r.addons_pass ? `, add-ons ${money(r.addons_pass)}` : ''}</span></span><span class="v">${money(r.pass_through)}</span></div>`;
    const ax = r ? r.ax_net_pct : 0, w = Math.max(0, Math.min(100, ax / (AX.thresholds.good * 2) * 100));
    el.innerHTML = `
      <div class="ax-ledger-h"><h2 class="ax-h2">Price build-up</h2>
        <p>${legacy() ? 'Old calculation' : 'Updates as you edit'} · ${W.p.rate_card_version ? `Rate card v${W.p.rate_card_version}` : 'Rates stored with the project'}</p></div>
      <div class="ax-levers">
        ${lever('Cloud4C margin', 'cloud4c_margin', '%', +(num(W.p.cloud4c_margin) * 100).toFixed(2), 0.5)}
        ${lever('AX margin', 'ax_margin', '%', +(num(W.p.ax_margin) * 100).toFixed(2), 0.5)}
        ${lever('Discount', 'discount_pct', '%', num(P().discount_pct), 0.5, legacy() ? { disabled: true, hint: 'Not counted in the old calculation' } : {})}
        ${lever('USD to INR', 'fx_rate', '₹', W.p.fx_rate == null || W.p.fx_rate === '' ? '' : +Number(W.p.fx_rate).toFixed(4), 0.01, { hint: fxHint })}
      </div>
      ${E._ ? `<div class="ax-section"><span class="ax-error">${esc(E._)}</span></div>` : ''}
      <div class="ax-rows ${Object.keys(E).length ? 'is-stale' : ''}">${rows}</div>
      ${r ? `<div class="ax-tcv ${Object.keys(E).length ? 'is-stale' : ''}"><div class="ax-label">Contract value</div><div class="ax-tcv-amt">${money(r.contract_value)}</div>
        <div class="ax-caption">${r.fx_rate > 0 ? `${inr(r.contract_inr)} at ₹${Number(r.fx_rate).toFixed(2)}` : 'Add a USD to INR rate to see rupees'}</div></div>
      <div class="ax-meter"><div class="ax-meter-top"><span>AX margin after discount</span><span class="ax-health ax-health--${health(ax)}">${pct(ax)}</span></div>
        <div class="ax-meter-track"><div class="ax-meter-fill ax-health--${health(ax)}" style="width:${w}%"></div><div class="ax-meter-tgt" style="left:50%"></div></div>
        <div class="ax-meter-cap"><span>0%</span><span>Target ${AX.thresholds.good}%</span><span>${AX.thresholds.good * 2}%</span></div></div>` : ''}
      <div class="ax-ledger-f"><button type="button" class="ax-btn ax-btn--small" data-ax-action="assistant"
          data-question="Explain how ${esc(P().customer || 'this project')} is priced">${icon('spark')}Explain</button>
        <button type="button" class="ax-btn ax-btn--small" data-act="export">${icon('download')}Excel</button></div>`;
  }

  // ── events ────────────────────────────────────────────────────────────
  root.addEventListener('click', e => {
    const t = e.target.closest('button');
    if (!t || t.disabled) return;
    if (t.dataset.tab) { W.tab = t.dataset.tab; rerenderTab(); return; }
    if (t.dataset.delLine) { W.p.resources.splice(+t.dataset.delLine, 1); rerenderTab(); markDirty(); return; }
    if (t.dataset.delCost) { W.p.one_time_costs.splice(+t.dataset.delCost, 1); rerenderTab(); markDirty(); return; }
    if (t.dataset.addon) { W.p.addon_treatment[t.dataset.addon] = t.dataset.mode; rerenderTab(); markDirty(); return; }
    switch (t.dataset.act) {
      case 'addline': W.p.resources.push(defaultLine()); rerenderTab(); markDirty(); break;
      case 'addone': W.p.one_time_costs.push({ label: '', amount: 0, category: 'one_time', exclude_from_margin: false }); rerenderTab(); markDirty(); break;
      case 'addlicense': W.p.one_time_costs.push({ label: '', amount: 0, category: 'license', exclude_from_margin: true, license_type: 'Other' }); rerenderTab(); markDirty(); break;
      case 'save': save(); break;
      case 'saveas': saveAsNew(); break;
      case 'versions': openDrawer(); break;
      case 'export': exportDialog(); break;
      case 'ratediff': rateDiff(); break;
      case 'switchmode': switchMode(); break;
      case 'livefx': W.p.fx_rate = W.liveFx; renderLedger(); markDirty(); break;
    }
  });

  root.addEventListener('input', e => {
    const t = e.target;
    if (t.dataset.lever) {
      const v = t.value === '' ? null : num(t.value);
      if (t.dataset.lever === 'discount_pct') P().discount_pct = v ?? 0;
      else if (t.dataset.lever === 'fx_rate') W.p.fx_rate = v;
      else W.p[t.dataset.lever] = v == null ? 0 : v / 100;
      markDirty();
      return;
    }
    if (t.dataset.path) {
      set(t.dataset.path, t.hasAttribute('data-number') ? (t.value === '' ? null : num(t.value)) : t.value);
      if (t.dataset.path === 'project.customer' && W.customerError && t.value.trim()) {
        W.customerError = ''; t.removeAttribute('aria-invalid');
        const err = document.getElementById(t.id + '-err'); if (err) err.remove();
      }
      markDirty(/cost|discount/.test(t.dataset.path));
      if (/status|stage|customer|_meta\.name/.test(t.dataset.path)) updateHeader();
      return;
    }
    const tr = t.closest('tr[data-i]');
    if (tr && t.dataset.line === 'hours') { W.p.resources[+tr.dataset.i].hours = t.value === '' ? 0 : Math.max(0, num(t.value)); markDirty(); return; }
    if (t.dataset.costAmount !== undefined) { W.p.one_time_costs[+t.dataset.costAmount].amount = Math.max(0, num(t.value)); markDirty(); return; }
    if (t.dataset.costLabel !== undefined) { W.p.one_time_costs[+t.dataset.costLabel].label = t.value; markDirty(false); }
  });

  root.addEventListener('change', e => {
    const t = e.target;
    const tr = t.closest('tr[data-i]');
    if (tr && ['group', 'role', 'level'].includes(t.dataset.line)) {
      const r = W.p.resources[+tr.dataset.i];
      r[t.dataset.line] = t.value;
      if (t.dataset.line === 'group') {
        const c = category(t.value);
        const role = c && (c.roles.find(x => x.active) || c.roles[0]);
        r.role = role ? role.name : ''; r.role_id = role ? role.id : null;
        const lv = ratedLevels(t.value);
        r.level = role && lv.includes(role.level) ? role.level : (lv[0] || '');
      }
      if (t.dataset.line === 'role') {
        const role = (category(r.group)?.roles || []).find(x => x.name === t.value);
        r.role_id = role ? role.id : null;
        if (role && ratedLevels(r.group).includes(role.level)) r.level = role.level;
      }
      setTimeout(rerenderTab, 0);
      markDirty();
      return;
    }
    if (t.dataset.costType !== undefined) { W.p.one_time_costs[+t.dataset.costType].license_type = t.value; markDirty(false); return; }
    if (t.dataset.path && /status|stage|customer|_meta\.name/.test(t.dataset.path)) updateHeader();
  });

  // ── save ──────────────────────────────────────────────────────────────
  async function save() {
    if (W.saving) return;
    if (!String(P().customer || '').trim()) {
      W.customerError = 'Enter the customer name before saving.';
      W.tab = 'details';
      rerenderTab();
      document.getElementById('f-project-customer')?.focus();
      return;
    }
    if (Object.keys(W.errors || {}).length) {
      toast('Fix the levers in the Price build-up before saving.', { error: true });
      return;
    }
    W.saving = true;
    const body = snapshot();
    body._meta = { ...(W.p._meta || {}), name: (W.p._meta?.name || '').trim() || `${P().customer.trim()} PnL` };
    try {
      const res = W.pid
        ? await api(`/api/projects/${encodeURIComponent(W.pid)}`, { method: 'PUT', body: JSON.stringify(body) })
        : await api('/api/projects', { method: 'POST', body: JSON.stringify(body) });
      const isNew = !W.pid;
      W.pid = res.id;
      W.meta = { ...W.meta, name: res.name };
      W.p._meta = { ...body._meta, id: res.id };
      W.dirty = false;
      await loadVersions();
      if (isNew) history.replaceState({}, '', '/projects/' + encodeURIComponent(res.id));
      render();
      const v = W.versions[0];
      toast(`Saved as version ${v ? v.version_no : 1}`);
    } catch (e) {
      toast(e.message || "The project couldn't be saved.", { error: true });
    } finally {
      W.saving = false;
    }
  }

  async function saveAsNew() {
    const res = await dialog({
      title: 'Save as new project',
      fields: [{ name: 'name', label: 'Project name', value: `${(W.meta.name || '').trim() || P().customer} (copy)`, required: true,
        hint: 'Creates a separate project with version 1. This project stays as it is.' }],
      validate: v => (v.name || '').trim() ? {} : { name: 'Enter a project name.' },
      confirmLabel: 'Create project',
    });
    if (!res) return;
    const body = snapshot();
    body._meta = { name: res.values.name.trim(), folder: W.p._meta?.folder || '' };
    try {
      const out = await api('/api/projects', { method: 'POST', body: JSON.stringify(body) });
      W.dirty = false;
      window.location.href = '/projects/' + encodeURIComponent(out.id);
    } catch (e) { toast(e.message, { error: true }); }
  }

  // ── banners: rate card update, calculation switch ─────────────────────
  async function rateDiff() {
    const from = W.p.rate_card_version, to = W.publishedVersion;
    let d;
    try { d = await api(`/api/rate-cards/diff?from=${from}&to=${to}&project_id=${encodeURIComponent(W.pid)}`); }
    catch (e) { toast(e.message, { error: true }); return; }
    const pr = d.project || { lines: [], cost_basis_change: 0, contract_value_change: 0 };
    const body = `<p>${pr.lines.length} of ${W.p.resources.length} resource lines change. The cost basis moves by <b>${money(pr.cost_basis_change)}</b>
      and the contract value by <b>${money(pr.contract_value_change)}</b>.</p>
      ${pr.lines.length ? `<div class="ax-table-wrap"><table class="ax-table"><thead><tr><th>Role</th><th>Level</th><th class="r">Now</th><th class="r">v${to}</th><th class="r">Cost change</th></tr></thead><tbody>
      ${pr.lines.map(l => `<tr><td>${esc(l.role)}</td><td>${esc(l.level)}</td><td class="r">$${l.from}</td><td class="r"><b>$${l.to}</b></td>
        <td class="r ${l.cost_change > 0 ? 'ax-health--bad' : 'ax-health--good'}">${l.cost_change > 0 ? '+' : ''}${money(l.cost_change)}</td></tr>`).join('')}</tbody></table></div>`
      : '<p class="ax-faint">None of this project\'s lines use a rate that changed.</p>'}`;
    const ok = await dialog({ title: `Rate card v${from} to v${to}`, body, confirmLabel: `Update to v${to}`, cancelLabel: `Keep v${from}` });
    if (!ok) return;
    W.p.rate_card = JSON.parse(JSON.stringify(W.publishedCard));
    W.p.rate_card_version = to;
    render();
    markDirty();
    toast(`Now pricing with rate card v${to}. Save to keep it.`);
  }

  async function switchMode() {
    let out;
    try {
      out = await api('/api/pnl/calculate', { method: 'POST', body: JSON.stringify({ snapshot: snapshot(), mode: 'legacy', compare_mode: 'v2' }) });
    } catch (e) { toast(e.message, { error: true }); return; }
    if (out.compare_errors) {
      toast('Fix the levers first: ' + Object.values(out.compare_errors).join(' '), { error: true });
      return;
    }
    const a = out.result, b = out.compare;
    const ok = await dialog({
      title: 'Switch to the new calculation?',
      body: `<p>The new calculation counts travel, infra and third-party costs and takes the discount off the list price.</p>
        <table class="ax-table"><thead><tr><th></th><th class="r">Old</th><th class="r">New</th></tr></thead><tbody>
        <tr><td>Contract value</td><td class="r">${money(a.contract_value)}</td><td class="r"><b>${money(b.contract_value)}</b></td></tr>
        <tr><td>AX margin after discount</td><td class="r">${pct(a.ax_net_pct)}</td><td class="r"><b>${pct(b.ax_net_pct)}</b></td></tr></tbody></table>
        <p class="ax-caption">Takes effect when you save. Earlier versions keep the old calculation.</p>`,
      confirmLabel: 'Switch calculation',
    });
    if (!ok) return;
    W.p.calc_mode = 'v2';
    render();
    markDirty();
  }

  // ── versions drawer and compare ───────────────────────────────────────
  let selected = [];
  function closeDrawer() { document.getElementById('ax-drawer')?.remove(); }
  async function openDrawer() {
    closeDrawer();
    await loadVersions();
    selected = [];
    const vs = W.versions;
    const rows = vs.map((v, i) => {
      const prev = vs[i + 1];
      const cv = v.pnl?.contract_value, pv = prev?.pnl?.contract_value;
      const d = (cv != null && pv != null) ? cv - pv : null;
      return `<div class="ax-ver ${i === 0 ? 'is-current' : ''}">
        <input type="checkbox" data-sel="${esc(v.vid)}" aria-label="Select version ${v.version_no}">
        <div style="min-width:0"><b>Version ${v.version_no}${i === 0 ? ' (latest)' : ''}</b>
          <input class="ax-input ax-cell-in" style="height:28px;margin:2px 0 2px -8px" placeholder="Add a label" value="${esc(v.label)}" data-label="${esc(v.vid)}" aria-label="Label for version ${v.version_no}">
          <div class="ax-caption">${fmtDateTime(v.saved_at)} by ${esc(v.saved_by || '')}${v.rate_card_version ? `, rates v${v.rate_card_version}` : ''}${v.pnl && !v.pnl.error ? `, AX ${pct(v.pnl.ax_net_pct)}` : ''}${v.calc_mode === 'legacy' ? '' : ', new calculation'}</div></div>
        <div style="text-align:right"><b class="num">${cv != null ? moneyK(cv) : ''}</b>
          <div class="ax-caption num ${d > 0 ? 'ax-health--good' : d < 0 ? 'ax-health--bad' : ''}">${d == null ? 'first save' : d === 0 ? 'no change' : (d > 0 ? '+' : '−') + moneyK(Math.abs(d))}</div>
          ${i ? `<button type="button" class="ax-btn ax-btn--ghost ax-btn--small" data-restore="${esc(v.vid)}">Restore</button>` : ''}</div>
      </div>`;
    }).join('');
    const el = document.createElement('div');
    el.id = 'ax-drawer';
    el.className = 'ax-drawer';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-label', 'Versions');
    el.innerHTML = `<div class="ax-drawer-h">${icon('history')}<h2 class="ax-h2" style="flex:1">Versions</h2>
        <button type="button" class="ax-btn ax-btn--ghost ax-btn--icon" data-close aria-label="Close">${icon('x')}</button></div>
      <div class="ax-drawer-ctx">Every save keeps a full snapshot. Versions are never deleted. Pick two to compare.</div>
      <div class="ax-drawer-b">${rows || '<div class="ax-empty"><b>No versions yet</b>Save the project to create version 1.</div>'}</div>
      <div class="ax-drawer-f"><button type="button" class="ax-btn ax-btn--primary" data-compare disabled>${icon('compare')}Compare selected</button></div>`;
    document.body.appendChild(el);
    el.querySelector('[data-close]').focus();
    el.addEventListener('click', async e => {
      const t = e.target.closest('button');
      if (!t) return;
      if (t.hasAttribute('data-close')) closeDrawer();
      if (t.dataset.restore) restore(t.dataset.restore);
      if (t.hasAttribute('data-compare')) compareSelected();
    });
    el.addEventListener('change', async e => {
      const t = e.target;
      if (t.dataset.sel !== undefined) {
        selected = t.checked ? [...selected, t.dataset.sel].slice(-2) : selected.filter(x => x !== t.dataset.sel);
        el.querySelectorAll('[data-sel]').forEach(c => { c.checked = selected.includes(c.dataset.sel); });
        el.querySelector('[data-compare]').disabled = selected.length !== 2;
      }
      if (t.dataset.label !== undefined) {
        try {
          await api(`/api/projects/${encodeURIComponent(W.pid)}/versions/${encodeURIComponent(t.dataset.label)}/label`,
            { method: 'POST', body: JSON.stringify({ label: t.value.trim() }) });
          toast('Label saved');
        } catch (err) { toast(err.message, { error: true }); }
      }
    });
  }

  async function restore(vid) {
    const v = W.versions.find(x => x.vid === vid);
    const ok = await dialog({ title: `Restore version ${v.version_no}?`,
      body: `<p>Version ${v.version_no} loads into the editor as unsaved changes. Saving it creates a new version, so nothing in the history is overwritten.</p>`,
      confirmLabel: `Restore version ${v.version_no}` });
    if (!ok) return;
    try {
      const snap = await api(`/api/projects/${encodeURIComponent(W.pid)}/versions/${encodeURIComponent(vid)}`);
      const meta = W.p._meta;
      W.p = normalise(snap);
      W.p._meta = meta;
      closeDrawer();
      W.dirty = true;
      render();
      calc();
      toast(`Version ${v.version_no} restored. Save to keep it.`);
    } catch (e) { toast(e.message, { error: true }); }
  }

  async function compareSelected() {
    const [x, y] = selected.map(vid => W.versions.find(v => v.vid === vid)).sort((a, b) => a.version_no - b.version_no);
    let d;
    try { d = await api(`/api/projects/${encodeURIComponent(W.pid)}/compare?a=${encodeURIComponent(x.vid)}&b=${encodeURIComponent(y.vid)}`); }
    catch (e) { toast(e.message, { error: true }); return; }
    const A = d.a || {}, B = d.b || {};
    const row = (label, a, b, f) => {
      const diff = (b ?? 0) - (a ?? 0);
      return `<tr><td>${label}</td><td class="r num">${f(a)}</td><td class="r num">${f(b)}</td>
        <td class="r num ${diff > 0 ? 'ax-health--good' : diff < 0 ? 'ax-health--bad' : 'ax-faint'}">${diff === 0 ? 'no change' : (diff > 0 ? '+' : '') + f(diff)}</td></tr>`;
    };
    const hrs = v => Math.round(v || 0).toLocaleString('en-US');
    const body = `<div class="ax-grid2" style="align-items:start">
      <div><h3 class="ax-label" style="margin:0 0 8px">Numbers</h3><table class="ax-table"><thead><tr><th></th><th class="r">v${x.version_no}</th><th class="r">v${y.version_no}</th><th class="r">Change</th></tr></thead><tbody>
        ${row('Cost basis', A.cost_basis, B.cost_basis, money)}${row('List price', A.list_price, B.list_price, money)}
        ${row('Contract value', A.contract_value, B.contract_value, money)}${row('Cloud4C margin', A.c4c_pct, B.c4c_pct, pct)}
        ${row('AX margin', A.ax_pct, B.ax_pct, pct)}${row('Discount', num(d.discount[0]), num(d.discount[1]), pct)}${row('Hours', A.hours, B.hours, hrs)}
      </tbody></table></div>
      <div><h3 class="ax-label" style="margin:0 0 8px">Resource changes</h3>${d.resource_changes.length ? `<table class="ax-table"><thead><tr><th>Role</th><th class="r">v${x.version_no} h</th><th class="r">v${y.version_no} h</th></tr></thead><tbody>
        ${d.resource_changes.map(c => `<tr><td>${esc(c.role)}<div class="ax-caption">${esc(c.category)}, ${esc(c.level)}</div></td>
          <td class="r num">${c.hours_a ? hrs(c.hours_a) : 'none'}</td><td class="r num"><b>${c.hours_b ? hrs(c.hours_b) : 'removed'}</b></td></tr>`).join('')}
      </tbody></table>` : '<p class="ax-faint">No resource changes.</p>'}</div></div>`;
    const dlg = dialog({ title: `Version ${x.version_no} and version ${y.version_no}`, body, confirmLabel: 'Close', cancelLabel: null });
    const box = document.querySelector('.ax-dialog');
    box?.classList.add('ax-dialog--wide');
    if (window.axAssistant) {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'ax-btn';
      b.innerHTML = `${icon('spark')}Summarise changes`;
      b.addEventListener('click', () => {
        box.querySelector('[type=submit]').click();
        window.axAssistant.open(`What changed between version ${x.version_no} and version ${y.version_no} of ${P().customer || W.pid}?`);
      });
      box?.querySelector('.ax-dialog-f').prepend(b);
    }
    await dlg;
  }

  // ── export ────────────────────────────────────────────────────────────
  async function exportDialog() {
    await loadVersions();
    const total = W.versions.length;
    const defName = no => `${P().customer || 'PnL'} PnL${no ? ' v' + no : ''}`;
    const res = await dialog({
      title: 'Export Excel',
      fields: [{ name: 'name', label: 'File name', value: W.p.export_filename || defName(W.dirty || !total ? null : W.versions[0].version_no),
        hint: 'Uses the Benline PnL template. The name is kept with this project when you save it.' }],
      body: `<div class="ax-field"><label for="ax-exp-version">Version</label><select class="ax-input" id="ax-exp-version" name="version">
        ${W.dirty || !total ? '<option value="">Changes on screen (not saved yet)</option>' : ''}
        ${W.versions.map(v => `<option value="${esc(v.vid)}">Version ${v.version_no}${v.label ? ', ' + esc(v.label) : ''} (${fmtDateTime(v.saved_at)})</option>`).join('')}
      </select></div>`,
      validate: v => (v.name || '').trim() ? {} : { name: 'Enter a file name.' },
      confirmLabel: 'Download',
    });
    if (!res) return;
    const name = res.values.name.trim();
    let payload = snapshot();
    if (res.values.version) {
      try { payload = await api(`/api/projects/${encodeURIComponent(W.pid)}/versions/${encodeURIComponent(res.values.version)}`); }
      catch (e) { toast(e.message, { error: true }); return; }
    }
    if (W.p.export_filename !== name) { W.p.export_filename = name; markDirty(false); }
    try {
      const r = await fetch('/api/export', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, download_name: name }) });
      if (!r.ok) { toast(await errorMessage(r, 'The export could not be created.'), { error: true }); return; }
      const blob = await r.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = name + '.xlsx';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      toast(`Downloaded ${name}.xlsx`);
    } catch { toast("The export couldn't reach the server. Check your connection and try again.", { error: true }); }
  }

  // A what-if from the assistant, loaded as unsaved changes (nothing is saved until Save version).
  async function applyScenario(rerender = true) {
    let s = null;
    try { s = JSON.parse(sessionStorage.getItem('ax-scenario') || 'null'); sessionStorage.removeItem('ax-scenario'); } catch { /* none */ }
    history.replaceState({}, '', location.pathname);
    if (!s || s.project_id !== W.pid) return;
    try {
      const snap = await api(`/api/projects/${encodeURIComponent(W.pid)}/scenario`, { method: 'POST', body: JSON.stringify({ overrides: s.overrides }) });
      const meta = W.p._meta;
      delete snap.published_rate_card_version;
      W.p = normalise(snap);
      W.p._meta = meta;
      W.dirty = true;
      if (rerender) { render(); calc(); }
      toast('Scenario loaded as unsaved changes. Save version to keep it.');
    } catch (e) { toast(e.message, { error: true }); }
  }
  W.applyScenario = () => applyScenario(true);

  load().catch(e => {
    root.innerHTML = `<div class="ax-panel"><div class="ax-empty"><b>${e.status === 404 ? 'This project does not exist' : "The project couldn't load"}</b>
      ${esc(e.message)}<div><a class="ax-btn ax-btn--small" href="/">Back to projects</a></div></div></div>`;
  });
  window.axWorkspace = W;
})();
