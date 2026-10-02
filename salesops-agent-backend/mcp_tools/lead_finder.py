"""find_leads — discovery, research and scoring in ONE tool call.

Why this exists: chaining discover → scrape → enrich through the LLM costs a
model round-trip (and the full prompt + tool schemas) per step. On a small model
with a tight tokens-per-minute budget (Groq free tier: 8k TPM) that chain hit
429s and the model re-delegated instead of finishing. Doing the chain in code
makes lead discovery one tool call and one compact result, whatever the model.

Discovery sources, in order:
  1. A URL the user gave — a directory is scraped, its own filters applied
     (?industry=…&location=…) when they match the request, and its listings used.
  2. Web search for company websites directly ("<industry> company <city> pvt ltd").
     Lead-list sellers and "Top 50" listicles are skipped: their lists are
     paywalled or rendered by JavaScript, so they never yield companies.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
from pydantic import BaseModel, Field

from mcp_tools.web_research import (
    MAX_COMPANIES,
    CompanyRef,
    ResearchCompaniesInput,
    ScrapePageInput,
    SEARCH_BLOCKED_MESSAGE,
    SearchBlocked,
    _is_non_official,
    _search,
    research_companies,
    scrape_page,
)

logger = logging.getLogger(__name__)

# DuckDuckGo returns empty pages to bursts of queries; a short gap avoids that.
QUERY_GAP_SECONDS = 1.0
_LISTICLE_RE = re.compile(r"\b(top \d+|list of|best \d*|\d+ best|directory|companies in)\b", re.I)
_TITLE_SPLIT_RE = re.compile(r"\s+[|–—:-]\s+")
_GENERIC_TITLE_PARTS = {"home", "contact us", "contact", "about us", "welcome", "official website"}
_GENERIC_PREFIX_RE = re.compile(r"^(about us|contact us|home|welcome to)\b[\s:,-]*", re.I)


class FindLeadsInput(BaseModel):
    industry: str = Field(..., description="e.g. 'manufacturing', 'plastic packaging'")
    city: str = Field(..., description="e.g. 'Karachi'")
    source_url: str | None = Field(None, description="A directory/list URL the user gave")
    max_leads: int = Field(MAX_COMPANIES, ge=1, le=MAX_COMPANIES)


def _company_name(title: str, domain: str) -> str:
    """The company's name from a page title: 'Contact Us - Indus Group' → 'Indus Group'."""
    parts = [p.strip() for p in _TITLE_SPLIT_RE.split(title) if p.strip()]
    named = [_GENERIC_PREFIX_RE.sub("", p).strip() for p in parts]
    named = [p for p in named if p and p.lower() not in _GENERIC_TITLE_PARTS]
    if named:
        return min(named, key=len) if len(named) > 1 and len(named[0]) > 60 else named[0]
    return domain.split(".")[0].replace("-", " ").title()


def _matching_option(options: list[str], wanted: str) -> str | None:
    wanted = wanted.lower().strip()
    for option in options:
        low = option.lower()
        if low == wanted or low in wanted or wanted in low:
            return option
    return None


async def _from_directory(source_url: str, industry: str, city: str) -> tuple[list[CompanyRef], list[str]]:
    notes: list[str] = []
    page = await scrape_page(ScrapePageInput(url=source_url))
    if page.get("status") != "success":
        return [], [f"{source_url}: {page.get('message', 'unreadable')}"]

    # Apply the directory's own filters when they cover the request — far more
    # accurate than reading an unfiltered first page of mixed listings.
    params: dict[str, str] = {}
    for name, options in page.get("filters", {}).items():
        for wanted in (industry, city):
            match = _matching_option(options, wanted)
            if match:
                params[name] = match
                break
    if params:
        base = source_url.split("?")[0]
        filtered_url = f"{base}?{urlencode(params)}"
        filtered = await scrape_page(ScrapePageInput(url=filtered_url))
        listings = filtered.get("listings", []) if filtered.get("status") == "success" else []
        if not listings:
            notes.append(f"{base} lists 0 companies for {params} (using the site's own filters)")
            return [], notes
        notes.append(f"Used the directory's filters: {filtered_url}")
    else:
        listings = page.get("listings", [])
        notes.append(f"{source_url} has no matching filters; read its first page unfiltered")

    companies = [CompanyRef(name=item["label"], profile_url=item["url"]) for item in listings]
    return companies, notes


async def _from_web(industry: str, city: str, limit: int, dork_creds: Any) -> tuple[list[CompanyRef], list[str]]:
    queries = [
        f"{industry} company {city} pvt ltd",
        f"{industry} {city} \"contact us\"",
        f"{industry} manufacturers {city}",
    ]
    companies: list[CompanyRef] = []
    seen: set[str] = set()
    used = 0
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for query in queries:
            if len(companies) >= limit:
                break
            if used:
                await asyncio.sleep(QUERY_GAP_SECONDS)
            used += 1
            try:
                results, _ = await _search(client, query, 10, dork_creds)
            except SearchBlocked:
                return companies, [SEARCH_BLOCKED_MESSAGE]
            except Exception as exc:
                logger.warning("find_leads search failed: %s", type(exc).__name__)
                continue
            for r in results:
                domain = r["domain"]
                if (not r["url"].startswith("http") or domain in seen or _is_non_official(r["url"])
                        or _LISTICLE_RE.search(r["title"])):
                    continue
                seen.add(domain)
                parsed = urlparse(r["url"])
                companies.append(CompanyRef(
                    name=_company_name(r["title"], domain),
                    website=f"{parsed.scheme}://{parsed.netloc}/",
                ))
                if len(companies) >= limit:
                    break
    return companies, [f"Web search: {used} queries, {len(companies)} company websites found"]


async def find_leads(input_data: FindLeadsInput, dork_creds: Any = None) -> dict[str, Any]:
    candidates: list[CompanyRef] = []
    notes: list[str] = []

    if input_data.source_url:
        found, directory_notes = await _from_directory(
            input_data.source_url, input_data.industry, input_data.city
        )
        candidates.extend(found)
        notes.extend(directory_notes)

    if len(candidates) < input_data.max_leads:
        found, web_notes = await _from_web(
            input_data.industry, input_data.city,
            input_data.max_leads - len(candidates), dork_creds,
        )
        candidates.extend(found)
        notes.extend(web_notes)

    if not candidates:
        if SEARCH_BLOCKED_MESSAGE in notes:
            return {"status": "error", "reason": "search_blocked", "leads": [], "notes": notes}
        return {
            "status": "success",
            "leads": [],
            "notes": notes + ["No companies found. Try a more specific industry term."],
        }

    research = await research_companies(
        ResearchCompaniesInput(companies=candidates[: input_data.max_leads], city=input_data.city),
        dork_creds,
    )
    discovered_by_search = {c.website for c in candidates if c.website and not c.profile_url}
    for company in research["companies"]:
        declared = company.pop("site_name", None)
        if declared and company.get("website") in discovered_by_search:
            company["name"] = declared
    in_city = [c for c in research["companies"] if c.get("city_match") is not False]
    elsewhere = [c for c in research["companies"] if c.get("city_match") is False]
    result: dict[str, Any] = {"status": "success", "leads": in_city, "notes": notes}
    if elsewhere:
        result["outside_city"] = elsewhere
    return result
