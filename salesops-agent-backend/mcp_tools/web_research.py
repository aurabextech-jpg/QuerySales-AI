"""Web research tools — search the web, read a page, enrich a company.

Three tools for the lead-generation agent, each returning *compact structured
fields* rather than page text. A raw homepage is 20-60k tokens; the profile this
module returns for the same page is ~150. That is the whole point: the agent
reasons over contacts, ratings and listings, never over HTML.

  web_search        — public web search. Uses the caller's own Google Custom
                      Search key when configured, otherwise DuckDuckGo's
                      keyless HTML endpoint (no credential, so rule §3.4 holds).
  scrape_page       — one URL → title, contacts, schema.org organisation data,
                      directory listings, filters and pagination.
  research_companies — for each company: find its official site, read the
                      homepage (+ contact page when needed), score the result.

Deliberately not a crawler: at most two pages per company, never recursive.
HTML is handled with regex, not a parser — the lambda has a 50 MB budget and no
HTML library (see pyproject.toml), same trade-off as lead_sources.py.
"""

from __future__ import annotations

import asyncio
import html as html_lib
import ipaddress
import json
import logging
import re
import socket
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Limits ─────────────────────────────────────────────────────────────────
FETCH_TIMEOUT = 10.0
# httpx timeouts are per network operation, so a server that trickles bytes can
# hold a fetch open indefinitely. These are hard wall-clock caps.
FETCH_DEADLINE = 15.0
COMPANY_DEADLINE = 40.0
MAX_PAGE_BYTES = 600_000
MAX_REDIRECTS = 4
MAX_COMPANIES = 8
# Parallel fetches per call — enough to finish 8 companies inside one serverless
# request without hammering any single site.
CONCURRENCY = 4
# A one-line pitch is enough to judge fit; the full blurb cost ~75 tokens per company.
DESCRIPTION_CHARS = 160
SNIPPET_CHARS = 220
MAX_LISTINGS = 30
MAX_EXTERNAL = 15
MAX_CONTACTS = 5
TEXT_EXCERPT_CHARS = 1500

# Opportunity score weights — published in every result as `score_breakdown`
# so the agent (and the user) can see exactly why a lead scored what it did.
SCORE_WEIGHTS = {
    "website": 15,
    "email": 20,
    "phone": 20,
    "address": 10,
    "social": 5,
    "description": 5,
}
# Networks a B2B seller acts on, in order; at most this many are returned.
PREFERRED_SOCIAL = ("linkedin", "facebook")
HIGH_TIER = 70
MEDIUM_TIER = 40

DDG_URL = "https://html.duckduckgo.com/html/"
GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
# A browser UA: several directories and DuckDuckGo serve an empty shell to
# obvious bots, which is indistinguishable from "no data" to the agent.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Aggregators, directories and social networks: useful as *evidence*, never as
# a company's official website.
_NON_OFFICIAL_DOMAINS = (
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "wikipedia.org", "google.com", "duckduckgo.com",
    "yelp.com", "yellowpages", "justdial", "pakbd.com", "b2bpakistan.com",
    "businessportal.pk", "zaubee", "dnb.com", "crunchbase.com", "glassdoor",
    "indeed.com", "rozee.pk", "olx", "daraz", "tradeindia", "indiamart",
    "alibaba.com", "made-in-china", "kompass", "opencorporates", "bloomberg.com",
    # Lead-list sellers and listicle hosts — their lists are paywalled or JS-only.
    "f6s.com", "aeroleads", "rentechdigital", "scribd.com", "businesslist",
    "pakistani.pk", "placedigger", "zoominfo", "rocketreach", "apollo.io",
)
_SOCIAL = {
    "linkedin": "linkedin.com",
    "facebook": "facebook.com",
    "instagram": "instagram.com",
    "twitter": ("twitter.com", "x.com"),
    "youtube": "youtube.com",
}
_NAV_WORDS = {
    "home", "login", "log in", "sign up", "signup", "register", "about", "about us",
    "contact", "contact us", "blog", "blogs", "privacy", "terms", "faq", "help",
    "next", "previous", "prev", "more", "read more", "view all", "menu", "search",
}

