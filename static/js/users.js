// Users (DESIGN.md 5.6): add, reset password (temporary), remove (switch off), restore.
(function () {
  'use strict';
  const { esc, toast, dialog, errorMessage } = window.axUI;
  const me = (window.AX.user || {}).username;
  const icon = n => (document.getElementById('ax-icon-' + n) || {}).innerHTML || '';
  const root = document.getElementById('ax-users');
  let users = [];
  const fmtDate = v => { const d = new Date(String(v || '').replace(' ', 'T')); return isNaN(d) ? '' : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }); };

  async function api(url, opts = {}) {
    const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts });
    if (!res.ok) throw new Error(await errorMessage(res));
    return res.json();
  }

  async function load() {
    try { users = await api('/api/users'); }
    catch (e) { document.getElementById('ax-users-table').innerHTML = `<div class="ax-empty"><b>Users couldn't load</b>${esc(e.message)}</div>`; return; }
    users.sort((a, b) => (b.active - a.active) || (a.name || a.username).localeCompare(b.name || b.username));
    document.getElementById('ax-users-table').innerHTML = `<table class="ax-table">
      <thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Added</th><th>Status</th><th><span class="ax-sr">Actions</span></th></tr></thead>
      <tbody>${users.map(u => `<tr class="${u.active ? '' : 'ax-row-off'}">
        <td><b>${esc(u.name || u.username)}</b>${u.username === me ? ' <span class="ax-caption">(you)</span>' : ''}</td>
        <td class="ax-muted">${esc(u.username)}</td>
        <td><span class="ax-pill ax-pill--${u.role === 'admin' ? 'submitted' : 'draft'}">${u.role === 'admin' ? 'Admin' : 'User'}</span></td>
        <td class="ax-faint">${fmtDate(u.created_at)}</td>
        <td>${u.active ? (u.must_change_password ? '<span class="ax-caption">Must set a new password</span>' : 'Active') : `<span class="ax-faint">Removed ${fmtDate(u.deactivated_at)}</span>`}</td>
        <td class="r" style="white-space:nowrap">${u.active
          ? `${u.username !== me ? `<button type="button" class="ax-btn ax-btn--ghost ax-btn--small" data-reset="${esc(u.username)}">${icon('key')}Reset password</button>
             <button type="button" class="ax-btn ax-btn--ghost ax-btn--small ax-btn--danger" data-remove="${esc(u.username)}">Remove</button>` : ''}`
          : `<button type="button" class="ax-btn ax-btn--ghost ax-btn--small" data-restore="${esc(u.username)}">Restore</button>`}</td>
      </tr>`).join('')}</tbody></table>`;
  }

  async function addUser() {
    const res = await dialog({
      title: 'Add user',
      fields: [
        { name: 'name', label: 'Full name', required: true },
        { name: 'username', label: 'Username', required: true, hint: 'Lowercase letters, numbers, dots or dashes.' },
        { name: 'password', label: 'Temporary password', type: 'password', autocomplete: 'new-password', required: true,
          hint: 'At least 8 characters. They choose their own at first sign-in.' },
      ],
      body: `<div class="ax-field"><label for="ax-new-role">Role</label><select class="ax-input" id="ax-new-role" name="role">
        <option value="user">User</option><option value="admin">Admin</option></select></div>`,
      validate: v => {
        const e = {};
        if (!v.name.trim()) e.name = 'Enter their full name.';
        const u = v.username.trim().toLowerCase();
        if (!/^[a-z0-9][a-z0-9._-]{1,39}$/.test(u)) e.username = 'Use 2 to 40 lowercase letters, numbers, dots, dashes or underscores.';
        else if (users.some(x => x.username === u)) e.username = `There is already a user called "${u}".`;
        if (v.password.length < 8) e.password = 'The temporary password needs at least 8 characters.';
        return e;
      },
      confirmLabel: 'Add user',
    });
    if (!res) return;
    const v = res.values;
    try {
      await api('/api/users', { method: 'POST', body: JSON.stringify({ name: v.name.trim(), username: v.username.trim().toLowerCase(), password: v.password, role: v.role }) });
      toast(`${v.name.trim()} added`);
      load();
    } catch (e) { toast(e.message, { error: true }); }
  }

  async function reset(username) {
    const u = users.find(x => x.username === username);
    const res = await dialog({
      title: `Reset password for ${u.name || u.username}`,
      fields: [{ name: 'password', label: 'Temporary password', type: 'password', autocomplete: 'new-password', required: true,
        hint: "They'll be asked to change it at their next sign-in." }],
      validate: v => v.password.length >= 8 ? {} : { password: 'The temporary password needs at least 8 characters.' },
      confirmLabel: 'Reset password',
    });
    if (!res) return;
    try {
      await api(`/api/users/${encodeURIComponent(username)}/password`, { method: 'POST', body: JSON.stringify({ password: res.values.password }) });
      toast('Password reset');
      load();
    } catch (e) { toast(e.message, { error: true }); }
  }

  async function setActive(username, active) {
    const u = users.find(x => x.username === username);
    if (!active) {
      const ok = await dialog({ title: `Remove ${u.name || u.username}?`, danger: true, confirmLabel: 'Remove user',
        body: `<p>${esc(u.name || u.username)} won't be able to sign in. Their projects and saved versions stay as they are, and you can restore the account later.</p>` });
      if (!ok) return;
    }
    try {
      await api(`/api/users/${encodeURIComponent(username)}/active`, { method: 'POST', body: JSON.stringify({ active }) });
      toast(active ? `${u.name || u.username} restored` : `${u.name || u.username} removed`,
        active ? {} : { undo: () => setActive(username, true) });
      load();
    } catch (e) { toast(e.message, { error: true }); }
  }

  root.addEventListener('click', e => {
    const t = e.target.closest('button');
    if (!t) return;
    if (t.dataset.act === 'add') addUser();
    if (t.dataset.reset) reset(t.dataset.reset);
    if (t.dataset.remove) setActive(t.dataset.remove, false);
    if (t.dataset.restore) setActive(t.dataset.restore, true);
  });
  load();
})();
