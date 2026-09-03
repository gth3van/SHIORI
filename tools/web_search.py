"""
tools/web_search.py
───────────────────
Web search tool for SHIORI — Phase 3.

Provider strategy:
  PRIMARY  → Tavily AI Search  (fast, AI-optimised, free tier 1000 req/mo)
  FALLBACK → SearXNG           (self-hosted Docker, unlimited, private)

Setup:
  1. Tavily API key → https://app.tavily.com  (free account)
     Set env var:  TAVILY_API_KEY=tvly-xxxxx
     Or put it in a .env file at project root.

  2. SearXNG (optional fallback) → run locally with Docker:
       docker run -d -p 8080:8080 searxng/searxng
     Set env var:  SEARXNG_URL=http://localhost:8080  (default)

Dependencies:
    pip install tavily-python python-dotenv httpx
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Load .env from project root (parent of tools/)
try:
    from dotenv import load_dotenv
    _PROJECT_ROOT = Path(__file__).parent.parent
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    pass  # python-dotenv optional — env vars can be set manually

import httpx

try:
    from tavily import TavilyClient
    _TAVILY_AVAILABLE = True
except ImportError:
    _TAVILY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_TAVILY_API_KEY: Optional[str] = os.getenv("TAVILY_API_KEY")
_SEARXNG_URL: str = os.getenv("SEARXNG_URL", "http://localhost:8080")
_DEFAULT_MAX_RESULTS: int = 3


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    snippet: str
    source: str   # "tavily" or "searxng"

    def to_context_string(self) -> str:
        """Format for injection into LLM prompt."""
        return f"[{self.title}]\n{self.snippet}\nSource: {self.url}"


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

def _search_tavily(query: str, max_results: int) -> list[SearchResult]:
    """Search via Tavily AI Search API."""
    if not _TAVILY_AVAILABLE:
        raise RuntimeError("tavily-python not installed. Run: pip install tavily-python")
    if not _TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY not set. Get one free at https://app.tavily.com")

    client = TavilyClient(api_key=_TAVILY_API_KEY)
    response = client.search(
        query=query,
        max_results=max_results,
        search_depth="basic",        # "basic" (fast) or "advanced" (deeper)
        include_answer=True,         # Tavily also returns a direct AI answer
    )

    results: list[SearchResult] = []

    # Tavily direct answer (most useful for SHIORI)
    if response.get("answer"):
        results.append(SearchResult(
            title="Direct Answer",
            url="",
            snippet=response["answer"],
            source="tavily",
        ))

    for r in response.get("results", [])[:max_results]:
        results.append(SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("content", ""),
            source="tavily",
        ))

    return results


def _search_searxng(query: str, max_results: int) -> list[SearchResult]:
    """Search via local SearXNG instance."""
    params = {
        "q": query,
        "format": "json",
        "categories": "general",
        "language": "auto",
    }
    try:
        response = httpx.get(
            f"{_SEARXNG_URL}/search",
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.ConnectError:
        raise RuntimeError(
            f"SearXNG not reachable at {_SEARXNG_URL}. "
            "Start it with: docker run -d -p 8080:8080 searxng/searxng"
        )

    results: list[SearchResult] = []
    for r in data.get("results", [])[:max_results]:
        results.append(SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("content", ""),
            source="searxng",
        ))
    return results


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def search(
    query: str,
    max_results: int = _DEFAULT_MAX_RESULTS,
    force_provider: Optional[str] = None,   # "tavily" | "searxng" | None (auto)
) -> list[SearchResult]:
    """Search the web and return a list of SearchResult objects.

    Tries Tavily first (if API key is set), falls back to SearXNG automatically.

    Parameters
    ----------
    query:
        The search query string.
    max_results:
        Maximum number of results to return (default: 3).
    force_provider:
        Force a specific provider. ``None`` = auto (Tavily → SearXNG fallback).

    Returns
    -------
    list[SearchResult]
        List of results. May be empty if both providers fail.
    """
    providers_tried: list[str] = []

    def _try_tavily() -> list[SearchResult]:
        providers_tried.append("tavily")
        print(f"[WebSearch] Searching via Tavily: '{query}'", flush=True)
        return _search_tavily(query, max_results)

    def _try_searxng() -> list[SearchResult]:
        providers_tried.append("searxng")
        print(f"[WebSearch] Searching via SearXNG: '{query}'", flush=True)
        return _search_searxng(query, max_results)

    if force_provider == "tavily":
        return _try_tavily()
    if force_provider == "searxng":
        return _try_searxng()

    # Auto: Tavily primary → SearXNG fallback
    if _TAVILY_API_KEY and _TAVILY_AVAILABLE:
        try:
            return _try_tavily()
        except Exception as e:
            print(f"[WebSearch] Tavily failed ({e}), falling back to SearXNG…")

    try:
        return _try_searxng()
    except Exception as e:
        print(f"[WebSearch] SearXNG also failed: {e}")
        return []


def search_to_context(query: str, max_results: int = _DEFAULT_MAX_RESULTS) -> str:
    """Search and return results formatted as a context string for the LLM.

    Returns an empty string if no results found.

    Example output::

        [Web Search Results for: "weather Jakarta today"]
        [Direct Answer]
        Partly cloudy, 31°C in Jakarta today.
        Source:

        [Cuaca Jakarta Hari Ini]
        Suhu di Jakarta hari ini ...
        Source: https://...
    """
    results = search(query, max_results)
    if not results:
        return ""

    lines = [f'[Web Search Results for: "{query}"]']
    for r in results:
        lines.append(r.to_context_string())
        lines.append("")

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "weather in Jakarta today"
    print(f"\nSearching: '{query}'\n" + "-" * 50)

    results = search(query)
    if not results:
        print("No results found. Check your API key or SearXNG connection.")
    else:
        for r in results:
            print(f"\n[{r.source.upper()}] {r.title}")
            print(f"  {r.snippet[:200]}...")
            if r.url:
                print(f"  -> {r.url}")
