"""Fetch and normalize Grok agents/models after sign-in."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from grok_bot_tui.client import DEFAULT_BASE_URL, GrokAPIError, error_message_from_body


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    blurb: str
    status: str = "ready"
    icon_url: str | None = None
    instructions: str = ""

    @property
    def seed(self) -> str:
        return self.id or self.name


def _from_model(item: dict[str, Any]) -> Agent:
    ident = str(item.get("id") or item.get("name") or "").strip()
    name = str(item.get("name") or ident).strip() or ident
    owned = str(item.get("owned_by") or item.get("object") or "model")
    blurb = str(item.get("description") or f"{owned} · selectable for chat")
    return Agent(id=ident, name=name, blurb=blurb, status="ready", icon_url=item.get("icon_url"))


def normalize_list(payload: Any) -> list[Agent]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("data") or payload.get("models") or payload.get("agents") or []
    else:
        rows = []
    agents: list[Agent] = []
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        agent = _from_model(item)
        if not agent.id or agent.id in seen:
            continue
        seen.add(agent.id)
        agents.append(agent)
    agents.sort(key=lambda a: a.name.lower())
    return agents


class AgentCatalog:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            transport=transport,
        )
        self.cache: list[Agent] = []

    def close(self) -> None:
        self._http.close()

    def refresh(self) -> list[Agent]:
        try:
            response = self._http.get("/models")
        except httpx.TimeoutException as exc:
            raise GrokAPIError("Request timed out.") from exc
        except httpx.RequestError as exc:
            raise GrokAPIError("Network error. Check connectivity and try again.") from exc
        try:
            body = response.json()
        except Exception:
            body = None
        if response.status_code >= 400:
            raise GrokAPIError(error_message_from_body(body, response.status_code))
        self.cache = normalize_list(body)
        return self.cache
