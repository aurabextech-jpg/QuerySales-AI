"""Google dork search tool — advanced-operator web search for lead discovery.

Runs queries against the Google Custom Search JSON API ("dorks" only in the
sense of `site:` / `intitle:` / `inurl:` operators) and returns the public
search-result metadata Google already publishes: title, link, snippet. It reads
Google's index, never the target sites themselves, so it surfaces only
information those sites chose to have indexed.

Complements Google Places: Places answers "which businesses exist here",
dork search answers "which pages mention this role, product or technology".
"""

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
# The Custom Search API caps `num` at 10 per request; asking for more is a 400.
MAX_PER_REQUEST = 10


class DorkSearchInput(BaseModel):
    """One search query, written with Google's advanced operators."""

    query: str = Field(
        ...,
        description=(
            "Google query, operators allowed: site:, -site:, intitle:, inurl:, "
            'filetype:, OR, and "quoted phrases". '
            'Example: site:linkedin.com/in "procurement manager" "Karachi"'
        ),
    )
    max_results: int = Field(
        10, ge=1, le=10, description="Results to return (Google caps one request at 10)"
    )


def _dork_creds(creds: Any = None) -> tuple[str, str]:
    """The caller's own key and search engine id. No environment fallback."""
    if creds is None:
        return "", ""
    return creds.get("api_key"), creds.get("cx")


def _unconfigured() -> dict[str, Any]:
    return {
        "status": "error",
        "reason": "not_configured",
        "message": (
            "Google Dork Search is not configured. Add a Custom Search API key "
            "and search engine ID in Settings -> Integrations."
        ),
    }


async def ping_dork_search(creds: Any = None) -> dict[str, Any]:
    """Verify the key and cx with one cheap query. Used by the settings test."""
    api_key, cx = _dork_creds(creds)
    if not api_key or not cx:
        return {"success": False, "message": "Google Dork Search is not configured."}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                SEARCH_URL,
                params={"key": api_key, "cx": cx, "q": "test", "num": 1},
                timeout=10.0,
            )
        if response.status_code in (401, 403):
            return {
                "success": False,
                "message": "Google rejected the key — check that the Custom Search API is enabled.",
            }
        if response.status_code == 400:
            return {"success": False, "message": "Google rejected the request — check the search engine ID (cx)."}
        response.raise_for_status()
        return {"success": True, "message": "Connected to Google Custom Search."}
    except httpx.HTTPStatusError as exc:
        return {"success": False, "message": f"Google returned HTTP {exc.response.status_code}."}
    except Exception as exc:
        return {"success": False, "message": f"Connection failed: {type(exc).__name__}"}


async def dork_search(input_data: DorkSearchInput, creds: Any = None) -> dict[str, Any]:
    """Run one dork query and return the public result metadata."""
    api_key, cx = _dork_creds(creds)
    if not api_key or not cx:
        return _unconfigured()

    params = {
        "key": api_key,
        "cx": cx,
        "q": input_data.query,
        "num": min(input_data.max_results, MAX_PER_REQUEST),
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(SEARCH_URL, params=params, timeout=15.0)
            if response.status_code == 429:
                return {
                    "status": "error",
                    "reason": "quota_exceeded",
                    "message": "Google Custom Search daily quota exhausted. Try again tomorrow.",
                }
            response.raise_for_status()
            data = response.json()

            results = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "domain": item.get("displayLink", ""),
                    "snippet": item.get("snippet", ""),
                }
                for item in data.get("items", [])
            ]

            return {
                "status": "success",
                "query": input_data.query,
                "total_results": len(results),
                # What Google claims exists overall — useful for judging whether
                # the query is too narrow or far too broad.
                "estimated_total_matches": data.get("searchInformation", {}).get(
                    "totalResults"
                ),
                "results": results,
            }
        except httpx.HTTPStatusError as exc:
            # The body echoes the API key back in some error shapes — log the
            # status only (rule §3.3: never log a credential).
            logger.error("Custom Search HTTP %s for a dork query", exc.response.status_code)
            return {
                "status": "error",
                "message": f"Google returned HTTP {exc.response.status_code}.",
            }
        except Exception as exc:
            logger.error("Custom Search failed: %s", type(exc).__name__)
            return {"status": "error", "message": f"Search failed: {type(exc).__name__}"}
