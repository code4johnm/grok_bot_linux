"""Official prompt catalog from xai-org/grok-prompts. Fetch at runtime; do not vendor."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx

from grok_bot_tui.paths import data_dir

SOURCE_REPO = "https://github.com/xai-org/grok-prompts"
SOURCE_RAW = "https://raw.githubusercontent.com/xai-org/grok-prompts/main"
LICENSE_NAME = "AGPL-3.0"
LICENSE_URL = "https://github.com/xai-org/grok-prompts/blob/main/LICENSE"

# Published filenames on xai-org/grok-prompts (main). IDs are local aliases only.
CATALOG: dict[str, str] = {
    "grok4": "grok4_system_turn_prompt_v8.j2",
    "grok3": "grok3_official0330_p1.j2",
    "ask": "ask_grok_system_prompt.j2",
    "analyze": "grok_analyze_button.j2",
    "safety-4": "grok_4_safety_prompt.txt",
    "safety-mini": "grok_4_mini_system_prompt.txt",
    "code-rc1": "grok_4_code_rc1_safety_prompt.txt",
}

NOTICE = (
    f"Cached from {SOURCE_REPO}\n"
    f"License: {LICENSE_NAME} — {LICENSE_URL}\n"
    "These files are an operator-local cache, not part of the grok-bot-tui MIT tree.\n"
)


class PromptError(Exception):
    """Safe-to-print catalog or fetch error."""


def listing() -> str:
    ids = ", ".join(CATALOG)
    return (
        f"Official prompt ids (source: xai-org/grok-prompts): {ids}\n"
        f"AGPL-3.0; fetched on demand into the local cache. /prompt <id> or /prompt off."
    )


class PromptCatalog:
    def __init__(
        self,
        cache_dir: Path | None = None,
        fetcher: Callable[[str], str] | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir is not None else data_dir() / "prompts"
        self._fetcher = fetcher
        self._timeout = timeout

    def get(self, prompt_id: str) -> str:
        key = prompt_id.strip().lower()
        filename = CATALOG.get(key)
        if filename is None:
            raise PromptError(f"Unknown prompt id {prompt_id!r}. Try /prompt for the catalog.")
        cached = self.cache_dir / filename
        if cached.is_file():
            return cached.read_text(encoding="utf-8")
        url = f"{SOURCE_RAW}/{filename}"
        text = self._download(url)
        self._write_cache(filename, text, url)
        return text

    def _download(self, url: str) -> str:
        if self._fetcher is not None:
            return self._fetcher(url)
        try:
            response = httpx.get(url, timeout=self._timeout, follow_redirects=True)
        except httpx.TimeoutException as exc:
            raise PromptError("Prompt fetch timed out.") from exc
        except httpx.RequestError as exc:
            raise PromptError("Could not fetch official prompt. Network error.") from exc
        if response.status_code >= 400:
            raise PromptError(f"Could not fetch official prompt (HTTP {response.status_code}).")
        return response.text

    def _write_cache(self, filename: str, text: str, url: str) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        notice = self.cache_dir / "NOTICE"
        if not notice.is_file():
            notice.write_text(NOTICE, encoding="utf-8")
        (self.cache_dir / filename).write_text(text, encoding="utf-8")
        meta = self.cache_dir / f"{filename}.source"
        meta.write_text(
            f"source_url={url}\nlicense={LICENSE_NAME}\nlicense_url={LICENSE_URL}\nrepo={SOURCE_REPO}\n",
            encoding="utf-8",
        )
