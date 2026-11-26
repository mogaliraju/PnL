// AX UI kit: dialogs, toasts with Undo, popovers (DESIGN.md 6, 11). No native alert/confirm/prompt.
(function () {
  'use strict';

  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ── Dialog ────────────────────────────────────────────────────────────
  // axDialog({title, body (html), confirmLabel, cancelLabel, danger, fields}) -> Promise<false | true | {values}>
  function dialog(opts) {
    return new Promise(resolve => {
      const prevFocus = document.activeElement;
      const scrim = document.createElement('div');
      scrim.className = 'ax-scrim';
      const id = 'ax-dlg-' + Math.random().toString(36).slice(2, 8);
      const fields = (opts.fields || []).map(f => `
        <div class="ax-field">
          <label for="${id}-${f.name}">${esc(f.label)}</label>
          <input class="ax-input" id="${id}-${f.name}" name="${esc(f.name)}" type="${f.type || 'text'}"
                 value="${esc(f.value || '')}" autocomplete="${f.autocomplete || 'off'}" ${f.required ? 'required' : ''}>
          ${f.hint ? `<span class="ax-hint">${esc(f.hint)}</span>` : ''}
          <span class="ax-error" data-err="${esc(f.name)}" hidden></span>
        </div>`).join('');
      scrim.innerHTML = `
        <form class="ax-dialog" role="dialog" aria-modal="true" aria-labelledby="${id}-t" novalidate>
          <div class="ax-dialog-h"><h2 class="ax-h2" id="${id}-t">${esc(opts.title)}</h2>
            <button type="button" class="ax-btn ax-btn--ghost ax-btn--icon" data-x aria-label="Close">✕</button></div>
          <div class="ax-dialog-b">${opts.body || ''}${fields}</div>
          <div class="ax-dialog-f">
            ${opts.cancelLabel === null ? '' : `<button type="button" class="ax-btn" data-x>${esc(opts.cancelLabel || 'Cancel')}</button>`}
            <button type="submit" class="ax-btn ${opts.danger ? 'ax-btn--danger' : 'ax-btn--primary'}">${esc(opts.confirmLabel || 'OK')}</button>
          </div>
        </form>`;
      document.body.appendChild(scrim);
      const form = scrim.querySelector('form');
      const close = result => {
        scrim.remove();
        document.removeEventListener('keydown', onKey, true);
        if (prevFocus && prevFocus.focus) prevFocus.focus();
        resolve(result);
      };
      const onKey = e => {
        if (e.key === 'Escape') { e.stopPropagation(); close(false); }
        if (e.key === 'Tab') {                       // keep focus inside the dialog
          const f = [...form.querySelectorAll('button, input, select, textarea, [tabindex]:not([tabindex="-1"])')].filter(el => !el.disabled);
          if (!f.length) return;
          const first = f[0], last = f[f.length - 1];
          if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
          else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
      };
      document.addEventListener('keydown', onKey, true);
      scrim.addEventListener('mousedown', e => { if (e.target === scrim) close(false); });
      scrim.querySelectorAll('[data-x]').forEach(b => b.addEventListener('click', () => close(false)));
      form.addEventListener('submit', e => {
        e.preventDefault();
        if (!opts.fields) { close(true); return; }
        const values = Object.fromEntries(new FormData(form).entries());
        const errors = opts.validate ? (opts.validate(values) || {}) : {};
        let bad = false;
        form.querySelectorAll('[data-err]').forEach(el => {
          const msg = errors[el.dataset.err];
          el.hidden = !msg; el.textContent = msg || '';
          const input = form.querySelector(`[name="${el.dataset.err}"]`);
          if (input) input.setAttribute('aria-invalid', msg ? 'true' : 'false');
          if (msg && !bad) { bad = true; input && input.focus(); }
        });
        if (!bad) close({ values });
      });
      (form.querySelector('input') || form.querySelector('[type="submit"]')).focus();
    });
  }

  // ── Toast ─────────────────────────────────────────────────────────────
  // axToast(message, {error, undo: fn, actionLabel})
  function toast(message, opts = {}) {
    let wrap = document.querySelector('.ax-toasts');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.className = 'ax-toasts';
      wrap.setAttribute('aria-live', 'polite');
      document.body.appendChild(wrap);
    }
    const t = document.createElement('div');
    t.className = 'ax-toast' + (opts.error ? ' ax-toast--error' : '');
    t.setAttribute('role', opts.error ? 'alert' : 'status');
    t.innerHTML = `<span>${esc(message)}</span>`;
    let timer;
    if (opts.undo) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = opts.actionLabel || 'Undo';
      b.addEventListener('click', () => { clearTimeout(timer); t.remove(); opts.undo(); });
      t.appendChild(b);
    }
    wrap.appendChild(t);
    timer = setTimeout(() => t.remove(), opts.error ? 6000 : (opts.undo ? 8000 : 4000));
    return t;
  }

  // ── Popover ───────────────────────────────────────────────────────────
  let openPop = null;
  function closePopover() {
    if (!openPop) return;
    openPop.el.remove();
    openPop.anchor.setAttribute('aria-expanded', 'false');
    document.removeEventListener('mousedown', openPop.outside, true);
    document.removeEventListener('keydown', openPop.key, true);
    openPop = null;
  }
  // axPopover(anchorEl, html, {onRender(el)}) - toggles
  function popover(anchor, html, opts = {}) {
    if (openPop && openPop.anchor === anchor) { closePopover(); return null; }
    closePopover();
    const el = document.createElement('div');
    el.className = 'ax-pop';
    el.innerHTML = html;
    document.body.appendChild(el);
    const r = anchor.getBoundingClientRect();
    const left = Math.max(8, Math.min(r.left + window.scrollX, window.scrollX + document.documentElement.clientWidth - el.offsetWidth - 8));
    el.style.top = (r.bottom + window.scrollY + 6) + 'px';
    el.style.left = left + 'px';
    anchor.setAttribute('aria-expanded', 'true');
    const outside = e => { if (!el.contains(e.target) && !anchor.contains(e.target)) closePopover(); };
    const key = e => { if (e.key === 'Escape') { closePopover(); anchor.focus(); } };
    document.addEventListener('mousedown', outside, true);
    document.addEventListener('keydown', key, true);
    openPop = { el, anchor, outside, key };
    if (opts.onRender) opts.onRender(el);
    const first = el.querySelector('input, button');
    if (first) first.focus();
    return el;
  }

  // Readable message from a failed fetch Response.
  async function errorMessage(res, fallback) {
    try { const j = await res.json(); if (j && j.error) return j.error; } catch { /* not JSON */ }
    return fallback || 'Something went wrong. Try again.';
  }

  window.axUI = { dialog, toast, popover, closePopover, esc, errorMessage };
})();
