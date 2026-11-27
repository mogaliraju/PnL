"""Shared UI helpers for the AX shell: icons, margin health, status pills and template globals."""
from __future__ import annotations

from markupsafe import Markup, escape

from pnl import config

# Line icons, 24x24 viewBox, 1.8 stroke (DESIGN.md 13.2). Same set as the prototype.
def _circle(x, y, r):
    return f"M{x - r} {y}a{r} {r} 0 1 0 {2 * r} 0a{r} {r} 0 1 0 {-2 * r} 0"


ICONS = {
    'folder': ['M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.7-.9l-.8-1.2A2 2 0 0 0 7.9 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2z'],
    'chart': ['M3 3v18h18', 'M7 16V10', 'M12 16V5', 'M17 16v-4'],
    'grid': ['M3 3h18v18H3z', 'M3 9h18', 'M3 15h18', 'M9 3v18'],
    'users': ['M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2', _circle(9, 7, 4), 'M22 21v-2a4 4 0 0 0-3-3.9', 'M16 3.1a4 4 0 0 1 0 7.8'],
    'search': [_circle(11, 11, 7), 'm21 21-4.3-4.3'],
    'spark': ['M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z', 'M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z'],
    'plus': ['M12 5v14', 'M5 12h14'],
    'download': ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'M7 10l5 5 5-5', 'M12 15V3'],
    'upload': ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'M17 8l-5-5-5 5', 'M12 3v12'],
    'history': ['M3 12a9 9 0 1 0 3-6.7L3 8', 'M3 3v5h5', 'M12 7v5l4 2'],
    'x': ['M18 6 6 18', 'M6 6l12 12'],
    'trash': ['M3 6h18', 'M19 6l-1 14H6L5 6', 'M10 11v6', 'M14 11v6', 'M9 6V4h6v2'],
    'alert': ['M12 9v4', 'M12 17h.01', 'M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z'],
    'compare': ['M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3', 'M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3', 'M12 2v20'],
    'columns': ['M3 3h18v18H3z', 'M9 3v18', 'M15 3v18'],
    'lock': ['M5 11h14v10H5z', 'M8 11V7a4 4 0 0 1 8 0v4'],
    'check': ['M20 6 9 17l-5-5'],
    'save': ['M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z', 'M17 21v-8H7v8', 'M7 3v5h8'],
    'copy': ['M9 9h12v12H9z', 'M5 15H3V3h12v2'],
    'back': ['M15 18l-6-6 6-6'],
    'archive': ['M3 4h18v4H3z', 'M5 8v12h14V8', 'M10 12h4'],
    'key': [_circle(7.5, 15.5, 4.5), 'm10.7 12.3 9.8-9.8', 'm16 7 3 3', 'm19 4 2 2'],
    'receipt': ['M4 2v20l3-2 3 2 3-2 3 2 3-2 1 .7V2l-1 .7-3-2-3 2-3-2-3 2-3-2z', 'M8 7h8', 'M8 11h8', 'M8 15h5'],
    'funnel': ['M3 4h18l-7 8v6l-4 2v-8z'],
    'logout': ['M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4', 'M16 17l5-5-5-5', 'M21 12H9'],
    'sun': [_circle(12, 12, 4), 'M12 2v2', 'M12 20v2', 'M4.9 4.9l1.4 1.4', 'M17.7 17.7l1.4 1.4', 'M2 12h2', 'M20 12h2', 'M4.9 19.1l1.4-1.4', 'M17.7 6.3l1.4-1.4'],
    'moon': ['M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z'],
    'gear': [_circle(12, 12, 3), 'M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z'],
}


def icon(name: str, cls: str = 'ax-i', label: str | None = None) -> Markup:
    paths = ''.join(f'<path d="{d}"/>' for d in ICONS.get(name, []))
    aria = f'role="img" aria-label="{escape(label)}"' if label else 'aria-hidden="true"'
    return Markup(f'<svg class="{escape(cls)}" viewBox="0 0 24 24" {aria}>{paths}</svg>')


def health_class(value) -> str:
    """'good' / 'warn' / 'bad' for an AX margin percentage (0-100)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 'bad'
    if v >= config.AX_MARGIN_GOOD:
        return 'good'
    if v >= config.AX_MARGIN_WARN:
        return 'warn'
    return 'bad'


STATUS_SLUGS = {'draft': 'draft', 'submitted': 'submitted', 'won': 'won', 'lost': 'lost',
                'on hold': 'on-hold', 'onhold': 'on-hold'}


def status_slug(status) -> str:
    return STATUS_SLUGS.get(str(status or '').strip().lower(), 'draft')


def initials(name: str) -> str:
    parts = [p for p in str(name or '').replace('.', ' ').split() if p]
    if not parts:
        return '?'
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else '')).upper()


def register(app) -> None:
    app.jinja_env.globals.update(icon=icon, health_class=health_class, status_slug=status_slug,
                                 initials=initials)

    @app.context_processor
    def _ax_context():
        return {
            'ax_thresholds': {'good': config.AX_MARGIN_GOOD, 'warn': config.AX_MARGIN_WARN},
            'feature_bookings_funnel': config.FEATURE_BOOKINGS_FUNNEL,
        }
