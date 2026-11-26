// AX shell: rail navigation, URL routing for the home screens, global search.
// The screens themselves are still the legacy tab panes driven by app.js; the rail
// switches them by clicking their (hidden) tab links so app.js loaders run as before.
(function () {
  'use strict';

  const body = document.body;
  const EDITOR = body.dataset.editorMode === 'true';

  const ROUTES = {
    projects:  { path: '/',            tab: '#tab-all-projects', rail: 'projects',  title: 'Projects' },
    dashboard: { path: '/dashboard',   tab: '#tab-dashboard',    rail: 'dashboard', title: 'Dashboard' },
    rates:     { path: '/rates',         tab: '#tab-rates', rail: 'rates', title: 'Rates and roles', sub: 'matrix' },
    roles:     { path: '/rates/roles',   tab: '#tab-rates', rail: 'rates', title: 'Rates and roles', sub: 'roles' },
    history:   { path: '/rates/history', tab: '#tab-rates', rail: 'rates', title: 'Rates and roles', sub: 'history' },
    bookings:  { path: '/bookings',    tab: '#tab-bookings',     rail: 'bookings',  title: 'Order bookings' },
    funnel:    { path: '/funnel',      tab: '#tab-funnel',       rail: 'funnel',    title: 'Funnel report' },
  };
  let current = null;

  function routeForPath(path) {
    return Object.keys(ROUTES).find(k => ROUTES[k].path === path) || 'projects';
  }

  function setRailActive(rail) {
    document.querySelectorAll('.ax-nav [data-ax-route]').forEach(a => {
      a.classList.toggle('is-active', a.dataset.axRoute === rail);
      if (a.dataset.axRoute === rail) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
  }

  function legacyLink(tab) {
    return document.querySelector(`#mainTabs a[href="${tab}"]`);
  }

  function show(route, push) {
    const r = ROUTES[route];
    if (!r) return;
    if (EDITOR || !legacyLink(r.tab)) {          // not on the home page: navigate
      window.location.href = r.path;
      return;
    }
    current = route;
    legacyLink(r.tab).click();                     // runs the legacy loader + Bootstrap tab switch
    setRailActive(r.rail);
    if (r.sub && window.axRates) window.axRates.open(r.sub);
    document.title = `${r.title} | AutomatonsX`;
    if (push && window.location.pathname !== r.path) history.pushState({ route }, '', r.path);
  }

  function openUsers() {
    const el = document.getElementById('usersModal');
    if (el && window.bootstrap) bootstrap.Modal.getOrCreateInstance(el).show();
  }

  function search(q) {
    q = (q || '').trim();
    if (EDITOR || !legacyLink(ROUTES.projects.tab)) {
      window.location.href = '/' + (q ? '?q=' + encodeURIComponent(q) : '');
      return;
    }
    if (typeof saveAllProjectsSearch === 'function') saveAllProjectsSearch(q);
    show('projects', true);
  }

  // Called by app.js once the session and data have loaded (home page only).
  function openInitialTab() {
    let route = body.dataset.initialTab || routeForPath(window.location.pathname);
    if (!ROUTES[route]) route = 'projects';
    const q = new URLSearchParams(window.location.search).get('q');
    if (q !== null && typeof saveAllProjectsSearch === 'function') saveAllProjectsSearch(q);
    show(route, false);
    history.replaceState({ route }, '', ROUTES[route].path + (q ? '?q=' + encodeURIComponent(q) : ''));
    if (body.dataset.openUsers === 'true') openUsers();
  }

  document.addEventListener('click', e => {
    const a = e.target.closest('[data-ax-route]');
    if (!a) return;
    const route = a.dataset.axRoute;
    if (route === 'users') {
      if (document.getElementById('usersModal')) { e.preventDefault(); openUsers(); }
      return;
    }
    if (EDITOR || !ROUTES[route] || !legacyLink(ROUTES[route].tab)) return;   // normal navigation
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;      // new tab / window
    e.preventDefault();
    show(route, true);
  });

  window.addEventListener('popstate', e => {
    if (EDITOR) return;
    show((e.state && e.state.route) || routeForPath(window.location.pathname), false);
  });

  const input = document.getElementById('ax-global-search');
  if (input) {
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); search(input.value); }
      if (e.key === 'Escape') input.blur();
    });
  }
  document.addEventListener('keydown', e => {
    if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return;
    const t = document.activeElement;
    if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable)) return;
    e.preventDefault();
    input && input.focus();
  });

  window.axShell = { show, openInitialTab, openUsers, search, get current() { return current; } };
})();
