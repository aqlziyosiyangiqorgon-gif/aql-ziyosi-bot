"""HTML escaping and sanitization utilities."""

import html


def escape_html(text: str | None) -> str:
    """Safely escapes text for Telegram HTML parse mode."""
    if not text:
        return ""
    return html.escape(str(text), quote=True)
