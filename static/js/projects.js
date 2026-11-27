// Projects list (DESIGN.md 5.2). Renders into #all-projects-container and replaces the
// legacy All Projects renderer in app.js (window.loadAllProjects is reassigned below).
(function () {
  'use strict';
  const { esc, toast, dialog, popover, closePopover, errorMessage } = window.axUI;
  const AX = window.AX || { thresholds: { good: 20, warn: 10 }, user: {} };

  const FILTERS = [
    ['status', 'Status'], ['business_unit', 'Business unit'], ['owner', 'Owner'], ['folder', 'Folder'],
  ];
  const VIEWS = [['all', 'All projects'], ['mine', 'Mine'], ['attention', 'Below AX target']];

  const state = {
    list: null, archivedCount: null, loading: false,
    view: 'all', q: '',
    filters: { status: [], business_unit: [], owner: [], folder: [] },
    cols: null, sort: { key: 'updated', dir: 'desc' },
    group: true,                 // one row per customer with 2+ projects, expandable
    expanded: new Set(),         // customer keys opened in this visit
    storedPrefs: {},             // keys other screens keep in the same preference (dashboard dates)
  };

  // ── formatting ─────────────────────────────────────────────────────────
  const money = n => (n == null || isNaN(n)) ? '' : '$' + Math.round(n).toLocaleString('en-US');
  const pct = n => (n == null || isNaN(n)) ? '' : (Math.round(n * 10) / 10).toFixed(1) + '%';
  const health = v => v >= AX.thresholds.good ? 'good' : v >= AX.thresholds.warn ? 'warn' : 'bad';
  const statusName = s => {
    const v = String(s || '').trim();
    if (!v) return 'Draft';
    return v.toLowerCase() === 'on hold' ? 'On hold' : v;          // DESIGN.md 10: sentence case
  };
  const statusSlug = s => statusName(s).toLowerCase().replace(/\s+/g, '-');
  const fmtDate = v => {
    if (!v) return '';
    const d = new Date(String(v).replace(' ', 'T'));
    return isNaN(d) ? esc(v) : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  };
  const owner = p => (p.project_owner || '').trim();
  const mark = text => {
    const s = String(text ?? '');
    if (!state.q) return esc(s);
    const i = s.toLowerCase().indexOf(state.q.toLowerCase());
    if (i < 0) return esc(s);
    return esc(s.slice(0, i)) + '<mark class="ax-mark">' + esc(s.slice(i, i + state.q.length)) + '</mark>' + esc(s.slice(i + state.q.length));
  };
  const n = (p, k) => Number(p.pnl?.[k] ?? 0);

  // ── columns ────────────────────────────────────────────────────────────
  // fixed: always shown. default: shown until the user changes columns.
  const COLS = [
    { key: 'project', label: 'Customer and project', fixed: true, sort: p => (p.customer || p.name || '').toLowerCase(),
      cell: p => `<div class="ax-two-line"><b>${mark(p.customer || 'No customer')}</b><span>${mark(p.name)}</span></div>` },
    { key: 'status', label: 'Status', default: true, sort: p => statusName(p.status),
      cell: p => `<span class="ax-pill ax-pill--${statusSlug(p.status)}">${esc(statusName(p.status))}</span>` },
    { key: 'stage', label: 'Stage', default: true, sort: p => p.stage || '', cell: p => esc(p.stage || '') },
    { key: 'business_unit', label: 'Unit', default: true, sort: p => p.business_unit || '', cell: p => esc(p.business_unit || '') },
    { key: 'owner', label: 'Owner', default: true, sort: p => owner(p).toLowerCase(),
      cell: p => owner(p) ? mark(owner(p)) : '<span class="ax-faint">No owner</span>' },
    { key: 'contract_value', label: 'Contract value', fixed: true, num: true, sort: p => n(p, 'contract_value'),
      cell: p => `<b>${money(n(p, 'contract_value'))}</b>` },
    { key: 'ax_margin', label: 'AX margin', fixed: true, num: true, sort: p => n(p, 'ax_net_pct'),
      cell: p => p.pnl?.error ? '<span class="ax-faint">Check levers</span>'
        : `<span class="ax-health ax-health--${health(n(p, 'ax_net_pct'))}">${pct(n(p, 'ax_net_pct'))}</span>` },
    { key: 'version', label: 'Version', default: true, sort: p => p.version_count || 0,
      cell: p => p.version_count ? `v${p.version_count}` : '<span class="ax-faint">Not saved</span>' },
    { key: 'updated', label: 'Updated', default: true, sort: p => p.saved_at || '',
      cell: p => `<div class="ax-two-line"><span style="color:var(--ink)">${fmtDate(p.saved_at)}</span><span>${esc(p.saved_by || '')}</span></div>` },
    // optional (from the old layout manager)
    { key: 'folder', label: 'Folder', group: 'Details', sort: p => p.folder || '', cell: p => mark(p.folder || '') },
    { key: 'location', label: 'Location', group: 'Details', sort: p => p.location || '', cell: p => esc(p.location || '') },
    { key: 'partner', label: 'Partner', group: 'Details', sort: p => p.partner || '', cell: p => esc(p.partner || '') },
    { key: 'industry', label: 'Industry', group: 'Details', sort: p => p.industry || '', cell: p => esc(p.industry || '') },
    { key: 'reference', label: 'Reference', group: 'Details', sort: p => p.reference || '', cell: p => esc(p.reference || '') },
    { key: 'opportunity_id', label: 'Opportunity ID', group: 'Details', sort: p => p.opportunity_id || '', cell: p => esc(p.opportunity_id || '') },
    { key: 'priority', label: 'Priority', group: 'Pipeline', sort: p => p.priority || '', cell: p => esc(p.priority || '') },
    { key: 'delivery_model', label: 'Delivery model', group: 'Pipeline', sort: p => p.delivery_model || '', cell: p => esc(p.delivery_model || '') },
    { key: 'billing_type', label: 'Billing type', group: 'Pipeline', sort: p => p.billing_type || '', cell: p => esc(p.billing_type || '') },
    { key: 'proposal_date', label: 'Proposal date', group: 'Pipeline', sort: p => p.proposal_date || '', cell: p => fmtDate(p.proposal_date) },
    { key: 'expected_start_date', label: 'Start', group: 'Pipeline', sort: p => p.expected_start_date || '', cell: p => fmtDate(p.expected_start_date) },
    { key: 'expected_end_date', label: 'End', group: 'Pipeline', sort: p => p.expected_end_date || '', cell: p => fmtDate(p.expected_end_date) },
    { key: 'next_follow_up_date', label: 'Next follow-up', group: 'Pipeline', sort: p => p.next_follow_up_date || '', cell: p => fmtDate(p.next_follow_up_date) },
    { key: 'account_manager', label: 'Account manager', group: 'People', sort: p => p.account_manager || '', cell: p => esc(p.account_manager || '') },
    { key: 'sales_spoc', label: 'Sales SPOC', group: 'People', sort: p => p.sales_spoc || '', cell: p => esc(p.sales_spoc || '') },
    { key: 'delivery_manager', label: 'Delivery manager', group: 'People', sort: p => p.delivery_manager || '', cell: p => esc(p.delivery_manager || '') },
    { key: 'cost_basis', label: 'Cost basis', group: 'Numbers', num: true, sort: p => n(p, 'cost_basis'), cell: p => money(n(p, 'cost_basis')) },
    { key: 'list_price', label: 'List price', group: 'Numbers', num: true, sort: p => n(p, 'list_price'), cell: p => money(n(p, 'list_price')) },
    { key: 'markup', label: 'Markup', group: 'Numbers', num: true, sort: p => n(p, 'list_price') - n(p, 'cost_basis'), cell: p => money(n(p, 'list_price') - n(p, 'cost_basis')) },
    { key: 'c4c_margin', label: 'Cloud4C margin', group: 'Numbers', num: true, sort: p => n(p, 'c4c_pct'), cell: p => pct(n(p, 'c4c_pct')) },
    { key: 'gross_margin', label: 'Gross margin', group: 'Numbers', num: true, sort: p => n(p, 'gross_pct'), cell: p => pct(n(p, 'gross_pct')) },
    { key: 'discount', label: 'Discount', group: 'Numbers', num: true, sort: p => Number(p.discount_pct || 0), cell: p => p.discount_pct ? pct(Number(p.discount_pct)) : '' },
    { key: 'hours', label: 'Hours', group: 'Numbers', num: true, sort: p => Number(p.total_hours || 0), cell: p => Math.round(p.total_hours || 0).toLocaleString('en-US') },
    { key: 'resources', label: 'Resource lines', group: 'Numbers', num: true, sort: p => p.resource_count || 0, cell: p => p.resource_count || 0 },
    { key: 'risks', label: 'Risks', group: 'Notes', sort: p => p.risks || '', cell: p => esc((p.risks || '').slice(0, 80)) },
    { key: 'next_action', label: 'Next action', group: 'Notes', sort: p => p.next_action || '', cell: p => esc(p.next_action || '') },
  ];
  const colByKey = Object.fromEntries(COLS.map(c => [c.key, c]));
  const defaultCols = () => COLS.filter(c => c.fixed || c.default).map(c => c.key);

  // ── preferences (saved per user in the database) ───────────────────────
  let prefsLoaded = false, saveTimer = null, prefsWritable = true;
  async function loadPrefs() {
    if (prefsLoaded) return;
    prefsLoaded = true;
    try {
      const res = await fetch('/api/prefs/projects_list');
      if (res.ok) {
        const p = await res.json();
        state.storedPrefs = p || {};
        if (typeof p.group === 'boolean') state.group = p.group;
        if (Array.isArray(p.cols)) state.cols = p.cols.filter(k => colByKey[k]);
        if (p.view && VIEWS.some(v => v[0] === p.view)) state.view = p.view;
        if (p.sort && colByKey[p.sort.key]) state.sort = p.sort;
        if (p.filters) for (const [k] of FILTERS) if (Array.isArray(p.filters[k])) state.filters[k] = p.filters[k];
      }
    } catch { /* defaults */ }
    if (!state.cols || !state.cols.length) state.cols = defaultCols();
    COLS.filter(c => c.fixed && !state.cols.includes(c.key)).forEach(c => state.cols.push(c.key));
  }
  function savePrefs() {
    if (!prefsWritable) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      try {
        const res = await fetch('/api/prefs/projects_list', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...state.storedPrefs, cols: state.cols, view: state.view, sort: state.sort,
                                 filters: { ...(state.storedPrefs.filters || {}), ...state.filters }, group: state.group }),
        });
        if (res.status === 503) prefsWritable = false;      // database not migrated yet: keep for this visit only
      } catch { /* offline: the choice still applies on this page */ }
    }, 600);
  }

  // ── data ───────────────────────────────────────────────────────────────
  function viewMatch(p, view) {
    if (view === 'mine') {
      const me = (AX.user.name || '').toLowerCase(), uid = (AX.user.username || '').toLowerCase();
      const o = owner(p).toLowerCase();
      return (o && (o === me || o === uid)) || (!o && (p.saved_by || '').toLowerCase() === uid);
    }
    if (view === 'attention') return statusName(p.status) !== 'Lost' && !p.pnl?.error && n(p, 'contract_value') > 0 && n(p, 'ax_net_pct') < AX.thresholds.good;
    return true;
  }
  const filterValue = (p, k) => k === 'status' ? statusName(p.status) : k === 'owner' ? owner(p) : (p[k] || '');
  function searchMatch(p) {
    if (!state.q) return true;
    const q = state.q.toLowerCase();
    return [p.customer, p.name, owner(p), p.folder].some(v => String(v || '').toLowerCase().includes(q));
  }
  function filtered(view = state.view, except = null) {
    return (state.list || []).filter(p => viewMatch(p, view) && searchMatch(p) &&
      FILTERS.every(([k]) => k === except || !state.filters[k].length || state.filters[k].includes(filterValue(p, k))));
  }
  function sorted(list) {
    const c = colByKey[state.sort.key] || colByKey.updated;
    const dir = state.sort.dir === 'asc' ? 1 : -1;
    return list.slice().sort((a, b) => {
      const x = c.sort(a), y = c.sort(b);
      return (x < y ? -1 : x > y ? 1 : 0) * dir;
    });
  }

  // Shares the query with the top-bar search (kept by app.js in this browser).
  const rememberSearch = () => { if (typeof saveAllProjectsSearch === 'function') saveAllProjectsSearch(state.q); };

  // ── grouping by customer ───────────────────────────────────────────────
  const customerKey = p => (p.customer || '').trim().toLowerCase() || '__' + p.id;
  function groups(sortedList) {
    const map = new Map();
    sortedList.forEach(p => {                                   // groups keep the sort order of their first project
      const k = customerKey(p);
      if (!map.has(k)) map.set(k, { key: k, customer: p.customer || p.name, items: [] });
      map.get(k).items.push(p);
    });
    return [...map.values()];
  }
  function groupCell(g, c) {
    const items = g.items;
    switch (c.key) {
      case 'project':
        return `<div class="ax-group-name">${icon('back').replace('ax-i', 'ax-i ax-chev')}<div class="ax-two-line"><b>${mark(g.customer)}</b>
          <span>${items.length} projects</span></div></div>`;
      case 'status': {
        const counts = {};
        items.forEach(p => { const s = statusName(p.status); counts[s] = (counts[s] || 0) + 1; });
        return Object.entries(counts).map(([s, n]) => `<span class="ax-pill ax-pill--${statusSlug(s)}">${n} ${esc(s)}</span>`).join(' ');
      }
      case 'contract_value':
        return `<b>${money(items.reduce((t, p) => t + n(p, 'contract_value'), 0))}</b><span class="ax-caption ax-block">total</span>`;
      case 'ax_margin': {
        const vals = items.filter(p => !p.pnl?.error && n(p, 'contract_value') > 0).map(p => n(p, 'ax_net_pct'));
        if (!vals.length) return '';
        const lo = Math.min(...vals), hi = Math.max(...vals);
        return `<span class="ax-health ax-health--${health(lo)}">${lo === hi ? pct(lo) : pct(lo) + '–' + pct(hi)}</span>`;
      }
      case 'version':
        return `<span class="ax-faint">${items.reduce((t, p) => t + (p.version_count || 0), 0)} saved</span>`;
      case 'updated': {
        const latest = items.reduce((a, p) => ((p.saved_at || '') > (a.saved_at || '') ? p : a), items[0]);
        return `<div class="ax-two-line"><span style="color:var(--ink)">${fmtDate(latest.saved_at)}</span><span>latest</span></div>`;
      }
      default: {
        const vals = [...new Set(items.map(p => String(c.sort(p) ?? '')).filter(Boolean))];
        return vals.length === 1 && !c.num ? c.cell(items[0]) : '';
      }
    }
  }
  function groupRow(g, cols, open, no) {
    return `<tr class="ax-group-row${open ? ' is-open' : ''}" data-group="${esc(g.key)}" tabindex="0" aria-expanded="${open}"
        title="${open ? 'Hide' : 'Show'} the ${g.items.length} projects for ${esc(g.customer)}">
      <td class="ax-sno">${no}</td>${cols.map(c => `<td class="${c.num ? 'r' : ''}">${groupCell(g, c)}</td>`).join('')}<td></td></tr>`;
  }
  const childCell = p => `<div class="ax-two-line ax-child-cell"><b>${mark(p.name)}</b><span>${esc(p.folder || p.stage || '')}</span></div>`;

  // ── render ─────────────────────────────────────────────────────────────
  const root = () => document.getElementById('all-projects-container');
  const anyFilter = () => !!state.q || FILTERS.some(([k]) => state.filters[k].length);

  function renderShell() {
    const el = root();
    if (!el) return;
    el.innerHTML = `
      <div class="ax-page-head">
        <div><h1 class="ax-h1">Projects</h1><p>Every saved proposal with its latest numbers. Open one to edit its resource plan and pricing.</p></div>
        <div class="ax-actions">
          <label class="ax-btn" for="ax-import-file" title="Import a project from an Excel PnL">Import project</label>
          <input type="file" id="ax-import-file" accept=".xlsx,.xlsm" hidden onchange="importExcel(this)">
          <button type="button" class="ax-btn ax-btn--primary" data-act="new">${icon('plus')}New project</button>
        </div>
      </div>
      <div class="ax-tabs" role="tablist" id="ax-proj-views"></div>
      <section class="ax-panel">
        <div class="ax-toolbar">
          <label class="ax-search ax-filter-search">${icon('search')}
            <input id="ax-proj-q" type="search" placeholder="Customer, project, owner" aria-label="Filter projects" value="${esc(state.q)}"></label>
          ${FILTERS.map(([k, l]) => `<button type="button" class="ax-chip" data-filter="${k}" aria-haspopup="true" aria-expanded="false">${l}</button>`).join('')}
          <button type="button" class="ax-btn ax-btn--ghost ax-btn--small" data-act="clear" hidden>Clear</button>
          <div class="ax-spacer"></div>
          <button type="button" class="ax-chip" data-act="group" aria-pressed="false">Group by customer</button>
          <button type="button" class="ax-btn ax-btn--small" data-act="columns" aria-haspopup="true" aria-expanded="false">${icon('columns')}Columns</button>
        </div>
        <div class="ax-table-wrap" id="ax-proj-table"></div>
      </section>
      <p class="ax-caption" id="ax-proj-archive-note" style="margin:12px 4px 0"></p>`;
    el.querySelector('#ax-proj-q').addEventListener('input', e => { state.q = e.target.value.trim(); rememberSearch(); renderBody(); });
  }

  function icon(name) {
    const tpl = document.getElementById('ax-icon-' + name);
    return tpl ? tpl.innerHTML : '';
  }

  function renderBody() {
    const el = root();
    if (!el || !state.list) return;
    // view tabs with counts (counts respect search and filters)
    el.querySelector('#ax-proj-views').innerHTML = VIEWS.map(([k, l]) =>
      `<button type="button" role="tab" data-view="${k}" class="${state.view === k ? 'is-active' : ''}" aria-selected="${state.view === k}">${l}<span class="ax-count">${filtered(k).length}</span></button>`).join('');
    // chips
    el.querySelectorAll('[data-filter]').forEach(b => {
      const k = b.dataset.filter, c = state.filters[k].length, label = FILTERS.find(f => f[0] === k)[1];
      b.classList.toggle('is-set', c > 0);
      b.innerHTML = `${label}${c ? ` <b>${c}</b>` : ''}`;
    });
    el.querySelector('[data-act="clear"]').hidden = !anyFilter();
    const gb = el.querySelector('[data-act="group"]');
    gb.classList.toggle('is-set', state.group);
    gb.setAttribute('aria-pressed', String(state.group));
    const list = sorted(filtered());
    const cols = state.cols.map(k => colByKey[k]).filter(Boolean);
    const table = el.querySelector('#ax-proj-table');
    if (!state.list.length) {
      table.innerHTML = `<div class="ax-empty"><b>No projects yet</b>Create one with New project.</div>`;
    } else if (!list.length) {
      table.innerHTML = `<div class="ax-empty"><b>No projects match</b>Try a different search or clear the filters.
        <div><button type="button" class="ax-btn ax-btn--small" data-act="clear">Clear filters</button></div></div>`;
    } else {
      const head = cols.map(c => {
        const on = state.sort.key === c.key;
        return `<th class="${c.num ? 'r' : ''}" aria-sort="${on ? (state.sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}"><button type="button" data-sort="${c.key}">${c.label}</button></th>`;
      }).join('');
      const row = (p, child, no) => `<tr tabindex="0" data-id="${esc(p.id)}" class="${child ? 'ax-child-row' : ''}">
          <td class="ax-sno">${no}</td>
          ${cols.map(c => `<td class="${c.num ? 'r' : ''}">${child && c.key === 'project' ? childCell(p) : c.cell(p)}</td>`).join('')}
          <td class="r"><button type="button" class="ax-btn ax-btn--ghost ax-btn--small ax-btn--icon" data-archive="${esc(p.id)}" aria-label="Archive ${esc(p.customer || p.name)}" title="Archive">${icon('archive')}</button></td>
        </tr>`;
      const rows = !state.group ? list.map((p, i) => row(p, false, i + 1)).join('') : groups(list).map((g, gi) => {
        if (g.items.length === 1) return row(g.items[0], false, gi + 1);
        const open = state.expanded.has(g.key) || !!state.q;      // a search opens matching groups
        return groupRow(g, cols, open, gi + 1) + (open ? g.items.map((p, i) => row(p, true, `${gi + 1}.${i + 1}`)).join('') : '');
      }).join('');
      table.innerHTML = `<table class="ax-table ax-table--list"><thead><tr><th class="ax-sno" scope="col">S.No</th>${head}<th><span class="ax-sr">Actions</span></th></tr></thead><tbody>${rows}</tbody></table>`;
    }
    const note = el.querySelector('#ax-proj-archive-note');
    note.textContent = state.archivedCount ? `${state.archivedCount} archived project${state.archivedCount === 1 ? '' : 's'} not shown. Archived projects keep all their versions.` : '';
  }

  // ── interactions ───────────────────────────────────────────────────────
  function openFilter(btn) {
    const k = btn.dataset.filter;
    const base = filtered(state.view, k);
    const counts = new Map();
    base.forEach(p => { const v = filterValue(p, k); counts.set(v, (counts.get(v) || 0) + 1); });
    state.filters[k].forEach(v => counts.has(v) || counts.set(v, 0));
    const vals = [...counts.keys()].sort((a, b) => (a === '') - (b === '') || a.localeCompare(b));
    const html = vals.length ? vals.map(v => `<label><input type="checkbox" value="${esc(v)}" ${state.filters[k].includes(v) ? 'checked' : ''}>
        ${v === '' ? '<span class="ax-faint">None</span>' : esc(v)}<span class="ax-pop-count">${counts.get(v)}</span></label>`).join('')
      : '<div class="ax-pop-head">No values</div>';
    popover(btn, html, {
      onRender: pop => pop.addEventListener('change', e => {
        const v = e.target.value;
        state.filters[k] = e.target.checked ? [...state.filters[k], v] : state.filters[k].filter(x => x !== v);
        renderBody(); savePrefs();
      }),
    });
  }

  function openColumns(btn) {
    const groups = {};
    COLS.filter(c => !c.fixed).forEach(c => (groups[c.group || 'Shown by default'] ||= []).push(c));
    const html = `<div class="ax-pop-head">Your columns are saved to your account.</div>` +
      Object.entries(groups).map(([g, cs]) => `<div class="ax-pop-head" style="padding-top:8px;font-weight:700">${g}</div>` +
        cs.map(c => `<label><input type="checkbox" value="${c.key}" ${state.cols.includes(c.key) ? 'checked' : ''}>${c.label}</label>`).join('')).join('') +
      `<div style="padding:8px"><button type="button" class="ax-btn ax-btn--small" data-reset>Reset to default</button></div>`;
    popover(btn, html, {
      onRender: pop => {
        pop.addEventListener('change', e => {
          const k = e.target.value;
          if (e.target.checked) {
            // keep table order the same as the column list
            state.cols = COLS.map(c => c.key).filter(x => x === k || state.cols.includes(x));
          } else state.cols = state.cols.filter(x => x !== k);
          renderBody(); savePrefs();
        });
        pop.querySelector('[data-reset]').addEventListener('click', () => {
          state.cols = defaultCols(); closePopover(); renderBody(); savePrefs();
        });
      },
    });
  }

  function toggleGroup(key) {
    if (state.expanded.has(key)) state.expanded.delete(key); else state.expanded.add(key);
    renderBody();
    root().querySelector(`tr[data-group="${CSS.escape(key)}"]`)?.focus();
  }

  async function archive(id) {
    const p = state.list.find(x => x.id === id);
    if (!p) return;
    const versions = p.version_count || 0;
    const ok = await dialog({
      title: 'Archive project?',
      body: `<p><b>${esc(p.customer || p.name)}</b>${p.customer && p.name ? ', ' + esc(p.name) : ''} moves to the archive with all ${versions} version${versions === 1 ? '' : 's'}. Nothing is deleted. An admin can restore it.</p>`,
      confirmLabel: 'Archive project',
    });
    if (!ok) return;
    const res = await fetch(`/api/projects/${encodeURIComponent(id)}/archive`, { method: 'POST' });
    if (!res.ok) { toast(await errorMessage(res, "The project couldn't be archived."), { error: true }); return; }
    state.list = state.list.filter(x => x.id !== id);
    state.archivedCount = (state.archivedCount || 0) + 1;
    renderBody();
    toast('Project archived', {
      undo: async () => {
        const r = await fetch(`/api/projects/${encodeURIComponent(id)}/restore`, { method: 'POST' });
        if (!r.ok) { toast(await errorMessage(r, "The project couldn't be restored."), { error: true }); return; }
        toast('Project restored');
        load(true);
      },
    });
  }

  function bind() {
    const el = root();
    if (!el || el.dataset.bound) return;
    el.dataset.bound = '1';
    el.addEventListener('click', e => {
      const t = e.target.closest('button, tr[data-id], tr[data-group]');
      if (!t) return;
      if (t.dataset.view) { state.view = t.dataset.view; renderBody(); savePrefs(); return; }
      if (t.dataset.filter) { openFilter(t); return; }
      if (t.dataset.sort) {
        const k = t.dataset.sort;
        state.sort = state.sort.key === k ? { key: k, dir: state.sort.dir === 'asc' ? 'desc' : 'asc' }
          : { key: k, dir: colByKey[k].num || k === 'updated' ? 'desc' : 'asc' };
        renderBody(); savePrefs(); return;
      }
      if (t.dataset.archive) { e.stopPropagation(); archive(t.dataset.archive); return; }
      const act = t.dataset.act;
      if (act === 'clear') { state.q = ''; rememberSearch(); FILTERS.forEach(([k]) => state.filters[k] = []); el.querySelector('#ax-proj-q').value = ''; renderBody(); savePrefs(); return; }
      if (act === 'columns') { openColumns(t); return; }
      if (act === 'group') { state.group = !state.group; renderBody(); savePrefs(); return; }
      if (act === 'new') { window.location.href = '/projects/new'; return; }
      if (t.matches('tr[data-group]')) { toggleGroup(t.dataset.group); return; }
      if (t.matches('tr[data-id]')) {
        const url = '/projects/' + encodeURIComponent(t.dataset.id);
        if (e.metaKey || e.ctrlKey) window.open(url, '_blank'); else window.location.href = url;
      }
    });
    el.addEventListener('keydown', e => {
      const gr = e.target.closest('tr[data-group]');
      if (gr && (e.key === 'Enter' || e.key === ' ') && e.target === gr) { e.preventDefault(); toggleGroup(gr.dataset.group); return; }
      const tr = e.target.closest('tr[data-id]');
      if (tr && e.key === 'Enter' && e.target === tr) window.location.href = '/projects/' + encodeURIComponent(tr.dataset.id);
    });
  }

  async function load(force) {
    const el = root();
    if (!el) return;
    if (state.loading) return;
    state.loading = true;
    // Start the list requests now; preferences load at the same time.
    const lists = Promise.all([
      fetch('/api/projects?summary=true', { cache: 'no-store' }),
      fetch('/api/projects?archived=true', { cache: 'no-store' }),
    ]);
    lists.catch(() => {});
    await loadPrefs();
    if (!el.querySelector('#ax-proj-table')) renderShell();
    bind();
    if (!state.list || force) el.querySelector('#ax-proj-table').innerHTML = '<div class="ax-empty">Loading projects…</div>';
    // The top-bar search sends its query here (saveAllProjectsSearch in app.js keeps it).
    if (typeof loadAllProjectsSearch === 'function') {
      const q = (loadAllProjectsSearch() || '').trim();
      if (q !== state.q) { state.q = q; el.querySelector('#ax-proj-q').value = q; }
    }
    try {
      const [res, arch] = await lists;
      if (!res.ok) throw new Error(await errorMessage(res, `The server answered ${res.status}.`));
      state.list = await res.json();
      state.archivedCount = arch.ok ? (await arch.json()).length : null;
      renderBody();
    } catch (e) {
      el.querySelector('#ax-proj-table').innerHTML =
        `<div class="ax-empty"><b>Projects couldn't load</b>${esc(e.message)} Check your connection, then try again.
         <div><button type="button" class="ax-btn ax-btn--small" onclick="loadAllProjects()">Try again</button></div></div>`;
    } finally {
      state.loading = false;
    }
  }

  window.axProjects = { load, state };
  window.loadAllProjects = () => load(true);   // replaces the legacy renderer in app.js
})();
