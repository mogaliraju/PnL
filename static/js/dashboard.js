// Dashboard (DESIGN.md 5.4). Figures come from the engine via /api/projects?summary=true.
// Filters (Business unit, Owner, Folder) are shared with the Projects list (user_pref projects_list).
(function () {
  'use strict';
  const { esc, toast, popover, errorMessage } = window.axUI;
  const AX = window.AX || { thresholds: { good: 20, warn: 10 } };
  const GOOD = AX.thresholds.good, WARN = AX.thresholds.warn;
  const STATUSES = ['Draft', 'Submitted', 'Won', 'Lost', 'On hold'];
  const OPEN = ['Draft', 'Submitted', 'On hold'];
  const FILTERS = [['business_unit', 'Business unit'], ['owner', 'Owner'], ['folder', 'Folder']];
  const S = { list: null, published: null, prefs: {}, filters: { business_unit: [], owner: [], folder: [] }, from: '', to: '' };

  const money = n => '$' + Math.round(n || 0).toLocaleString('en-US');
  const moneyK = n => n >= 1e6 ? '$' + (n / 1e6).toFixed(2) + 'M' : n >= 1e3 ? '$' + (n / 1e3).toFixed(1) + 'k' : money(n);
  const pct = n => (Math.round((n || 0) * 10) / 10).toFixed(1) + '%';
  const health = v => v >= GOOD ? 'good' : v >= WARN ? 'warn' : 'bad';
  const healthWord = v => v >= GOOD ? 'on target' : v >= WARN ? 'below target' : 'well below target';
  const status = p => { const s = String(p.status || 'Draft'); return s.toLowerCase() === 'on hold' ? 'On hold' : s; };
  const owner = p => (p.project_owner || '').trim();
  const val = (p, k) => k === 'owner' ? owner(p) : (p[k] || '');
  const cv = p => Number(p.pnl?.contract_value || 0);
  const ax = p => Number(p.pnl?.ax_net_pct || 0);
  const root = () => document.getElementById('ax-dash-root');

  function filtered() {
    return (S.list || []).filter(p => !p.pnl?.error &&
      FILTERS.every(([k]) => !S.filters[k].length || S.filters[k].includes(val(p, k))) &&
      (!S.from || (p.saved_at || '').slice(0, 10) >= S.from) && (!S.to || (p.saved_at || '').slice(0, 10) <= S.to));
  }

  async function savePrefs() {
    S.prefs = { ...S.prefs, filters: { ...(S.prefs.filters || {}), ...S.filters }, dashboard: { from: S.from, to: S.to } };
    try {
      await fetch('/api/prefs/projects_list', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(S.prefs) });
    } catch { /* the choice still applies on this page */ }
  }

  // ── charts ─────────────────────────────────────────────────────────────
  function dotStrip(items) {
    const open = items.filter(p => status(p) !== 'Lost' && cv(p) > 0).sort((a, b) => cv(b) - cv(a));
    if (!open.length) return '<div class="ax-empty">No open projects with a price yet.</div>';
    const W = 760, H = 230, L = 44, R = 12, T = 14, B = 24;
    const top = Math.max(GOOD * 2, Math.ceil(Math.max(...open.map(ax)) / 10) * 10);
    const y = v => T + (H - T - B) * (1 - Math.max(0, Math.min(v, top)) / top);
    const maxCv = Math.max(...open.map(cv));
    const step = (W - L - R) / open.length;
    const ticks = []; for (let t = 0; t <= top; t += 10) ticks.push(t);
    const dots = open.map((p, i) => {
      const r = 4 + 10 * Math.sqrt(cv(p) / maxCv);
      const label = `${p.customer || p.name}: ${pct(ax(p))} AX margin, ${moneyK(cv(p))} contract value (${status(p)})`;
      return `<a href="/projects/${encodeURIComponent(p.id)}" aria-label="${esc(label)}">
        <circle class="ax-dot ax-dot--${health(ax(p))}" cx="${(L + step * (i + .5)).toFixed(1)}" cy="${y(ax(p)).toFixed(1)}" r="${r.toFixed(1)}"><title>${esc(label)}</title></circle>
        <circle class="ax-dot-hit" cx="${(L + step * (i + .5)).toFixed(1)}" cy="${y(ax(p)).toFixed(1)}" r="${Math.max(r, 11).toFixed(1)}"><title>${esc(label)}</title></circle></a>`;
    }).join('');
    return `<svg class="ax-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="AX margin after discount for each open project">
      ${ticks.map(t => `<line class="ax-grid" x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}"/><text class="ax-tick" x="${L - 8}" y="${y(t) + 4}" text-anchor="end">${t}%</text>`).join('')}
      <line class="ax-target" x1="${L}" x2="${W - R}" y1="${y(GOOD)}" y2="${y(GOOD)}"/>
      <text class="ax-target-label" x="${W - R}" y="${y(GOOD) - 6}" text-anchor="end">Target ${GOOD}%</text>
      ${dots}
    </svg>
    <div class="ax-legend" aria-hidden="true"><span><i class="ax-dot--good"></i>${GOOD}% or more</span><span><i class="ax-dot--warn"></i>${WARN}% to ${GOOD}%</span>
      <span><i class="ax-dot--bad"></i>Under ${WARN}%</span><span class="ax-faint">Bigger dot = bigger contract. Projects sorted by contract value.</span></div>
    <table class="ax-sr"><caption>AX margin by project</caption><thead><tr><th>Project</th><th>Status</th><th>AX margin</th><th>Contract value</th></tr></thead>
      <tbody>${open.map(p => `<tr><td>${esc(p.customer || p.name)}</td><td>${status(p)}</td><td>${pct(ax(p))}</td><td>${money(cv(p))}</td></tr>`).join('')}</tbody></table>`;
  }

  function statusBars(items) {
    const rows = STATUSES.map(s => {
      const ps = items.filter(p => status(p) === s);
      return { s, n: ps.length, v: ps.reduce((t, p) => t + cv(p), 0) };
    });
    const max = Math.max(1, ...rows.map(r => r.v));
    return rows.map(r => `<div class="ax-hbar" title="${esc(r.s)}: ${money(r.v)} across ${r.n} project${r.n === 1 ? '' : 's'}">
      <span>${r.s} <span class="ax-faint">(${r.n})</span></span>
      <div class="ax-hbar-track"><div class="ax-hbar-fill" style="width:${(r.v / max * 100).toFixed(1)}%"></div></div>
      <span class="r num">${moneyK(r.v)}</span></div>`).join('');
  }

  // ── render ─────────────────────────────────────────────────────────────
  function render() {
    const items = filtered();
    const sum = arr => arr.reduce((t, p) => t + cv(p), 0);
    const pipeline = items.filter(p => ['Draft', 'Submitted'].includes(status(p)));
    const won = items.filter(p => status(p) === 'Won');
    const priced = items.filter(p => status(p) !== 'Lost' && cv(p) > 0);
    const avgAx = priced.length ? priced.reduce((t, p) => t + ax(p), 0) / priced.length : 0;
    const below = items.filter(p => OPEN.includes(status(p)) && cv(p) > 0 && ax(p) < GOOD).sort((a, b) => ax(a) - ax(b));
    const stale = S.published ? items.filter(p => OPEN.includes(status(p)) && p.rate_card_version && p.rate_card_version < S.published) : [];
    const any = FILTERS.some(([k]) => S.filters[k].length) || S.from || S.to;
    root().innerHTML = `
      <div class="ax-page-head"><div><h1 class="ax-h1">Dashboard</h1>
        <p>Portfolio value and margin health across ${items.length} project${items.length === 1 ? '' : 's'}. The AX margin target is ${GOOD}%, after discount.</p></div></div>
      <div class="ax-toolbar ax-toolbar--bare">
        ${FILTERS.map(([k, l]) => `<button type="button" class="ax-chip ${S.filters[k].length ? 'is-set' : ''}" data-filter="${k}" aria-haspopup="true" aria-expanded="false">${l}${S.filters[k].length ? ` <b>${S.filters[k].length}</b>` : ''}</button>`).join('')}
        <label class="ax-date">Updated from <input class="ax-input" type="date" data-range="from" value="${S.from}"></label>
        <label class="ax-date">to <input class="ax-input" type="date" data-range="to" value="${S.to}"></label>
        ${any ? '<button type="button" class="ax-btn ax-btn--ghost ax-btn--small" data-act="clear">Clear</button>' : ''}
      </div>
      <section class="ax-kpis">
        <div class="ax-kpi"><span>Open pipeline</span><b class="num">${moneyK(sum(pipeline))}</b><small>${pipeline.length} draft and submitted</small></div>
        <div class="ax-kpi"><span>Won</span><b class="num">${moneyK(sum(won))}</b><small>${won.length} project${won.length === 1 ? '' : 's'}</small></div>
        <div class="ax-kpi"><span>Average AX margin</span><b class="num ax-health ax-health--${health(avgAx)}">${pct(avgAx)}</b><small>After discount, excluding lost</small></div>
        <div class="ax-kpi"><span>Below target</span><b class="num ax-health ax-health--${below.length ? 'bad' : 'good'}">${below.length}</b><small>Open projects under ${GOOD}%</small></div>
      </section>
      <div class="ax-dgrid">
        <section class="ax-panel ax-section"><div class="ax-section-head"><h2 class="ax-h2">AX margin by project</h2></div>${dotStrip(items)}</section>
        <section class="ax-panel ax-section"><div class="ax-section-head"><h2 class="ax-h2">Needs attention</h2></div>
          <ul class="ax-att">
            ${below.slice(0, 6).map(p => `<li><span class="ax-health ax-health--${health(ax(p))}">${pct(ax(p))}</span>
              <div><a href="/projects/${encodeURIComponent(p.id)}">${esc(p.customer || p.name)}</a> is ${healthWord(ax(p))}
              <span class="ax-faint">(${status(p)}, ${moneyK(cv(p))})</span></div></li>`).join('')}
            ${below.length > 6 ? `<li><span></span><div><a href="/">${below.length - 6} more below target</a> <span class="ax-faint">(Projects, Below AX target)</span></div></li>` : ''}
            ${stale.length ? `<li><span class="ax-faint">Rates</span><div>${stale.length} open project${stale.length === 1 ? '' : 's'} still price with an older rate card. v${S.published} is published.
              <span class="ax-faint">For example ${stale.slice(0, 3).map(p => `<a href="/projects/${encodeURIComponent(p.id)}">${esc(p.customer || p.name)}</a>`).join(', ')}.</span>
              Each project shows a banner to review the change.</div></li>` : ''}
            ${!below.length && !stale.length ? `<li><span class="ax-health ax-health--good">OK</span><div>All open projects meet the AX target and use the published rate card.</div></li>` : ''}
          </ul></section>
      </div>
      <section class="ax-panel ax-section" style="margin-top:18px"><div class="ax-section-head"><h2 class="ax-h2">Contract value by status</h2></div>${statusBars(items)}</section>`;
  }

  function openFilter(btn) {
    const k = btn.dataset.filter;
    const counts = new Map();
    (S.list || []).forEach(p => { const v = val(p, k); counts.set(v, (counts.get(v) || 0) + 1); });
    S.filters[k].forEach(v => counts.has(v) || counts.set(v, 0));
    const vals = [...counts.keys()].sort((a, b) => (a === '') - (b === '') || a.localeCompare(b));
    popover(btn, vals.map(v => `<label><input type="checkbox" value="${esc(v)}" ${S.filters[k].includes(v) ? 'checked' : ''}>
      ${v === '' ? '<span class="ax-faint">None</span>' : esc(v)}<span class="ax-pop-count">${counts.get(v)}</span></label>`).join('') || '<div class="ax-pop-head">No values</div>', {
      onRender: pop => pop.addEventListener('change', e => {
        const v = e.target.value;
        S.filters[k] = e.target.checked ? [...S.filters[k], v] : S.filters[k].filter(x => x !== v);
        render(); savePrefs();
        const again = root().querySelector(`[data-filter="${k}"]`);
        if (again) { window.axUI.closePopover(); openFilter(again); }
      }),
    });
  }

  let bound = false;
  function bind() {
    if (bound) return;
    bound = true;
    root().addEventListener('click', e => {
      const t = e.target.closest('button');
      if (!t) return;
      if (t.dataset.filter) openFilter(t);
      if (t.dataset.act === 'clear') { FILTERS.forEach(([k]) => S.filters[k] = []); S.from = S.to = ''; render(); savePrefs(); }
    });
    root().addEventListener('change', e => {
      const t = e.target;
      if (t.dataset.range) { S[t.dataset.range] = t.value; render(); savePrefs(); }
    });
  }

  async function load() {
    if (!root()) return;
    bind();
    if (!S.list) root().innerHTML = '<div class="ax-empty" style="padding:60px 0">Loading the dashboard…</div>';
    try {
      const [list, prefs, settings] = await Promise.all([
        fetch('/api/projects?summary=true', { cache: 'no-store' }).then(async r => { if (!r.ok) throw new Error(await errorMessage(r)); return r.json(); }),
        fetch('/api/prefs/projects_list').then(r => r.ok ? r.json() : {}).catch(() => ({})),
        fetch('/api/data').then(r => r.ok ? r.json() : {}).catch(() => ({})),
      ]);
      S.list = list;
      S.prefs = prefs || {};
      S.published = settings.rate_card_version || null;
      FILTERS.forEach(([k]) => { S.filters[k] = Array.isArray(S.prefs.filters?.[k]) ? S.prefs.filters[k] : []; });
      S.from = S.prefs.dashboard?.from || ''; S.to = S.prefs.dashboard?.to || '';
      render();
    } catch (e) {
      root().innerHTML = `<div class="ax-panel"><div class="ax-empty"><b>The dashboard couldn't load</b>${esc(e.message)}
        <div><button type="button" class="ax-btn ax-btn--small" onclick="loadDashboard()">Try again</button></div></div></div>`;
    }
  }

  window.axDashboard = { load, state: S };
  window.loadDashboard = load;      // replaces the legacy dashboard renderer in app.js
})();
