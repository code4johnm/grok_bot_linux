"""Open the official Grok GUI in the default browser. No scraping, no internals."""

from __future__ import annotations

import webbrowser
from collections.abc import Callable

# Official web app per https://docs.x.ai/grok/overview and https://docs.x.ai/grok/faq
# (use grok.com; grok.x.ai is not the recommended host).
OFFICIAL_GUI_URL = "https://grok.com"


def open_official_gui(
    url: str = OFFICIAL_GUI_URL,
    *,
    opener: Callable[[str], bool] | None = None,
) -> str:
    """Open or focus the official Grok GUI. `opener` is injectable for tests."""
    open_url = opener or webbrowser.open
    try:
        ok = open_url(url)
    except Exception as exc:  # noqa: BLE001 — one-line error, do not crash the TUI
        return f"Could not open official Grok GUI ({url}): {exc}"
    if ok is False:
        return f"Could not open official Grok GUI ({url}). Open it in a browser."
    return f"Opened official Grok GUI: {url}"
