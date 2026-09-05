"""Lead source sites tool — searches the user's own list of public pages.

The user curates a list of source URLs in Settings -> Integrations (directories,
chamber-of-commerce member lists, exhibitor lists, industry news). This tool
fetches those pages and returns the passages, links and contact details that
match the agent's query, so lead discovery is not limited to Google Places.

Deliberately not a crawler: it fetches exactly the pages the user listed, never
follows links, and holds nothing between runs. HTML is reduced to text with
regex rather than a parser — the lambda has a 50 MB budget and no HTML library
(see pyproject.toml).
"""

import asyncio
import logging
import re
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# One page per configured URL, fetched once per call — a cap keeps a long list
# from blowing the serverless request budget.
MAX_SITES = 10
MAX_PAGE_BYTES = 400_000
FETCH_TIMEOUT = 12.0
# Enough context around a hit for the agent to judge the lead without shipping
# the whole page into its context window.
SNIPPET_RADIUS = 200

_USER_AGENT = "QuerySalesAI/1.0 (+lead source search; configured by the site owner's customer)"

_SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?){2,4}\d{2,4}")
_LINK_RE = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)


class SearchSourceSitesInput(BaseModel):
    """Query the user's configured lead source pages."""

    query: str = Field(
        ...,
        description="What to look for, e.g. 'textile exporters Faisalabad' or 'CFO'",
    )
    max_results_per_site: int = Field(
        5, ge=1, le=20, description="Max matching passages to return per source page"
    )


def _source_urls(creds: Any = None) -> list[str]:
    """The caller's configured source URLs, one per line. No shared default."""
    if creds is None:
        return []
    raw = creds.get("site_urls", "")
    urls = [line.strip() for line in raw.splitlines() if line.strip()]
    return [u for u in urls if u.startswith(("http://", "https://"))][:MAX_SITES]


def _unconfigured() -> dict[str, Any]:
    return {
        "status": "error",
        "reason": "not_configured",
        "message": (
            "No lead source sites configured. Add page URLs in "
            "Settings -> Integrations -> Lead Source Sites."
        ),
    }


def _visible_text(html: str) -> str:
    """Strip scripts, tags and repeated whitespace down to readable text."""
    without_code = _SCRIPT_STYLE_RE.sub(" ", html)
    return _WHITESPACE_RE.sub(" ", _TAG_RE.sub(" ", without_code)).strip()


def _keywords(query: str) -> list[str]:
    """Query terms worth matching on — short filler words only add noise."""
    return [w for w in re.findall(r"[\w&.-]+", query.lower()) if len(w) > 2]


def _match_snippets(text: str, keywords: list[str], limit: int) -> list[str]:
    """Passages around each keyword hit, deduplicated by overlap."""
    lowered = text.lower()
    snippets: list[str] = []
    taken: list[tuple[int, int]] = []

    for keyword in keywords:
        for match in re.finditer(re.escape(keyword), lowered):
            start = max(0, match.start() - SNIPPET_RADIUS)
            end = min(len(text), match.end() + SNIPPET_RADIUS)
            if any(start < t_end and t_start < end for t_start, t_end in taken):
                continue
            taken.append((start, end))
            snippets.append(text[start:end].strip())
            if len(snippets) >= limit:
                return snippets
    return snippets


def _matching_links(html: str, base_url: str, keywords: list[str], limit: int) -> list[dict[str, str]]:
    """Links whose anchor text hits a keyword — usually the lead's own page."""
    links: list[dict[str, str]] = []
    seen: set[str] = set()

    for href, inner in _LINK_RE.findall(html):
        label = _WHITESPACE_RE.sub(" ", _TAG_RE.sub(" ", inner)).strip()
        if not label or href.startswith(("#", "javascript:", "mailto:")):
            continue
        if not any(k in label.lower() for k in keywords):
            continue
        url = httpx.URL(base_url).join(href)
        if str(url) in seen:
            continue
        seen.add(str(url))
        links.append({"label": label[:120], "url": str(url)})
        if len(links) >= limit:
            break
    return links


async def _fetch(client: httpx.AsyncClient, url: str) -> tuple[str, str | None]:
    """Return (html, error). Never raises — one dead source must not fail the run."""
    try:
        response = await client.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text[:MAX_PAGE_BYTES], None
    except httpx.HTTPStatusError as exc:
        return "", f"HTTP {exc.response.status_code}"
    except Exception as exc:
        return "", type(exc).__name__


async def ping_lead_sources(creds: Any = None) -> dict[str, Any]:
    """Check the configured pages are reachable. Used by the settings test."""
    urls = _source_urls(creds)
    if not urls:
        return {"success": False, "message": "No lead source sites configured."}

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(_fetch(client, url) for url in urls))

    reachable = sum(1 for _, error in results if error is None)
    if reachable == 0:
        first_error = next((error for _, error in results if error), "unreachable")
        return {
            "success": False,
            "message": f"None of the {len(urls)} configured page(s) responded ({first_error}).",
        }
    return {
        "success": True,
        "message": f"{reachable} of {len(urls)} configured page(s) reachable.",
    }


async def search_source_sites(
    input_data: SearchSourceSitesInput, creds: Any = None
) -> dict[str, Any]:
    """Fetch every configured source page and return the matches for the query."""
    urls = _source_urls(creds)
    if not urls:
        return _unconfigured()

    keywords = _keywords(input_data.query)
    if not keywords:
        return {
            "status": "error",
            "message": "The query has no searchable terms — use words of 3+ characters.",
        }

    async with httpx.AsyncClient() as client:
        pages = await asyncio.gather(*(_fetch(client, url) for url in urls))

    sites: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for url, (html, error) in zip(urls, pages):
        if error:
            logger.info("Lead source %s unreachable: %s", url, error)
            errors.append({"url": url, "error": error})
            continue

        text = _visible_text(html)
        snippets = _match_snippets(text, keywords, input_data.max_results_per_site)
        if not snippets:
            continue

        matched_text = " ".join(snippets)
        sites.append({
            "source_url": url,
            "matches": snippets,
            "links": _matching_links(html, url, keywords, input_data.max_results_per_site),
            "emails": sorted(set(_EMAIL_RE.findall(matched_text)))[:10],
            "phones": sorted({
                p.strip() for p in _PHONE_RE.findall(matched_text) if len(p.strip()) >= 9
            })[:10],
        })

    return {
        "status": "success",
        "query": input_data.query,
        "sites_searched": len(urls),
        "sites_with_matches": len(sites),
        "results": sites,
        "unreachable": errors,
    }
