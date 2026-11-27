// Proposals tab in the project workspace (design/PROPOSALS.md section 6).
// Lists generated proposals, polls running ones and opens the Generate form.
(function () {
  'use strict';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const icon = n => (document.getElementById('ax-icon-' + n) || {}).innerHTML || '';
  const BRAND = { automatonsx: 'AutomatonsX', cloud4c: 'Cloud4C' };
  const ENG = { greenfield: 'Greenfield', migration: 'Migration', assessment: 'Assessment and completion', governance: 'Governance only' };
  const TECH = ['Microsoft Fabric', 'OneLake', 'Power BI', 'Microsoft Purview', 'Azure Databricks', 'Azure Synapse', 'Azure Data Factory'];
  const INVENTORY = [['pipelines', 'Pipelines'], ['notebooks', 'Notebooks'], ['tables', 'Tables or objects'],
    ['stored_procedures', 'Stored procedures'], ['reports_datasets', 'Reports or datasets'], ['linked_services', 'Linked services']];
  const S = { pid: null, rows: [], timer: null, unavailable: null, defaults: null, open: new Set() };

  const fmtDate = s => { const d = new Date(s); return isNaN(d) ? '' : d.toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }); };
  const pill = st => {
    const cls = { ready: 'won', failed: 'lost', running: 'submitted', queued: 'draft' }[st] || 'draft';
    const label = { ready: 'Ready', failed: 'Failed', running: 'Generating', queued: 'Waiting' }[st] || st;
    return `<span class="ax-pill ax-pill--${cls}">${label}</span>`;
  };

  // ── list ──────────────────────────────────────────────────────────────
  async function load() {
    try {
      const r = await fetch(`/api/projects/${encodeURIComponent(S.pid)}/proposals`);
      if (r.status === 503) { S.unavailable = await window.axUI.errorMessage(r); S.rows = []; }
      else if (r.ok) { const j = await r.json(); S.unavailable = null; S.rows = j.proposals || []; S.problems = j.setup_problems || []; }
    } catch { /* keep what we have */ }
    paint();
    clearTimeout(S.timer);
    if (S.rows.some(p => p.status === 'queued' || p.status === 'running')) S.timer = setTimeout(load, 4000);
  }

  function paint() {
    const el = document.getElementById('ax-proposals');
    if (!el) { clearTimeout(S.timer); return; }
    const head = `<div class="ax-section-head"><div style="flex:1"><h2 class="ax-h2">Proposals</h2>
        <p>Branded Word proposals written from a saved version. The commercials come from the PnL; the model writes the scope and approach.</p></div>
        <button type="button" class="ax-btn ax-btn--primary" data-pr="new" ${S.unavailable ? 'disabled' : ''}>${icon('plus')}Generate proposal</button></div>`;
    if (S.unavailable) {
      el.innerHTML = head + `<div class="ax-empty"><b>Proposal generation isn't set up on this server yet</b>${esc(S.unavailable)}</div>`;
      return;
    }
    const setup = (S.problems || []).length ? `<div class="ax-banner ax-banner--warn" role="status">${icon('alert')}<span><b>Generation isn't fully set up on this server.</b> ${S.problems.map(esc).join(' ')}</span></div>` : '';
    if (!S.rows.length) {
      el.innerHTML = head + setup + `<div class="ax-empty"><b>No proposals yet</b>Generate one from a saved version. It takes a minute or two.</div>`;
      return;
    }
    el.innerHTML = head + setup + `<div class="ax-table-wrap"><table class="ax-table"><thead><tr>
        <th>Version</th><th>Brand</th><th>Engagement</th><th>Status</th><th>Created</th><th><span class="ax-sr">Actions</span></th></tr></thead><tbody>
      ${S.rows.map(p => {
        const q = p.open_questions || [];
        const detail = p.status === 'failed' ? `<span class="ax-error">${esc(p.error || 'Generation failed.')}</span>`
          : p.status === 'ready' ? (() => {
              const ck = p.checks || [], bad = ck.filter(c => !c.ok).length;
              const parts = [];
              if (ck.length) parts.push(bad ? `<span class="ax-pr-bad">${bad} check${bad > 1 ? 's' : ''} failed</span>` : `${ck.length} checks passed`);
              if (q.length) parts.push(`${q.length} open question${q.length > 1 ? 's' : ''}`);
              return parts.length ? `<button type="button" class="ax-link" data-pr="questions" data-id="${p.id}" aria-expanded="${S.open.has(p.id)}">${parts.join(' · ')}</button>` : '';
            })()
          : `<span class="ax-faint"><span class="ax-typing"><i></i><i></i><i></i></span> ${esc(p.stage || 'Working')}</span>`;
        return `<tr><td>v${p.version_no}</td><td>${BRAND[p.brand] || esc(p.brand)}</td>
          <td><div class="ax-two-line"><span>${ENG[p.engagement_type] || esc(p.engagement_type)}</span><span>${esc(p.doc_type || '')}</span></div></td>
          <td><div class="ax-two-line">${pill(p.status)}<span>${detail}</span></div></td>
          <td><div class="ax-two-line"><span>${fmtDate(p.created_at)}</span><span>${esc(p.created_by)}</span></div></td>
          <td class="r">${p.status === 'ready' ? `<a class="ax-btn ax-btn--small" href="/api/proposals/${p.id}/download" download>${icon('download')}Word</a>` : ''}
            ${p.status === 'failed' ? `<button type="button" class="ax-btn ax-btn--small" data-pr="retry" data-id="${p.id}">Try again</button>` : ''}</td></tr>
          ${S.open.has(p.id) ? `<tr class="ax-pr-q"><td colspan="6">
            ${(p.checks || []).length ? `<b>Checks</b><ul class="ax-pr-checks-list">${p.checks.map(c =>
              `<li class="${c.ok ? 'is-ok' : 'is-bad'}"><span aria-hidden="true">${c.ok ? '✓' : '✗'}</span><span class="ax-sr">${c.ok ? 'Passed' : 'Failed'}:</span> ${esc(c.label)}${c.detail ? ` <span class="ax-faint">${esc(c.detail)}</span>` : ''}</li>`).join('')}</ul>` : ''}
            ${q.length ? `<b>Close these before sending</b><ul>${q.map(x => `<li><label><input type="checkbox"> ${esc(x)}</label></li>`).join('')}</ul>` : ''}</td></tr>` : ''}`;
      }).join('')}</tbody></table></div>`;
  }

  // ── Generate form ─────────────────────────────────────────────────────
  async function defaults() {
    const r = await fetch(`/api/projects/${encodeURIComponent(S.pid)}/proposals/defaults`);
    if (!r.ok) throw new Error(await window.axUI.errorMessage(r));
    return r.json();
  }

  const f = (label, name, opts = {}) => {
    const id = 'pr-' + name.replace(/\W/g, '-');
    const req = opts.required ? ' <span aria-hidden="true" class="ax-faint">(required)</span>' : '';
    const input = opts.textarea
      ? `<textarea class="ax-input" id="${id}" name="${name}" rows="${opts.rows || 3}" placeholder="${esc(opts.placeholder || '')}">${esc(opts.value || '')}</textarea>`
      : opts.options
        ? `<select class="ax-input" id="${id}" name="${name}">${opts.blank ? `<option value="">${esc(opts.blank)}</option>` : ''}${opts.options.map(([v, l]) =>
            `<option value="${esc(v)}" ${String(opts.value ?? '') === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`
        : `<input class="ax-input${opts.number ? ' num' : ''}" id="${id}" name="${name}" type="${opts.type || 'text'}" value="${esc(opts.value ?? '')}" placeholder="${esc(opts.placeholder || '')}" ${opts.number ? 'min="0" step="1"' : ''}>`;
    return `<div class="ax-field${opts.wide ? ' ax-span2' : ''}"><label for="${id}">${esc(label)}${req}</label>${input}${opts.hint ? `<span class="ax-hint">${esc(opts.hint)}</span>` : ''}<span class="ax-error" data-err="${name}" hidden></span></div>`;
  };
  const check = (label, name, on) => `<label class="ax-check"><input type="checkbox" name="${name}" ${on ? 'checked' : ''}> ${esc(label)}</label>`;
  const sourceRow = (s = {}) => `<div class="ax-pr-src">
      <input class="ax-input" data-src="name" value="${esc(s.name || '')}" placeholder="System, for example SAP S/4HANA" aria-label="Source system">
      <input class="ax-input" data-src="notes" value="${esc(s.notes || '')}" placeholder="How it's extracted and how often" aria-label="Ingestion notes">
      <input class="ax-input" data-src="objects" value="${esc(s.objects || '')}" placeholder="About 80 tables" aria-label="Object count">
      <button type="button" class="ax-btn ax-btn--ghost ax-btn--icon" data-pr-src-del aria-label="Remove source">${icon('x')}</button></div>`;
  const planRow = (m = {}) => `<div class="ax-pr-plan">
      <input class="ax-input" data-plan="milestone" value="${esc(m.milestone || '')}" aria-label="Milestone">
      <input class="ax-input num" data-plan="percent" type="number" min="0" max="100" value="${esc(m.percent ?? '')}" aria-label="Percent">
      <button type="button" class="ax-btn ax-btn--ghost ax-btn--icon" data-pr-plan-del aria-label="Remove milestone">${icon('x')}</button></div>`;

  async function openForm(prefill) {
    let d;
    try { d = S.defaults || (S.defaults = await defaults()); } catch (e) { window.axUI.toast(e.message, { error: true }); return; }
    if (!d.versions.length) { window.axUI.toast('Save a version of this project first. Proposals are priced from a saved version.', { error: true }); return; }
    const p = prefill || {};
    const latest = d.versions[0].version_no;
    const scrim = document.createElement('div');
    scrim.className = 'ax-scrim';
    scrim.innerHTML = `<form class="ax-dialog ax-dialog--wide ax-pr-form" role="dialog" aria-modal="true" aria-labelledby="pr-title" novalidate>
      <div class="ax-dialog-h"><h2 class="ax-h2" id="pr-title">Generate proposal</h2>
        <button type="button" class="ax-btn ax-btn--ghost ax-btn--icon" data-x aria-label="Close">${icon('x')}</button></div>
      <div class="ax-dialog-b">
        <p class="ax-caption">Claude Opus writes the client-specific sections from what you enter here. Boilerplate and commercials are added by the app, so prices always match the PnL version.</p>
        <fieldset class="ax-pr-fs"><legend>Basics</legend><div class="ax-grid3">
          ${f('PnL version', 'version_no', { options: d.versions.map(v => [v.version_no, `v${v.version_no}${v.label ? ' · ' + v.label : ''}`]), value: p.version_no || latest })}
          <div class="ax-field"><span class="ax-label-like">Brand <span class="ax-faint">(required)</span></span><div class="ax-seg" role="radiogroup" aria-label="Brand">
            ${Object.entries(BRAND).map(([k, l]) => `<button type="button" role="radio" aria-checked="${p.brand === k}" class="${p.brand === k ? 'is-on' : ''}" data-brand="${k}">${l}</button>`).join('')}</div>
            <span class="ax-error" data-err="brand" hidden></span></div>
          ${f('Engagement type', 'engagement_type', { options: Object.entries(ENG), blank: 'Choose a type', value: p.engagement_type, required: true })}
          ${f('Document type', 'doc_type', { options: [['Techno-Commercial Proposal', 'Techno-Commercial Proposal'], ['Technical Proposal', 'Technical Proposal']], value: p.doc_type })}
          ${f('Client name', 'client', { value: p.client ?? d.client, required: true })}
          ${f('Short name', 'client_short', { value: p.client_short, placeholder: 'Used in tables, for example Crestline' })}
          ${f('Industry', 'industry', { value: p.industry ?? d.industry })}
          ${f('Region and data residency', 'region', { value: p.region ?? d.region, placeholder: 'For example UAE North' })}
          ${f('Document version', 'version', { value: p.version || 'V0.1' })}
        </div></fieldset>

        <fieldset class="ax-pr-fs"><legend>What the client needs</legend>
          ${f('Brief', 'brief', { textarea: true, rows: 4, value: p.brief ?? d.brief, wide: true, placeholder: "The client's situation, pain points and goals. Upload a BRD or SOW instead if you have one." })}
          <div class="ax-field"><label for="pr-document">BRD or SOW (optional)</label><input class="ax-input" id="pr-document" name="document" type="file" accept=".pdf,.docx,.txt,.md">
            <span class="ax-hint">${p.document_name ? `Using the text of ${esc(p.document_name)} unless you choose another file. ` : ''}PDF, Word or text, up to 15 MB. Only the text is kept.</span></div>
          <div class="ax-field"><span class="ax-label-like">Target technologies</span><div class="ax-pr-chips">${TECH.map(t =>
            `<button type="button" class="ax-chip${(p.target_technologies || ['Microsoft Fabric', 'OneLake', 'Power BI']).includes(t) ? ' is-set' : ''}" data-tech="${esc(t)}" aria-pressed="${(p.target_technologies || ['Microsoft Fabric', 'OneLake', 'Power BI']).includes(t)}">${esc(t)}</button>`).join('')}</div></div>
          <div class="ax-field"><span class="ax-label-like">Source systems</span><div id="pr-sources">${(p.sources && p.sources.length ? p.sources : [{}]).map(sourceRow).join('')}</div>
            <div><button type="button" class="ax-btn ax-btn--small" data-pr-src-add>${icon('plus')}Add source</button></div></div>
          <div class="ax-grid3">
            ${f('Data volume', 'data_volume', { value: p.data_volume, placeholder: 'About 1.5 TB, growing 20% a year' })}
            ${f('Ingestion cadence', 'ingestion_cadence', { value: p.ingestion_cadence, placeholder: 'Daily batch, hourly for finance' })}
            ${f('Medallion scope', 'medallion_scope', { options: [['Full Bronze, Silver and Gold', 'Bronze, Silver and Gold'], ['Bronze only, Silver and Gold later', 'Bronze only (archive foundation)']], value: p.medallion_scope })}
          </div>
          ${f('Reports and consumption', 'consumption', { textarea: true, rows: 2, value: p.consumption, wide: true, placeholder: '12 Power BI dashboards, 3 semantic models, RLS by business unit, mobile layouts' })}
        </fieldset>

        <fieldset class="ax-pr-fs" data-when="migration" hidden><legend>Migration</legend><div class="ax-grid2">
          ${f('From (current platform)', 'm_source_platform', { value: p.migration?.source_platform, required: true, placeholder: 'Azure Synapse dedicated SQL pool, ADF' })}
          ${f('To (target platform)', 'm_target_platform', { value: p.migration?.target_platform, required: true, placeholder: 'Microsoft Fabric Lakehouse and Warehouse' })}
          ${f('Approach', 'm_stance', { value: p.migration?.stance, placeholder: 'Re-platform pipelines, refactor stored procedures' })}
          ${f('Cutover', 'm_cutover', { value: p.migration?.cutover, placeholder: 'Four week parallel run' })}
          </div><div class="ax-grid3" style="margin-top:12px">${INVENTORY.map(([k, l]) => f(l, 'inv_' + k, { number: true, type: 'number', value: p.migration?.inventory?.[k] })).join('')}</div>
          <span class="ax-hint">Only counts you enter here appear in the inventory table. The model never invents them.</span>
        </fieldset>

        <fieldset class="ax-pr-fs"><legend>Governance and extra sections</legend>
          <div class="ax-pr-checks">${check('Includes data governance', 'gov_included', p.governance?.included ?? true)}
            ${check('Microsoft Purview can be used', 'gov_purview', p.governance?.purview_allowed ?? true)}
            ${check('Project Governance Structure section', 'x_project_governance', (p.extra_sections || []).includes('project_governance'))}
            ${check('Risk and Mitigation section', 'x_risks', (p.extra_sections || []).includes('risks'))}</div>
          ${f('Governance notes', 'gov_notes', { value: p.governance?.notes, placeholder: 'Catalog, glossary, lineage, sensitivity labels for PII' })}
        </fieldset>

        <fieldset class="ax-pr-fs"><legend>Commercials</legend>
          <div class="ax-pr-checks">${check('Include commercials (from the PnL version)', 'include_commercials', p.include_commercials ?? true)}</div>
          <div class="ax-field"><span class="ax-label-like">Payment plan</span><div id="pr-plan"></div>
            <div><button type="button" class="ax-btn ax-btn--small" data-pr-plan-add>${icon('plus')}Add milestone</button> <span class="ax-error" data-err="plan" hidden></span></div></div>
          <div class="ax-grid2">
            ${f('Payment terms (one per line)', 'payment_terms', { textarea: true, rows: 2 })}
            ${f('Cloud consumption note', 'consumption_note', { textarea: true, rows: 2 })}
            ${f('Partner funding label', 'funding_label', { value: p.commercial_terms?.funding?.label, placeholder: 'Microsoft Partner Funding (indicative)' })}
            ${f('Partner funding amount (USD)', 'funding_amount', { number: true, type: 'number', value: p.commercial_terms?.funding?.amount })}
            ${f('Optional managed services, monthly (USD)', 'ms_monthly', { number: true, type: 'number', value: p.commercial_terms?.managed_services?.monthly })}
            ${f('Managed services, months', 'ms_months', { number: true, type: 'number', value: p.commercial_terms?.managed_services?.months })}
            ${f('Tax note', 'tax_note', { wide: true })}
          </div>
        </fieldset>

        <fieldset class="ax-pr-fs"><legend>People</legend><div class="ax-grid3">
          ${f('Prepared by', 'pb_name', { value: p.people?.prepared_by?.name || d.people.prepared_by.name })}
          ${f('Designation', 'pb_designation', { value: p.people?.prepared_by?.designation || d.people.prepared_by.designation })}
          ${f('Email', 'pb_email', { type: 'email', value: p.people?.prepared_by?.email })}
          ${f('Reviewed by', 'rv_name', { value: p.people?.reviewed_by?.name })}
          ${f('Designation', 'rv_designation', { value: p.people?.reviewed_by?.designation })}
          <div></div>
          ${f('Account manager', 'am_name', { value: p.people?.account_manager?.name ?? d.people.account_manager.name })}
          ${f('Email', 'am_email', { type: 'email', value: p.people?.account_manager?.email })}
          ${f('Mobile', 'am_mobile', { value: p.people?.account_manager?.mobile })}
        </div></fieldset>
      </div>
      <div class="ax-dialog-f"><span class="ax-error" data-err="_" hidden style="margin-right:auto"></span>
        <button type="button" class="ax-btn" data-x>Cancel</button>
        <button type="submit" class="ax-btn ax-btn--primary">${icon('spark')}Generate</button></div></form>`;
    document.body.appendChild(scrim);
    const form = scrim.querySelector('form');
    const prevFocus = document.activeElement;
    let brand = p.brand || '';
    const touched = new Set();

    const fillTerms = () => {                       // brand defaults, unless the person has edited them
      const t = brand && d.terms[brand];
      if (!t) return;
      const plan = p.commercial_terms?.payment_plan || t.payment_plan;
      if (!touched.has('plan')) form.querySelector('#pr-plan').innerHTML = plan.map(planRow).join('');
      if (!touched.has('payment_terms')) form.payment_terms.value = (p.commercial_terms?.payment_terms || t.payment_terms).join('\n');
      if (!touched.has('consumption_note')) form.consumption_note.value = p.commercial_terms?.consumption_note || t.consumption_note;
      if (!touched.has('tax_note')) form.tax_note.value = p.commercial_terms?.tax_note || t.tax_note;
      const rv = d.people.reviewed_by[brand];
      if (!touched.has('rv_name')) form.rv_name.value = p.people?.reviewed_by?.name || rv.name;
      if (!touched.has('rv_designation')) form.rv_designation.value = p.people?.reviewed_by?.designation || rv.designation;
    };
    const showWhen = () => form.querySelectorAll('[data-when]').forEach(el => { el.hidden = form.engagement_type.value !== el.dataset.when; });
    fillTerms(); showWhen();
    if (!brand) form.querySelector('#pr-plan').innerHTML = d.terms.automatonsx.payment_plan.map(planRow).join('');

    const close = () => { scrim.remove(); document.removeEventListener('keydown', onKey, true); prevFocus?.focus?.(); };
    const onKey = e => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
    document.addEventListener('keydown', onKey, true);
    scrim.addEventListener('mousedown', e => { if (e.target === scrim) close(); });
    const clearErr = name => { const el = form.querySelector(`[data-err="${name}"]`); if (el) { el.hidden = true; el.textContent = ''; }
      form.elements[name]?.setAttribute?.('aria-invalid', 'false'); };
    form.addEventListener('change', e => { if (e.target.name) clearErr(e.target.name); });
    form.addEventListener('input', e => {
      if (e.target.name) { touched.add(e.target.name); clearErr(e.target.name); }
      if (e.target.dataset.plan) touched.add('plan');
    });
    form.engagement_type.addEventListener('change', showWhen);
    form.addEventListener('click', e => {
      const t = e.target.closest('button');
      if (!t) return;
      if (t.hasAttribute('data-x')) close();
      else if (t.dataset.brand) {
        brand = t.dataset.brand; clearErr('brand');
        form.querySelectorAll('[data-brand]').forEach(b => { const on = b === t; b.classList.toggle('is-on', on); b.setAttribute('aria-checked', on); });
        fillTerms();
      } else if (t.dataset.tech) {
        const on = !t.classList.contains('is-set');
        t.classList.toggle('is-set', on); t.setAttribute('aria-pressed', on);
      } else if (t.hasAttribute('data-pr-src-add')) form.querySelector('#pr-sources').insertAdjacentHTML('beforeend', sourceRow());
      else if (t.hasAttribute('data-pr-src-del')) t.closest('.ax-pr-src').remove();
      else if (t.hasAttribute('data-pr-plan-add')) { touched.add('plan'); form.querySelector('#pr-plan').insertAdjacentHTML('beforeend', planRow()); }
      else if (t.hasAttribute('data-pr-plan-del')) { touched.add('plan'); t.closest('.ax-pr-plan').remove(); }
    });

    form.addEventListener('submit', async e => {
      e.preventDefault();
      const v = name => (form.elements[name]?.value || '').trim();
      const n = name => (v(name) === '' ? null : Number(v(name)));
      const on = name => !!form.elements[name]?.checked;
      const inventory = Object.fromEntries(INVENTORY.map(([k]) => [k, n('inv_' + k)]).filter(([, x]) => x !== null));
      const plan = [...form.querySelectorAll('.ax-pr-plan')].map(r => ({ milestone: r.querySelector('[data-plan="milestone"]').value.trim(),
        percent: Number(r.querySelector('[data-plan="percent"]').value || 0) })).filter(m => m.milestone);
      const intake = {
        brand, engagement_type: v('engagement_type'), doc_type: v('doc_type'), client: v('client'), client_short: v('client_short'),
        industry: v('industry'), region: v('region'), currency: 'USD', version: v('version'),
        target_technologies: [...form.querySelectorAll('[data-tech].is-set')].map(b => b.dataset.tech),
        sources: [...form.querySelectorAll('.ax-pr-src')].map(r => Object.fromEntries([...r.querySelectorAll('[data-src]')].map(i => [i.dataset.src, i.value.trim()]))).filter(s => s.name),
        data_volume: v('data_volume'), ingestion_cadence: v('ingestion_cadence'), consumption: v('consumption'), medallion_scope: v('medallion_scope'),
        governance: { included: on('gov_included'), purview_allowed: on('gov_purview'), notes: v('gov_notes') },
        extra_sections: [on('x_project_governance') && 'project_governance', on('x_risks') && 'risks'].filter(Boolean),
        include_commercials: on('include_commercials'), brief: v('brief'),
        people: { prepared_by: { name: v('pb_name'), designation: v('pb_designation'), email: v('pb_email') },
                  reviewed_by: { name: v('rv_name'), designation: v('rv_designation') },
                  account_manager: { name: v('am_name'), email: v('am_email'), mobile: v('am_mobile') } },
        commercial_terms: { payment_plan: plan, payment_terms: v('payment_terms').split('\n').map(x => x.trim()).filter(Boolean),
          consumption_note: v('consumption_note'), tax_note: v('tax_note'),
          funding: n('funding_amount') ? { label: v('funding_label'), amount: n('funding_amount') } : null,
          managed_services: n('ms_monthly') && n('ms_months') ? { monthly: n('ms_monthly'), months: n('ms_months') } : null },
      };
      if (intake.engagement_type === 'migration') {
        intake.migration = { source_platform: v('m_source_platform'), target_platform: v('m_target_platform'),
          stance: v('m_stance'), cutover: v('m_cutover'), inventory };
      }
      const file = form.elements.document.files[0];
      if (!file && p.document_text) { intake.document_text = p.document_text; intake.document_name = p.document_name; }
      const errs = {};
      if (!brand) errs.brand = 'Choose AutomatonsX or Cloud4C.';
      if (!intake.engagement_type) errs.engagement_type = 'Choose the engagement type.';
      if (!intake.client) errs.client = 'Enter the client name.';
      if (!intake.brief && !file && !intake.document_text) errs.brief = 'Write a short brief or upload the BRD or SOW.';
      if (intake.engagement_type === 'migration') {
        if (!intake.migration.source_platform) errs.m_source_platform = 'Enter the current platform.';
        if (!intake.migration.target_platform) errs.m_target_platform = 'Enter the target platform.';
      }
      const total = plan.reduce((t, m) => t + m.percent, 0);
      if (intake.include_commercials && plan.length && total !== 100) errs.plan = `The milestones add up to ${total}%. Make them 100%.`;
      let first = null;
      form.querySelectorAll('[data-err]').forEach(el => {
        const msg = errs[el.dataset.err]; el.hidden = !msg; el.textContent = msg || '';
        const input = form.elements[el.dataset.err];
        if (input && input.setAttribute) input.setAttribute('aria-invalid', msg ? 'true' : 'false');
        if (msg && !first) first = input && input.focus ? input : el;
      });
      if (first) { first.scrollIntoView({ block: 'center' }); if (first.focus) first.focus(); return; }

      const body = new FormData();
      body.append('intake', JSON.stringify(intake));
      if (file) body.append('document', file);
      const btn = form.querySelector('[type="submit"]');
      btn.disabled = true; btn.textContent = 'Starting…';
      try {
        const r = await fetch(`/api/projects/${encodeURIComponent(S.pid)}/versions/${v('version_no')}/proposals`, { method: 'POST', body });
        if (!r.ok) throw new Error(await window.axUI.errorMessage(r, "Couldn't start the proposal."));
        close();
        window.axUI.toast('Generating the proposal. It takes a minute or two; you can keep working.');
        load();
      } catch (err) {
        const el = form.querySelector('[data-err="_"]'); el.hidden = false; el.textContent = err.message;
        btn.disabled = false; btn.innerHTML = `${icon('spark')}Generate`;
      }
    });
    (form.querySelector('[data-brand]')).focus();
  }

  async function retry(id) {
    const r = await fetch(`/api/proposals/${id}/intake`);
    if (!r.ok) { window.axUI.toast(await window.axUI.errorMessage(r), { error: true }); return; }
    openForm(await r.json());
  }

  document.addEventListener('click', e => {
    const t = e.target.closest('[data-pr]');
    if (!t || !t.closest('#ax-proposals')) return;
    if (t.dataset.pr === 'new') openForm();
    if (t.dataset.pr === 'retry') retry(+t.dataset.id);
    if (t.dataset.pr === 'questions') { const id = +t.dataset.id; S.open.has(id) ? S.open.delete(id) : S.open.add(id); paint(); }
  });

  window.axProposals = {
    mount(pid) {
      if (S.pid !== pid) { S.pid = pid; S.rows = []; S.defaults = null; S.open.clear(); }
      paint();
      load();
    },
    count: () => S.rows.length,
  };
})();
