"""Optional xAI Grok multi-agent research client.

This module is a research assistant, not a directional trading specialist.
It is never called automatically by the live signal engine. It uses only
xAI's built-in web_search and x_search tools; no exchange, wallet, order,
account, or arbitrary MCP tools are exposed.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_API_URL = "https://api.x.ai/v1/responses"
_DEFAULT_MODEL = "grok-4.20-multi-agent"


@dataclass(frozen=True)
class GrokResearchReport:
    model: str
    text: str
    request_id: str | None = None
    source_urls: tuple[str, ...] = ()
    usage: dict[str, Any] | None = None
    research_only: bool = True
    live_orders: bool = False


def _extract_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    chunks: list[str] = []
    for item in payload.get("output", ()):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content", ()):
            if not isinstance(part, dict):
                continue
            if part.get("type") in ("output_text", "text"):
                value = part.get("text")
                if isinstance(value, str) and value.strip():
                    chunks.append(value.strip())
    return "\n".join(chunks)


def _extract_source_urls(payload: dict[str, Any]) -> tuple[str, ...]:
    urls: list[str] = []
    for item in payload.get("output", ()):
        if not isinstance(item, dict):
            continue
        for part in item.get("content", ()):
            if not isinstance(part, dict):
                continue
            for annotation in part.get("annotations", ()):
                if not isinstance(annotation, dict):
                    continue
                if annotation.get("type") == "url_citation":
                    url = annotation.get("url")
                    if isinstance(url, str) and url.startswith("https://") and url not in urls:
                        urls.append(url)
    return tuple(urls)


def run_grok_research(
    prompt: str,
    *,
    api_key: str | None = None,
    model: str = _DEFAULT_MODEL,
    timeout: float = 45.0,
) -> GrokResearchReport:
    """Run an explicitly requested, billed research task using xAI Responses API.

    Supply the key through XAI_API_KEY in the runtime environment. The key is
    never written to disk, returned, or included in errors. The model receives
    only the user's research prompt and two built-in read/search tools.
    """
    clean_prompt = str(prompt).strip()
    if not clean_prompt:
        raise ValueError("prompt must not be empty")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    key = api_key or os.environ.get("XAI_API_KEY")
    if not key:
        raise RuntimeError("XAI_API_KEY is not configured in the runtime environment")
    if not model or not isinstance(model, str):
        raise ValueError("model must be a non-empty string")

    body = {
        "model": model,
        "input": [{"role": "user", "content": clean_prompt}],
        "tools": [{"type": "web_search"}, {"type": "x_search"}],
    }
    request = Request(
        _API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "Project60-ResearchAgent/1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"xAI research request failed with HTTP {exc.code}") from None
    except URLError as exc:
        raise RuntimeError(f"xAI research connection failed: {type(exc.reason).__name__}") from None
    except TimeoutError:
        raise RuntimeError("xAI research request timed out") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("xAI research response was not valid JSON") from None

    if not isinstance(payload, dict):
        raise RuntimeError("xAI research response had an invalid shape")
    text = _extract_text(payload)
    if not text:
        raise RuntimeError("xAI research response contained no text output")
    return GrokResearchReport(
        model=str(payload.get("model") or model),
        text=text,
        request_id=payload.get("id") if isinstance(payload.get("id"), str) else None,
        source_urls=_extract_source_urls(payload),
        usage=payload.get("usage") if isinstance(payload.get("usage"), dict) else None,
    )
