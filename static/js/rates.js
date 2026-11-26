// Rates and roles (DESIGN.md 5.5): versioned rate card matrix, roles, rate card history.
(function () {
  'use strict';
  const { esc, toast, dialog, errorMessage } = window.axUI;
  const AX = window.AX || { user: {} };
  const isAdmin = () => AX.user.role === 'admin';
  const icon = n => (document.getElementById('ax-icon-' + n) || {}).innerHTML || '';

  const S = {
    sub: 'matrix', cards: null, version: null, matrix: null, edits: {}, unit: 'USD', fx: null,
    roles: null, catId: null, unavailable: null,
  };
  const root = () => document.getElementById('ax-rates-root');
  const money = v => v == null ? '' : '$' + Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 });
  const fmtDate = v => {
    if (!v) return '';
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v);          // a date without a time is a calendar date, not UTC midnight
    const d = m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date(v);
    return isNaN(d) ? esc(v) : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  };
  const dirty = () => Object.keys(S.edits).length > 0;

  async function api(url, opts = {}) {
    const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts });
    if (res.status === 503) { S.unavailable = await errorMessage(res); throw new Error(S.unavailable); }
    if (!res.ok) throw new Error(await errorMessage(res));
    return res.json();
  }

  // ── frame ──────────────────────────────────────────────────────────────
  function frame() {
    const tabs = [['matrix', 'Rate card', 'rates'], ['roles', 'Roles', 'roles'], ['history', 'Rate card history', 'history']];
    root().innerHTML = `
      <div class="ax-page-head"><div><h1 class="ax-h1">Rates and roles</h1>
        <p>Roles belong to a category. Each category has an hourly rate per level. Projects keep the rate card they were priced with until someone updates them.</p></div></div>
      <div class="ax-tabs" role="tablist">${tabs.map(([k, l, route]) =>
        `<button type="button" role="tab" data-route="${route}" class="${S.sub === k ? 'is-active' : ''}" aria-selected="${S.sub === k}">${l}</button>`).join('')}</div>
      ${isAdmin() ? '' : '<p class="ax-caption" style="margin:-8px 0 14px">Only admins can change rates and roles.</p>'}
      <div id="ax-rates-body"><div class="ax-empty">Loading…</div></div>`;
  }
  const body = () => document.getElementById('ax-rates-body');
  function failed(e) {
    body().innerHTML = `<div class="ax-panel"><div class="ax-empty"><b>${S.unavailable ? 'Rate cards are not set up on this database yet' : "This couldn't load"}</b>${esc(e.message)}</div></div>`;
  }

  // ── rate card matrix ──────────────────────────────────────────────────
  async function loadMatrix(version) {
    S.cards = await api('/api/rate-cards');
    const draft = S.cards.find(c => c.status === 'draft');
    const pub = S.cards.find(c => c.status === 'published');
    S.version = version || S.version || (draft || pub || S.cards[0] || {}).version;
    if (!S.version) { body().innerHTML = '<div class="ax-panel"><div class="ax-empty"><b>No rate card yet</b>Ask an admin to create the first draft.</div></div>'; return; }
    S.matrix = await api(`/api/rate-cards/${S.version}`);
    S.edits = {};
    renderMatrix();
  }

  function cellValue(cid, lid) {
    const key = `${cid}:${lid}`;
    if (key in S.edits) return S.edits[key];
    return S.matrix.rates[cid]?.[lid] ?? null;
  }

  function renderMatrix() {
    const m = S.matrix, card = m.card, draft = card.status === 'draft', canEdit = draft && isAdmin();
    const pub = m.published_rates;
    let changes = 0;
    const rows = m.categories.map(c => {
      const cells = m.levels.map(l => {
        const v = cellValue(c.id, l.id);
        const was = pub ? (pub[c.id]?.[l.id] ?? null) : v;
        const changed = draft && pub && v !== was;
        if (changed) changes++;
        if (canEdit && S.unit === 'USD') {
          return `<td class="ax-cell r"><input class="ax-input ax-rate-in num${changed ? ' is-changed' : ''}" type="number" min="0" step="0.5"
            data-c="${c.id}" data-l="${l.id}" value="${v ?? ''}" placeholder="None" aria-label="${esc(c.name)} ${esc(l.code)} rate">
            ${changed ? `<span class="ax-was">was ${was == null ? 'not offered' : money(was)}</span>` : ''}</td>`;
        }
        if (v == null) return '<td class="r"><span class="ax-faint">Not offered</span></td>';
        const shown = S.unit === 'USD' ? money(v) : (S.fx ? '₹' + Math.round(v * S.fx).toLocaleString('en-IN') : '…');
        return `<td class="r"><b class="num">${shown}</b>${changed ? `<span class="ax-was">was ${was == null ? 'not offered' : money(was)}</span>` : ''}</td>`;
      }).join('');
      return `<tr class="${c.active ? '' : 'ax-row-off'}"><th scope="row" class="ax-cat">${esc(c.name)}${c.active ? '' : ' <span class="ax-faint">(off)</span>'}</th>${cells}
        <td class="r"><button type="button" class="ax-btn ax-btn--ghost ax-btn--small" data-cat="${c.id}" title="Open this category's roles">${c.active_roles}</button></td></tr>`;
    }).join('');
    const opts = S.cards.map(c => `<option value="${c.version}" ${c.version === card.version ? 'selected' : ''}>Rate card v${c.version} (${c.status})</option>`).join('');
    const hasDraft = S.cards.some(c => c.status === 'draft');
    let status;
    if (draft) status = `<span class="ax-pill ax-pill--on-hold">Draft${pub ? `, ${changes} change${changes === 1 ? '' : 's'} from v${m.published_version}` : ''}</span>`;
    else if (card.status === 'published') status = `<span class="ax-lock">${icon('lock')}Published ${fmtDate(card.effective_from)}.${isAdmin() ? ' Create a draft to change rates.' : ''}</span>`;
    else status = `<span class="ax-lock">${icon('lock')}Archived. Read only.</span>`;
    const actions = !isAdmin() ? '' : draft
      ? `<span class="ax-dirty" ${dirty() ? '' : 'hidden'}>Unsaved changes</span>
         <button type="button" class="ax-btn ax-btn--small" data-act="save" ${dirty() ? '' : 'disabled'}>Save draft</button>
         <button type="button" class="ax-btn ax-btn--primary ax-btn--small" data-act="publish">Publish v${card.version}</button>`
      : (card.status === 'published' && !hasDraft ? `<button type="button" class="ax-btn ax-btn--primary ax-btn--small" data-act="draft">${icon('plus')}New draft</button>` : '');
    body().innerHTML = `<section class="ax-panel">
      <div class="ax-toolbar">
        <select class="ax-input" style="width:auto" id="ax-rc-version" aria-label="Rate card version">${opts}</select>
        ${status}
        <div class="ax-spacer"></div>
        <div class="ax-seg" role="group" aria-label="Currency">
          <button type="button" data-unit="USD" class="${S.unit === 'USD' ? 'is-on' : ''}">USD / h</button>
          <button type="button" data-unit="INR" class="${S.unit === 'INR' ? 'is-on' : ''}">INR / h</button></div>
        ${actions}
      </div>
      <div class="ax-table-wrap"><table class="ax-table ax-matrix">
        <thead><tr><th>Category</th>${m.levels.map(l => `<th class="r">${esc(l.code)}</th>`).join('')}<th class="r">Roles</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      <div class="ax-section ax-caption">${card.note ? esc(card.note) + '. ' : ''}Leave a cell empty when a category doesn't offer that level. It then won't appear in the level picker for that category.</div>
    </section>`;
  }

  async function ensureFx() {
    if (S.fx) return;
    try { S.fx = typeof fetchExchangeRate === 'function' ? await fetchExchangeRate() : null; } catch { S.fx = null; }
    if (!S.fx) toast("The live USD to INR rate isn't available, so INR can't be shown.", { error: true });
  }

  async function saveDraft() {
    const rates = Object.entries(S.edits).map(([k, v]) => { const [c, l] = k.split(':'); return { category_id: +c, level_id: +l, rate_usd: v }; });
    try {
      S.matrix = await api(`/api/rate-cards/${S.version}/rates`, { method: 'PUT', body: JSON.stringify({ rates }) });
      S.edits = {};
      renderMatrix();
      toast(`Draft v${S.version} saved`);
      return true;
    } catch (e) { toast(e.message, { error: true }); return false; }
  }

  async function publish() {
    if (dirty() && !(await saveDraft())) return;
    const m = S.matrix, pub = m.published_rates || {};
    let n = 0;
    m.categories.forEach(c => m.levels.forEach(l => { if ((m.rates[c.id]?.[l.id] ?? null) !== (pub[c.id]?.[l.id] ?? null)) n++; }));
    const today = new Date().toISOString().slice(0, 10);
    const res = await dialog({
      title: `Publish rate card v${S.version}?`,
      body: `<p>${n} rate${n === 1 ? '' : 's'} change. Existing projects keep their current rate card and see a prompt to review the change. New projects use v${S.version}.</p>`,
      fields: [{ name: 'effective_from', label: 'Effective from', type: 'date', value: today, required: true }],
      validate: v => v.effective_from ? {} : { effective_from: 'Pick the date the new rates apply from.' },
      confirmLabel: `Publish v${S.version}`,
    });
    if (!res) return;
    try {
      await api(`/api/rate-cards/${S.version}/publish`, { method: 'POST', body: JSON.stringify(res.values) });
      toast(`Rate card v${S.version} published`);
      await loadMatrix(S.version);
    } catch (e) { toast(e.message, { error: true }); }
  }

  async function newDraft() {
    try {
      const m = await api('/api/rate-cards/draft', { method: 'POST', body: '{}' });
      toast(`Draft v${m.card.version} created from v${m.published_version}`);
      await loadMatrix(m.card.version);
    } catch (e) { toast(e.message, { error: true }); }
  }

  // ── roles ─────────────────────────────────────────────────────────────
  async function loadRoles() {
    S.roles = await api('/api/roles');
    if (!S.catId || !S.roles.categories.some(c => c.id === S.catId)) S.catId = S.roles.categories[0]?.id;
    renderRoles();
  }

  function renderRoles() {
    const { categories, roles, levels } = S.roles;
    const cat = categories.find(c => c.id === S.catId);
    const mine = roles.filter(r => r.category_id === S.catId);
    const admin = isAdmin();
    const lvOpts = sel => `<option value="">None</option>` + levels.map(l => `<option value="${l.id}" ${l.id === sel ? 'selected' : ''}>${esc(l.code)}</option>`).join('');
    body().innerHTML = `<div class="ax-two">
      <section class="ax-panel ax-catlist">
        <div class="ax-section-head" style="padding:14px 14px 6px;margin:0"><h2 class="ax-h2" style="flex:1">Categories</h2>
          ${admin ? `<button type="button" class="ax-btn ax-btn--small ax-btn--icon" data-act="add-cat" aria-label="Add category">${icon('plus')}</button>` : ''}</div>
        ${categories.map(c => `<button type="button" data-catsel="${c.id}" class="${c.id === S.catId ? 'is-active' : ''}${c.active ? '' : ' ax-faint'}">
          <span>${esc(c.name)}</span><span class="ax-faint">${c.active_roles}</span></button>`).join('')}
      </section>
      <section class="ax-panel">
        <div class="ax-toolbar"><h2 class="ax-h2">${esc(cat?.name || '')}</h2>
          ${cat && admin ? `<label class="ax-caption" style="display:flex;gap:6px;align-items:center;margin-left:8px">
            <button type="button" class="ax-switch ${cat.active ? 'is-on' : ''}" role="switch" aria-checked="${cat.active}" data-catactive="${cat.id}" aria-label="Category in use"></button>In use</label>` : ''}
          <div class="ax-spacer"></div>
          ${admin && cat ? `<button type="button" class="ax-btn ax-btn--small" data-act="add-role">${icon('plus')}Add role</button>` : ''}</div>
        ${mine.length ? `<div class="ax-table-wrap"><table class="ax-table">
          <thead><tr><th>Role</th><th>Default level</th><th class="r">Used in</th><th>Active</th></tr></thead>
          <tbody>${mine.map(r => `<tr class="${r.active ? '' : 'ax-row-off'}">
            <td>${admin ? `<input class="ax-input ax-cell-in" value="${esc(r.name)}" data-rename="${r.id}" aria-label="Role name">` : esc(r.name)}
              ${r.imported ? '<span class="ax-caption">Found on old projects</span>' : ''}</td>
            <td>${admin ? `<select class="ax-input ax-cell-in" data-level="${r.id}" aria-label="Default level">${lvOpts(r.default_level_id)}</select>`
              : esc((levels.find(l => l.id === r.default_level_id) || {}).code || '')}</td>
            <td class="r ax-faint">${r.used_in} project${r.used_in === 1 ? '' : 's'}</td>
            <td><button type="button" class="ax-switch ${r.active ? 'is-on' : ''}" role="switch" aria-checked="${r.active}" data-active="${r.id}" aria-label="Active" ${admin ? '' : 'disabled'}></button></td>
          </tr>`).join('')}</tbody></table></div>`
          : `<div class="ax-empty"><b>No roles yet</b>${admin ? 'Add the first role for this category.' : ''}</div>`}
        <div class="ax-section ax-caption">Roles are never deleted. Turn one off to hide it from the role picker. Projects that already use it keep it.</div>
      </section></div>`;
  }

  async function patch(url, data, okMsg) {
    try {
      await api(url, { method: 'PATCH', body: JSON.stringify(data) });
      if (okMsg) toast(okMsg);
      await loadRoles();
    } catch (e) { toast(e.message, { error: true }); await loadRoles(); }
  }

  async function addRole() {
    const levels = S.roles.levels;
    const cat = S.roles.categories.find(c => c.id === S.catId);
    const res = await dialog({
      title: `Add role to ${cat.name}`,
      fields: [{ name: 'name', label: 'Role name', required: true, hint: 'For example, Analytics engineer' }],
      body: `<div class="ax-field"><label for="ax-new-role-level">Default level</label><select class="ax-input" id="ax-new-role-level" name="level">
        <option value="">None</option>${levels.map(l => `<option value="${l.id}">${esc(l.code)}</option>`).join('')}</select></div>`,
      validate: v => {
        const name = (v.name || '').trim();
        if (!name) return { name: 'Enter a role name.' };
        if (S.roles.roles.some(r => r.category_id === S.catId && r.name.toLowerCase() === name.toLowerCase()))
          return { name: `${cat.name} already has a role called "${name}".` };
        return {};
      },
      confirmLabel: 'Add role',
    });
    if (!res) return;
    try {
      await api('/api/roles', { method: 'POST', body: JSON.stringify({ category_id: S.catId, name: res.values.name.trim(), default_level_id: res.values.level || null }) });
      toast('Role added');
      await loadRoles();
    } catch (e) { toast(e.message, { error: true }); }
  }

  async function addCategory() {
    const res = await dialog({
      title: 'Add category',
      fields: [{ name: 'name', label: 'Category name', required: true, hint: 'Set its rates in the next rate card draft.' }],
      validate: v => {
        const name = (v.name || '').trim();
        if (!name) return { name: 'Enter a category name.' };
        if (S.roles.categories.some(c => c.name.toLowerCase() === name.toLowerCase())) return { name: `A category called "${name}" already exists.` };
        return {};
      },
      confirmLabel: 'Add category',
    });
    if (!res) return;
    try {
      const c = await api('/api/role-categories', { method: 'POST', body: JSON.stringify({ name: res.values.name.trim() }) });
      S.catId = c.id;
      toast('Category added');
      await loadRoles();
    } catch (e) { toast(e.message, { error: true }); }
  }

  // ── history ───────────────────────────────────────────────────────────
  async function loadHistory() {
    S.cards = await api('/api/rate-cards');
    const pill = s => `<span class="ax-pill ax-pill--${s === 'published' ? 'won' : s === 'draft' ? 'on-hold' : 'draft'}">${s[0].toUpperCase() + s.slice(1)}</span>`;
    body().innerHTML = `<section class="ax-panel"><div class="ax-table-wrap"><table class="ax-table">
      <thead><tr><th>Rate card</th><th>Status</th><th>Effective from</th><th>Note</th><th>By</th><th class="r">Projects using it</th><th></th></tr></thead>
      <tbody>${S.cards.map(c => `<tr><td><b>v${c.version}</b></td><td>${pill(c.status)}</td><td>${fmtDate(c.effective_from)}</td>
        <td class="ax-muted">${esc(c.note)}</td><td>${esc(c.published_by || c.created_by)}</td><td class="r num">${c.projects_using}</td>
        <td class="r"><button type="button" class="ax-btn ax-btn--ghost ax-btn--small" data-open="${c.version}">Open</button></td></tr>`).join('')
      || '<tr><td colspan="7" class="ax-empty">No rate cards yet.</td></tr>'}</tbody></table></div></section>`;
  }

  // ── wiring ────────────────────────────────────────────────────────────
  function bind() {
    const el = root();
    if (el.dataset.bound) return;
    el.dataset.bound = '1';
    el.addEventListener('click', async e => {
      const t = e.target.closest('button');
      if (!t) return;
      if (t.dataset.route) { if (!(await leaveOk())) return; window.axShell.show(t.dataset.route, true); return; }
      if (t.dataset.unit) { S.unit = t.dataset.unit; if (S.unit === 'INR') await ensureFx(); renderMatrix(); return; }
      if (t.dataset.cat) { S.catId = +t.dataset.cat; window.axShell.show('roles', true); return; }
      if (t.dataset.catsel) { S.catId = +t.dataset.catsel; renderRoles(); return; }
      if (t.dataset.open) { S.version = +t.dataset.open; window.axShell.show('rates', true); return; }
      if (t.dataset.active && !t.disabled) {
        const r = S.roles.roles.find(x => x.id === +t.dataset.active);
        patch(`/api/roles/${r.id}`, { active: !r.active }, r.active ? 'Role hidden from new resources' : 'Role turned on');
        return;
      }
      if (t.dataset.catactive) {
        const c = S.roles.categories.find(x => x.id === +t.dataset.catactive);
        patch(`/api/role-categories/${c.id}`, { active: !c.active }, c.active ? 'Category turned off' : 'Category turned on');
        return;
      }
      const act = t.dataset.act;
      if (act === 'save') saveDraft();
      if (act === 'publish') publish();
      if (act === 'draft') newDraft();
      if (act === 'add-role') addRole();
      if (act === 'add-cat') addCategory();
    });
    el.addEventListener('input', e => {
      const t = e.target;
      if (!t.matches('.ax-rate-in')) return;
      const key = `${t.dataset.c}:${t.dataset.l}`;
      const v = t.value === '' ? null : Number(t.value);
      const orig = S.matrix.rates[t.dataset.c]?.[t.dataset.l] ?? null;
      if (v === orig) delete S.edits[key]; else S.edits[key] = v;
      const tb = el.querySelector('.ax-dirty');
      if (tb) tb.hidden = !dirty();
      const sb = el.querySelector('[data-act="save"]');
      if (sb) sb.disabled = !dirty();
    });
    el.addEventListener('change', async e => {
      const t = e.target;
      if (t.id === 'ax-rc-version') {
        if (!(await leaveOk())) { t.value = S.version; return; }
        await loadMatrix(+t.value);
      }
      if (t.matches('.ax-rate-in')) setTimeout(renderMatrix, 0);   // after the browser finishes the blur
      if (t.dataset.rename) {
        const name = t.value.trim();
        const r = S.roles.roles.find(x => x.id === +t.dataset.rename);
        if (name && name !== r.name) patch(`/api/roles/${r.id}`, { name }, 'Role renamed. Projects saved earlier keep the old name on their lines.');
        else t.value = r.name;
      }
      if (t.dataset.level) patch(`/api/roles/${t.dataset.level}`, { default_level_id: t.value ? +t.value : null }, 'Default level updated');
    });
    window.addEventListener('beforeunload', e => { if (dirty()) { e.preventDefault(); e.returnValue = ''; } });
  }

  async function leaveOk() {
    if (!dirty()) return true;
    const ok = await dialog({ title: 'Discard unsaved rates?', body: '<p>The changes to this draft have not been saved.</p>',
      confirmLabel: 'Discard changes', danger: true });
    if (ok) S.edits = {};
    return ok;
  }

  async function open(sub) {
    if (!root()) return;
    S.sub = sub;
    frame();
    bind();
    try {
      if (sub === 'matrix') await loadMatrix();
      else if (sub === 'roles') await loadRoles();
      else await loadHistory();
    } catch (e) { failed(e); }
  }

  window.axRates = { open, state: S };
})();
