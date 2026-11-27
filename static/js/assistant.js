// PnL assistant drawer (DESIGN.md 9.2). Streams answers from /api/assistant/chat (server-sent events).
(function () {
  'use strict';
  const ui = window.axUI;
  const esc = ui.esc;
  const icon = n => (document.getElementById('ax-icon-' + n) || {}).innerHTML || '';
  const S = { open: false, loaded: false, available: true, reason: '', sid: null, messages: [], busy: false };
  const SUGGESTIONS = ['Which open projects are below the AX target?', 'What changed across the versions of this project?',
    'What if the AX margin were 20% and the discount 0?', 'Download this project as Excel'];

  // Markdown from the model -> safe HTML (escape first; tables, bold, lists, paragraphs only).
  function md(text) {
    const lines = esc(text || '').split('\n');
    const out = [];
    let i = 0;
    const inline = s => s.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/(^|[\s(])_([^_]+)_(?=$|[\s.,;:)])/g, '$1<em>$2</em>');
    while (i < lines.length) {
      const l = lines[i];
      if (/^\s*\|.*\|\s*$/.test(l) && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1] || '')) {
        const cells = r => r.trim().replace(/^\||\|$/g, '').split('|').map(c => inline(c.trim()));
        const head = cells(l); i += 2;
        const rows = [];
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
        const num = c => /^[−\-+]?[$₹]?[\d,.]+[%kM]?$/.test(c.replace(/<[^>]+>/g, ''));
        out.push(`<div class="ax-table-wrap"><table class="ax-table ax-chat-table"><thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${
          rows.map(r => `<tr>${r.map(c => `<td class="${num(c) ? 'r' : ''}">${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
        continue;
      }
      if (/^\s*[-*] /.test(l)) {
        const items = [];
        while (i < lines.length && /^\s*[-*] /.test(lines[i])) items.push(inline(lines[i++].replace(/^\s*[-*] /, '')));
        out.push(`<ul>${items.map(x => `<li>${x}</li>`).join('')}</ul>`);
        continue;
      }
      if (/^\s*\d+\. /.test(l)) {
        const items = [];
        while (i < lines.length && /^\s*\d+\. /.test(lines[i])) items.push(inline(lines[i++].replace(/^\s*\d+\. /, '')));
        out.push(`<ol>${items.map(x => `<li>${x}</li>`).join('')}</ol>`);
        continue;
      }
      if (/^#{1,4} /.test(l)) { out.push(`<p><b>${inline(l.replace(/^#+ /, ''))}</b></p>`); i++; continue; }
      if (!l.trim()) { i++; continue; }
      // Always take the current line (a half-streamed table row lands here), then any plain lines after it.
      const para = [inline(lines[i++])];
      while (i < lines.length && lines[i].trim() && !/^\s*([-*] |\d+\. |\|)/.test(lines[i]) && !/^#{1,4} /.test(lines[i])) para.push(inline(lines[i++]));
      out.push(`<p>${para.join('<br>')}</p>`);
    }
    return out.join('');
  }

  function context() {
    const ws = window.axWorkspace;
    if (ws && ws.pid) {
      const latest = (ws.versions || [])[0];
      return { project_id: ws.pid, version: ws.dirty ? null : latest ? latest.version_no : null, unsaved: !!ws.dirty,
               label: `${(ws.p && ws.p.project && ws.p.project.customer) || ws.pid}, ${ws.dirty ? 'unsaved changes (I read the saved version)' : latest ? 'version ' + latest.version_no : 'not saved yet'}` };
    }
    return { label: 'All projects' };
  }

  function msgHtml(m) {
    if (m.role === 'user') return `<div class="ax-msg ax-msg--user">${esc(m.text)}</div>`;
    const files = (m.files || []).map(f => `<div class="ax-file"><span class="ax-file-ico">XLS</span>
      <div style="flex:1;min-width:0"><b>${esc(f.filename)}</b><span class="ax-caption">Link works for 15 minutes</span></div>
      <a class="ax-btn ax-btn--small" href="${esc(f.url)}" download>${icon('download')}Download</a></div>`).join('');
    const scen = m.scenario ? `<button type="button" class="ax-btn ax-btn--small" data-scenario='${esc(JSON.stringify(m.scenario))}'>Open in editor as unsaved changes</button>` : '';
    return `<div class="ax-msg ax-msg--assistant"><div class="ax-msg-body">${m.text ? md(m.text) : (m.pending ? '<span class="ax-typing"><i></i><i></i><i></i></span>' : '')}
        ${m.tools && m.tools.length ? `<div class="ax-caption">${m.tools.map(esc).join(' · ')}</div>` : ''}${files}${scen}</div>
      ${(m.sources || []).length ? `<div class="ax-src">${m.sources.map(s => `<span>${esc(s)}</span>`).join('')}</div>` : ''}
      ${m.error ? `<div class="ax-error" role="alert">${esc(m.error)}</div>` : ''}</div>`;
  }

  function drawer() {
    let el = document.getElementById('ax-assistant');
    if (el) return el;
    el = document.createElement('aside');
    el.id = 'ax-assistant';
    el.className = 'ax-drawer ax-assistant';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-label', 'PnL assistant');
    el.hidden = true;
    el.innerHTML = `<div class="ax-drawer-h">${icon('spark')}<div style="flex:1"><h2 class="ax-h2">PnL assistant</h2>
        <div class="ax-caption">Reads projects, versions and rate cards. Can't change saved data.</div></div>
        <button type="button" class="ax-btn ax-btn--ghost ax-btn--small" data-act="new" title="Start a new conversation">New chat</button>
        <button type="button" class="ax-btn ax-btn--ghost ax-btn--icon" data-act="close" aria-label="Close assistant">${icon('x')}</button></div>
      <div class="ax-drawer-ctx" id="ax-as-ctx"></div>
      <div class="ax-chat" id="ax-as-log" aria-live="polite" tabindex="0" role="log" aria-label="Conversation"></div>
      <div class="ax-sugg" id="ax-as-sugg"></div>
      <form class="ax-composer" id="ax-as-form"><textarea class="ax-input" id="ax-as-q" rows="2" placeholder="Ask about projects, versions or rates" aria-label="Message"></textarea>
        <button type="submit" class="ax-btn ax-btn--primary ax-btn--icon" aria-label="Send">${icon('spark')}</button></form>`;
    document.body.appendChild(el);
    el.addEventListener('click', e => {
      const t = e.target.closest('button');
      if (!t) return;
      if (t.dataset.act === 'close') close();
      if (t.dataset.act === 'new') newChat();
      if (t.dataset.sugg) ask(t.dataset.sugg);
      if (t.dataset.scenario) openScenario(JSON.parse(t.dataset.scenario));
    });
    el.querySelector('#ax-as-form').addEventListener('submit', e => { e.preventDefault(); const q = el.querySelector('#ax-as-q'); ask(q.value); q.value = ''; });
    el.querySelector('#ax-as-q').addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); el.querySelector('#ax-as-form').requestSubmit(); }
    });
    el.addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); close(); } });
    return el;
  }

  function render() {
    const el = drawer();
    el.querySelector('#ax-as-ctx').innerHTML = `Looking at: <b>${esc(context().label)}</b>`;
    const log = el.querySelector('#ax-as-log');
    if (!S.available) {
      log.innerHTML = `<div class="ax-empty"><b>The assistant isn't set up yet</b>${esc(S.reason)}</div>`;
    } else if (!S.messages.length) {
      log.innerHTML = `<div class="ax-msg ax-msg--assistant"><div class="ax-msg-body"><p>Ask about any project, version or rate. Every number comes from the same calculator the editor uses.</p></div></div>`;
    } else {
      log.innerHTML = S.messages.map(msgHtml).join('');
    }
    log.scrollTop = log.scrollHeight;
    el.querySelector('#ax-as-sugg').innerHTML = S.available && !S.busy && !S.messages.length ? SUGGESTIONS.map(s => `<button type="button" data-sugg="${esc(s)}">${esc(s)}</button>`).join('') : '';
    el.querySelector('#ax-as-form button').disabled = S.busy || !S.available;
  }

  async function load() {
    if (S.loaded) return;
    try {
      const r = await fetch('/api/assistant/session');
      const s = await r.json();
      S.available = s.available; S.reason = s.reason || ''; S.sid = s.id || null; S.messages = s.messages || [];
      S.loaded = true;
    } catch { S.available = false; S.reason = "The assistant couldn't be reached."; }
  }

  async function open(question) {
    const el = drawer();
    el.hidden = false;
    S.open = true;
    await load();
    if (!S.available && question && window.axShell) { close(); window.axShell.search(question); return; }
    render();
    if (question) ask(question); else el.querySelector('#ax-as-q').focus();
  }
  function close() { const el = document.getElementById('ax-assistant'); if (el) el.hidden = true; S.open = false; }

  async function newChat() {
    if (S.busy) return;
    const r = await fetch('/api/assistant/session', { method: 'POST' });
    if (r.ok) { S.sid = (await r.json()).id; S.messages = []; render(); }
  }

  async function ask(text) {
    text = (text || '').trim();
    if (!text || S.busy || !S.available) return;
    S.busy = true;
    S.messages.push({ role: 'user', text });
    const m = { role: 'assistant', text: '', pending: true, tools: [], sources: [], files: [] };
    S.messages.push(m);
    render();
    const ctx = context();
    try {
      const res = await fetch('/api/assistant/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: S.sid, context: ctx.project_id ? ctx : null }) });
      if (!res.ok) throw new Error(await ui.errorMessage(res, 'The assistant could not answer.'));
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let cut;
        while ((cut = buf.indexOf('\n\n')) >= 0) {
          const line = buf.slice(0, cut); buf = buf.slice(cut + 2);
          if (!line.startsWith('data: ')) continue;
          const ev = JSON.parse(line.slice(6));
          if (ev.type === 'session') S.sid = ev.id;
          if (ev.type === 'text') { m.text += ev.text; m.pending = false; }
          if (ev.type === 'tool' && ev.status === 'running') m.tools.push(`Checking ${ev.name.replace(/_/g, ' ')}`);
          if (ev.type === 'sources') m.sources = ev.items;
          if (ev.type === 'file') m.files.push(ev);
          if (ev.type === 'scenario') m.scenario = { project_id: ev.project_id, overrides: ev.overrides };
          if (ev.type === 'error') m.error = ev.message;
          render();
        }
      }
    } catch (e) {
      m.error = e.message;
    }
    m.pending = false; m.tools = [];
    S.busy = false;
    render();
  }

  function openScenario(s) {
    try { sessionStorage.setItem('ax-scenario', JSON.stringify(s)); } catch { /* falls back to plain open */ }
    const here = window.axWorkspace && window.axWorkspace.pid === s.project_id;
    if (here && window.axWorkspace.applyScenario) { window.axWorkspace.applyScenario(); close(); return; }
    window.location.href = '/projects/' + encodeURIComponent(s.project_id) + '?scenario=1';
  }

  document.addEventListener('click', e => {
    const t = e.target.closest('[data-ax-action="assistant"]');
    if (t) { e.preventDefault(); open(t.dataset.question || ''); }
  });
  window.axAssistant = { open, ask, close, state: S };
})();