# ── Regexes ────────────────────────────────────────────────────────────────
_SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_LINK_RE = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_META_RE = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*["\']([^"\']*)["\']')
_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S
)
_SELECT_RE = re.compile(r'<select\b[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', re.I | re.S)
_OPTION_RE = re.compile(r'<option\b[^>]*value=["\']([^"\']*)["\']', re.I)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
# Phone numbers: international (+92 …) or local trunk (0…) forms, 9-15 digits.
_PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?\(?\d{2,5}\)?(?:[\s.-]?\d{2,8}){1,4}")
_RATING_RE = re.compile(
    r"(\d(?:\.\d)?)\s*(?:/\s*5|out of 5|stars?|★)"
    r"(?:[^\d]{0,30}?(\d[\d,]*)\s*(?:reviews?|ratings?|votes?))?",
    re.I,
)
_ASSET_EMAIL_RE = re.compile(r"\.(png|jpe?g|gif|svg|webp|css|js)$", re.I)


# ── Input models ───────────────────────────────────────────────────────────


class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query")
    max_results: int = Field(8, ge=1, le=10)


class ScrapePageInput(BaseModel):
    url: str = Field(..., description="Absolute http(s) URL to read")
    include_text: bool = Field(
        False, description="Also return a short visible-text excerpt (costs tokens)"
    )


class CompanyRef(BaseModel):
    name: str
    website: str | None = None
    profile_url: str | None = Field(
        None, description="A directory/listing page about the company, if known"
    )


class ResearchCompaniesInput(BaseModel):
    companies: list[CompanyRef] = Field(..., min_length=1)
    city: str = ""


# ── SSRF guard ─────────────────────────────────────────────────────────────
# The LLM chooses these URLs, and a model can be steered by page content. On a
# cloud lambda an unchecked fetch could reach the metadata service or a private
# network, so every hop (including redirects) must resolve to a public address.


class UnsafeUrl(Exception):
    pass


