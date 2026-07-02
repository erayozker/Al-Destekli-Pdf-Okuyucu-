from __future__ import annotations

from markupsafe import Markup, escape


def render_highlights(text: str) -> Markup:
    safe_text = escape(text or "")
    highlighted = str(safe_text).replace("[[HIGHLIGHT]]", "<mark>").replace("[[/HIGHLIGHT]]", "</mark>")
    return Markup(highlighted)