async def _assert_public(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeUrl("only absolute http(s) URLs are allowed")
    host = parsed.hostname
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeUrl(f"host does not resolve: {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise UnsafeUrl("URL resolves to a non-public address")


async def _fetch(client: httpx.AsyncClient, url: str) -> tuple[str, str, str | None]:
    """Return (final_url, html, error). Never raises — one dead site must not fail a batch."""
    try:
        return await asyncio.wait_for(_fetch_inner(client, url), FETCH_DEADLINE)
    except asyncio.TimeoutError:
        return url, "", "timed out"


async def _fetch_inner(client: httpx.AsyncClient, url: str) -> tuple[str, str, str | None]:
    current = url
    try:
        for _ in range(MAX_REDIRECTS + 1):
            await _assert_public(current)
            async with client.stream(
                "GET", current, headers={"User-Agent": _USER_AGENT}, timeout=FETCH_TIMEOUT
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    current = str(httpx.URL(current).join(location))
                    continue
                if response.status_code >= 400:
                    return current, "", f"HTTP {response.status_code}"
                content_type = response.headers.get("content-type", "")
                if "html" not in content_type and "xml" not in content_type:
                    return current, "", f"not an HTML page ({content_type or 'unknown type'})"
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) >= MAX_PAGE_BYTES:
                        break
                return current, body.decode(response.encoding or "utf-8", errors="replace"), None
        return current, "", "too many redirects"
    except UnsafeUrl as exc:
        return current, "", str(exc)
    except httpx.TimeoutException:
        return current, "", "timed out"
    except httpx.ConnectError as exc:
        # Certificate checks stay on: a site with a broken chain is reported,
        # never fetched insecurely.
        if "CERTIFICATE" in str(exc):
            return current, "", "site's TLS certificate could not be verified"
        return current, "", "connection failed"
    except Exception as exc:
        return current, "", type(exc).__name__


# ── Extraction helpers ─────────────────────────────────────────────────────


def _clean(fragment: str) -> str:
    return _WS_RE.sub(" ", html_lib.unescape(_TAG_RE.sub(" ", fragment))).strip()


def _visible_text(page: str) -> str:
    return _clean(_SCRIPT_STYLE_RE.sub(" ", page))


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _is_non_official(url: str) -> bool:
    domain = _domain(url)
    return any(marker in domain for marker in _NON_OFFICIAL_DOMAINS)


def _meta(page: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for tag in _META_RE.findall(page):
        attrs = {k.lower(): v for k, v in _ATTR_RE.findall(tag)}
        key = attrs.get("name") or attrs.get("property")
        if key and "content" in attrs:
            found.setdefault(key.lower(), html_lib.unescape(attrs["content"]).strip())
    return found


def _iter_jsonld(page: str):
    """Yield every dict node in the page's JSON-LD blocks (graphs flattened)."""
    for raw in _JSONLD_RE.findall(page):
        try:
            data = json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                yield node
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))


def _format_address(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        parts = [
            value.get(k) for k in
            ("streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry")
        ]
        text = ", ".join(str(p).strip() for p in parts if p and isinstance(p, (str, int)))
        return text or None
    if isinstance(value, list) and value:
        return _format_address(value[0])
    return None


def _organization(page: str) -> dict[str, Any]:
    """schema.org Organization/LocalBusiness facts — the most reliable contact source."""
    org: dict[str, Any] = {}
    for node in _iter_jsonld(page):
        node_type = node.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        is_org = any(
            isinstance(t, str) and (t in ("Organization", "Corporation", "Store")
                                    or t.endswith("Business") or "Organization" in t)
            for t in types
        )
        rating = node.get("aggregateRating")
        if isinstance(rating, dict) and "rating" not in org:
            try:
                org["rating"] = float(str(rating.get("ratingValue")))
                count = rating.get("reviewCount") or rating.get("ratingCount")
                org["review_count"] = int(str(count).replace(",", "")) if count else None
            except (TypeError, ValueError):
                pass
        if not is_org:
            continue
        for src, dst in (("name", "name"), ("telephone", "phone"), ("email", "email"),
                         ("url", "website"), ("description", "description")):
            value = node.get(src)
            if isinstance(value, str) and value.strip() and dst not in org:
                org[dst] = value.strip()
        address = _format_address(node.get("address"))
        if address and "address" not in org:
            org["address"] = address
        same_as = node.get("sameAs")
        if isinstance(same_as, list):
            org.setdefault("same_as", [s for s in same_as if isinstance(s, str)])
    if "email" in org:
        org["email"] = org["email"].removeprefix("mailto:")
    return org


def _normalise_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if not 9 <= len(digits) <= 15:
        return None
    return ("+" if raw.strip().startswith("+") else "") + digits


def _contacts(page: str, text: str) -> tuple[list[str], list[str]]:
    """Emails and phones. Explicit mailto:/tel: links win over text matches."""
    emails: list[str] = []
    phones: list[str] = []

    def add(bucket: list[str], value: str | None) -> None:
        if value and value not in bucket and len(bucket) < MAX_CONTACTS:
            bucket.append(value)

    for href, _ in _LINK_RE.findall(page):
        href = html_lib.unescape(href.strip())
        if href.lower().startswith("mailto:"):
            add(emails, unquote(href[7:].split("?")[0]).strip().lower())
        elif href.lower().startswith("tel:"):
            add(phones, _normalise_phone(unquote(href[4:])))
    for match in _EMAIL_RE.findall(text):
        if not _ASSET_EMAIL_RE.search(match):
            add(emails, match.lower())
    # Text phones are noisy (dates, prices, IDs) — only trust them near a label.
    for label in re.finditer(r"(?:phone|tel|call|mobile|whatsapp|contact)[^0-9+]{0,15}", text, re.I):
        window = text[label.end(): label.end() + 25]
        match = _PHONE_RE.match(window)
        # Real numbers are written international (+92…) or with a trunk 0;
        # anything else after a label is usually a fax extension or an ID.
        if match and window[:1] in ("+", "0", "("):
            add(phones, _normalise_phone(match.group(0)))
    return emails, phones


def _social_network(url: str) -> str | None:
    domain = _domain(url)
    for name, hosts in _SOCIAL.items():
        hosts = hosts if isinstance(hosts, tuple) else (hosts,)
        if any(domain == h or domain.endswith("." + h) for h in hosts):
            return name
    return None


def _is_social(url: str) -> bool:
    return _social_network(url) is not None


def _social_links(links: list[tuple[str, str]]) -> dict[str, str]:
    social: dict[str, str] = {}
    for href, _ in links:
        # Share buttons ("sharer.php", "intent/tweet") point at the network, not the company.
        if re.search(r"share|intent/", urlparse(href).path, re.I):
            continue
        name = _social_network(href)
        if name and name not in social:
            social[name] = href
    return social


def _rating_from_text(text: str) -> tuple[float | None, int | None]:
    for match in _RATING_RE.finditer(text):
        value = float(match.group(1))
        if 0 < value <= 5:
            count = match.group(2)
            return value, int(count.replace(",", "")) if count else None
    return None, None


def _absolute_links(page: str, base_url: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for href, inner in _LINK_RE.findall(page):
        href = html_lib.unescape(href.strip())
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        try:
            links.append((str(httpx.URL(base_url).join(href)), _clean(inner)))
        except Exception:
            continue
    return links


def _listings(links: list[tuple[str, str]], base_url: str) -> tuple[list, list, list]:
    """Split a page's links into (same-site detail pages, external sites, pagination).

    A directory's company entries are same-site links one level deeper than the
    page itself (``/business-directory/crest-led`` under ``/business-directory``);
    navigation is everything shallower or labelled like a menu item.
    """
    base = urlparse(base_url)
    base_path = base.path.rstrip("/")
    site = _domain(base_url)
    listings: list[dict[str, str]] = []
    external: list[dict[str, str]] = []
    pages: list[str] = []
    seen: set[str] = set()

    for url, label in links:
        parsed = urlparse(url)
        key = url.split("#")[0]
        if key in seen:
            continue
        seen.add(key)
        if _domain(url) == site:
            query = parse_qs(parsed.query)
            if "page" in query or "p" in query:
                pages.append(url)
                continue
            path = parsed.path.rstrip("/")
            deeper = base_path and path.startswith(base_path + "/") and path != base_path
            if deeper and label.lower() not in _NAV_WORDS and len(listings) < MAX_LISTINGS:
                listings.append({"label": label[:80] or path.rsplit("/", 1)[-1], "url": url})
        elif not _is_social(url) and len(external) < MAX_EXTERNAL:
            external.append({"label": label[:80], "url": url})
    return listings, external, sorted(set(pages))[:10]


def directory_structure(page: str, url: str) -> dict[str, Any]:
    """A directory page's company entries, filters and pagination — shared with lead_sources."""
    listings, _, pagination = _listings(_absolute_links(page, url), url)
    return _public({"listings": listings, "filters": _filters(page), "pagination": pagination})


def _filters(page: str) -> dict[str, list[str]]:
    """GET-form <select> options — lets the agent build a filtered directory URL."""
    filters: dict[str, list[str]] = {}
    for name, body in _SELECT_RE.findall(page)[:6]:
        options = [v for v in _OPTION_RE.findall(body) if v and v.lower() != "all"]
        if options:
            filters[name] = options[:20]
    return filters


def _contact_page(links: list[tuple[str, str]], base_url: str) -> str | None:
    site = _domain(base_url)
    for url, label in links:
        if _domain(url) != site:
            continue
        haystack = (urlparse(url).path + " " + label).lower()
        if "contact" in haystack or "get in touch" in haystack:
            return url
    return None


def _extract(page: str, url: str) -> dict[str, Any]:
    """Everything useful from one page, nothing else."""
    text = _visible_text(page)
    meta = _meta(page)
    links = _absolute_links(page, url)
    org = _organization(page)
    emails, phones = _contacts(page, text)
    if org.get("email"):
        emails = [org["email"].lower()] + [e for e in emails if e != org["email"].lower()]
    if org.get("phone"):
        phone = _normalise_phone(org["phone"])
        phones = ([phone] if phone else []) + [p for p in phones if p != phone]
    rating, reviews = org.get("rating"), org.get("review_count")
    if rating is None:
        rating, reviews = _rating_from_text(text)
    title_match = _TITLE_RE.search(page)
    title = _clean(title_match.group(1)) if title_match else ""
    description = org.get("description") or meta.get("description") or meta.get("og:description") or ""
    return {
        "url": url,
        "title": title[:120],
        "name": org.get("name") or meta.get("og:site_name"),
        "description": _clean(description)[:DESCRIPTION_CHARS] or None,
        "emails": emails[:MAX_CONTACTS],
        "phones": phones[:MAX_CONTACTS],
        "address": org.get("address"),
        "website": org.get("website"),
        "rating": rating,
        "review_count": reviews,
        "social": _social_links(links),
        "contact_page": _contact_page(links, url),
        "_links": links,
        "_text": text,
    }


def _public(result: dict[str, Any]) -> dict[str, Any]:
    """Drop internal keys and empty values — every null is a wasted token."""
    return {
        k: v for k, v in result.items()
        if not k.startswith("_") and v not in (None, "", [], {})
    }


# ── Search ─────────────────────────────────────────────────────────────────


def _ddg_target(href: str) -> str:
    """DuckDuckGo sometimes wraps results in a /l/?uddg= redirect."""
    href = html_lib.unescape(href)
    if "duckduckgo.com/l/" in href:
        target = parse_qs(urlparse(href if href.startswith("http") else "https:" + href).query)
        return target.get("uddg", [href])[0]
    return href


class SearchBlocked(Exception):
    """The keyless engine served a bot challenge instead of results."""


SEARCH_BLOCKED_MESSAGE = (
    "The free web search is temporarily blocking automated queries. For reliable "
    "lead discovery add a Google Custom Search key (free: 100 queries/day) in "
    "Settings -> Integrations -> Google Dork Search, or configure Google Places."
)


async def _search_ddg(client: httpx.AsyncClient, query: str, limit: int) -> list[dict[str, str]]:
    response = await client.post(
        DDG_URL, data={"q": query}, headers={"User-Agent": _USER_AGENT}, timeout=FETCH_TIMEOUT
    )
    response.raise_for_status()
    # A burst of queries gets HTTP 202 + an "anomaly" challenge page. Treating
    # that as "no results" would make the agent report "no companies exist".
    if response.status_code == 202 or "anomaly" in response.text[:20000]:
        raise SearchBlocked(SEARCH_BLOCKED_MESSAGE)
    results: list[dict[str, str]] = []
    blocks = re.split(r'<div[^>]+class="[^"]*\bresult\b', response.text)[1:]
    for block in blocks:
        if "result--ad" in block[:200]:
            continue
        link = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not link:
            continue
        snippet = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, re.S)
        url = _ddg_target(link.group(1))
        results.append({
            "title": _clean(link.group(2))[:120],
            "url": url,
            "domain": _domain(url),
            "snippet": _clean(snippet.group(1))[:SNIPPET_CHARS] if snippet else "",
        })
        if len(results) >= limit:
            break
    return results


async def _search_google(
    client: httpx.AsyncClient, query: str, limit: int, api_key: str, cx: str
) -> list[dict[str, str]]:
    response = await client.get(
        GOOGLE_CSE_URL,
        params={"key": api_key, "cx": cx, "q": query, "num": min(limit, 10)},
        timeout=FETCH_TIMEOUT,
    )
    response.raise_for_status()
    return [
        {
            "title": item.get("title", "")[:120],
            "url": item.get("link", ""),
            "domain": _domain(item.get("link", "")),
            "snippet": item.get("snippet", "")[:SNIPPET_CHARS],
        }
        for item in response.json().get("items", [])
    ]


async def _search(
    client: httpx.AsyncClient, query: str, limit: int, dork_creds: Any = None
) -> tuple[list[dict[str, str]], str]:
    """Search with the user's Google key when they have one, else keyless DuckDuckGo."""
    api_key = dork_creds.get("api_key") if dork_creds else ""
    cx = dork_creds.get("cx") if dork_creds else ""
    if api_key and cx:
        try:
            return await _search_google(client, query, limit, api_key, cx), "google"
        except httpx.HTTPStatusError as exc:
            # Quota or key problems fall through to DuckDuckGo instead of failing
            # the research. Status only — the error body can echo the key.
            logger.warning("Google CSE HTTP %s; falling back to DuckDuckGo", exc.response.status_code)
    return await _search_ddg(client, query, limit), "duckduckgo"


async def web_search(input_data: WebSearchInput, dork_creds: Any = None) -> dict[str, Any]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            results, engine = await asyncio.wait_for(
                _search(client, input_data.query, input_data.max_results, dork_creds),
                FETCH_DEADLINE,
            )
        except SearchBlocked:
            return {"status": "error", "reason": "search_blocked", "message": SEARCH_BLOCKED_MESSAGE}
        except Exception as exc:
            logger.warning("web_search failed: %s", type(exc).__name__)
            return {
                "status": "error",
                "reason": "search_unavailable",
                "message": f"Web search failed ({type(exc).__name__}). Try again shortly.",
            }
    return {"status": "success", "engine": engine, "query": input_data.query, "results": results}


# ── Scrape ─────────────────────────────────────────────────────────────────


async def scrape_page(input_data: ScrapePageInput) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        final_url, page, error = await _fetch(client, input_data.url)
    if error:
        return {"status": "error", "url": input_data.url, "message": f"Could not read page: {error}"}

    data = _extract(page, final_url)
    listings, external, pagination = _listings(data["_links"], final_url)
    result = _public(data)
    result.update(_public({
        "listings": listings,
        "external_sites": external,
        "pagination": pagination,
        "filters": _filters(page),
    }))
    if input_data.include_text:
        result["text_excerpt"] = data["_text"][:TEXT_EXCERPT_CHARS]
    result["status"] = "success"
    return result


# ── Company research ───────────────────────────────────────────────────────


def _name_tokens(name: str) -> list[str]:
    stop = {"private", "limited", "pvt", "ltd", "the", "and", "company", "co", "inc", "llc", "group"}
    return [t for t in re.findall(r"[a-z0-9]+", name.lower()) if len(t) > 2 and t not in stop]


def _pick_official(results: list[dict[str, str]], name: str) -> str | None:
    """Prefer a non-directory result whose domain contains a word of the company name."""
    tokens = _name_tokens(name)
    candidates = [r for r in results if r["url"].startswith("http") and not _is_non_official(r["url"])]
    for r in candidates:
        compact = r["domain"].replace("-", "")
        if any(t in compact for t in tokens):
            return f"{urlparse(r['url']).scheme}://{urlparse(r['url']).netloc}/"
    return None


def _score(profile: dict[str, Any]) -> tuple[int, dict[str, int], str]:
    breakdown: dict[str, int] = {}
    if profile.get("website"):
        breakdown["website"] = SCORE_WEIGHTS["website"]
    if profile.get("emails"):
        breakdown["email"] = SCORE_WEIGHTS["email"]
    if profile.get("phones"):
        breakdown["phone"] = SCORE_WEIGHTS["phone"]
    if profile.get("address"):
        breakdown["address"] = SCORE_WEIGHTS["address"]
    if profile.get("social"):
        breakdown["social"] = SCORE_WEIGHTS["social"]
    if profile.get("description"):
        breakdown["description"] = SCORE_WEIGHTS["description"]
    rating, reviews = profile.get("rating"), profile.get("review_count") or 0
    if rating is not None:
        breakdown["rating"] = 15 if rating >= 4.0 else 8 if rating >= 3.5 else 0
    if reviews:
        breakdown["reviews"] = 10 if reviews >= 50 else 5 if reviews >= 10 else 0
    total = min(100, sum(breakdown.values()))
    tier = "High" if total >= HIGH_TIER else "Medium" if total >= MEDIUM_TIER else "Low"
    return total, {k: v for k, v in breakdown.items() if v}, tier


def _merge(profile: dict[str, Any], page: dict[str, Any]) -> None:
    for key in ("emails", "phones"):
        for value in page.get(key, []):
            if value not in profile[key] and len(profile[key]) < MAX_CONTACTS:
                profile[key].append(value)
    for key in ("address", "description", "rating", "review_count"):
        if profile.get(key) is None and page.get(key) is not None:
            profile[key] = page[key]
    for name, url in page.get("social", {}).items():
        profile["social"].setdefault(name, url)


async def _research_one(
    client: httpx.AsyncClient,
    gate: asyncio.Semaphore,
    company: CompanyRef,
    city: str,
    dork_creds: Any,
) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "name": company.name, "website": company.website, "emails": [], "phones": [],
        "address": None, "rating": None, "review_count": None, "description": None,
        "social": {}, "sources": [], "notes": [],
    }
    search_results: list[dict[str, str]] = []

    async with gate:
        # A directory profile often carries the cleanest contact record (JSON-LD).
        if company.profile_url:
            url, page, error = await _fetch(client, company.profile_url)
            if not error:
                data = _extract(page, url)
                # The directory's own footer email and social links are not the
                # company's — keep only contacts that don't belong to the host.
                host = _domain(url)
                data["emails"] = [e for e in data["emails"] if not e.endswith("@" + host)]
                data["social"] = {}
                _merge(profile, data)
                profile["sources"].append(url)
                if not profile["website"]:
                    # The profile usually links the company's own site.
                    _, external, _ = _listings(data["_links"], url)
                    official = [e["url"] for e in external if not _is_non_official(e["url"])]
                    if data.get("website") and not _is_non_official(data["website"]):
                        profile["website"] = data["website"]
                    elif official:
                        profile["website"] = official[0]

        if not profile["website"]:
            # Plain "name city" finds the official site far more often than a
            # quoted phrase; the second query catches companies with a generic name.
            for query in (f"{company.name} {city}", f"{company.name} official website"):
                try:
                    results, _ = await _search(client, query.strip(), 8, dork_creds)
                except SearchBlocked:
                    profile["notes"].append("web search blocked; pass a website to research this company")
                    break
                except Exception as exc:
                    profile["notes"].append(f"search failed ({type(exc).__name__})")
                    break
                search_results.extend(results)
                profile["website"] = _pick_official(results, company.name)
                if profile["website"]:
                    break

        if profile["website"]:
            url, page, error = await _fetch(client, profile["website"])
            if error:
                profile["notes"].append(f"website unreadable: {error}")
            else:
                home = _extract(page, url)
                _merge(profile, home)
                profile["sources"].append(url)
                # One extra hop, only when the homepage lacked a way to reach them.
                contact_url = home.get("contact_page")
                if contact_url and (not profile["emails"] or not profile["phones"]):
                    c_url, c_page, c_error = await _fetch(client, contact_url)
                    if not c_error:
                        _merge(profile, _extract(c_page, c_url))
                        profile["sources"].append(c_url)
        else:
            profile["notes"].append("no official website found")

    # Ratings mostly live in search snippets (Google/Facebook review widgets).
    if profile["rating"] is None:
        for r in search_results:
            rating, reviews = _rating_from_text(r["snippet"])
            if rating is not None:
                profile["rating"], profile["review_count"] = rating, reviews
                profile["sources"].append(r["url"])
                break
    if city and profile.get("address"):
        profile["city_match"] = city.lower() in profile["address"].lower()
    other = [r["url"] for r in search_results if _is_non_official(r["url"])][:2]
    if other:
        profile["other_listings"] = other

    score, breakdown, tier = _score(profile)
    profile.update({"score": score, "tier": tier, "score_breakdown": breakdown})
    # Scoring used everything found; the agent only needs enough to cite and act.
    profile["sources"] = profile["sources"][:2]
    profile["social"] = {
        k: profile["social"][k] for k in PREFERRED_SOCIAL if k in profile["social"]
    }
    return _public(profile)


async def research_companies(
    input_data: ResearchCompaniesInput, dork_creds: Any = None
) -> dict[str, Any]:
    companies = input_data.companies[:MAX_COMPANIES]
    gate = asyncio.Semaphore(CONCURRENCY)
    async def bounded(company: CompanyRef) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                _research_one(client, gate, company, input_data.city, dork_creds),
                COMPANY_DEADLINE,
            )
        except asyncio.TimeoutError:
            return {"name": company.name, "notes": ["research timed out"], "score": 0, "tier": "Low"}

    async with httpx.AsyncClient() as client:
        profiles = await asyncio.gather(*(bounded(c) for c in companies))
    profiles = sorted(profiles, key=lambda p: p.get("score", 0), reverse=True)
    result: dict[str, Any] = {
        "status": "success",
        "researched": len(profiles),
        "scoring": "contact completeness + reputation; see score_breakdown. Adjust for fit.",
        "companies": profiles,
    }
    if len(input_data.companies) > MAX_COMPANIES:
        result["skipped"] = [c.name for c in input_data.companies[MAX_COMPANIES:]]
    return result
