"""Google Places API MCP tool adapter.

Uses the Google Places API (New) for business discovery.
Supports Text Search to find businesses by query string.
"""

import asyncio
import httpx
import logging
from typing import Any
from pydantic import BaseModel, Field
from core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input / Output schemas
# ---------------------------------------------------------------------------

class SearchBusinessesInput(BaseModel):
    """Input schema for searching businesses via Google Places."""
    query: str = Field(..., description="Search query, e.g. 'clinics in Gulberg Lahore'")
    max_results: int = Field(20, ge=1, le=60, description="Max number of results to return")


class PlaceResult(BaseModel):
    """Simplified representation of a Google Places result."""
    place_id: str
    name: str
    formatted_address: str
    rating: float | None = None
    user_ratings_total: int | None = None
    types: list[str] = []
    phone_number: str | None = None
    website: str | None = None


class GetPlaceDetailsInput(BaseModel):
    """Input schema for fetching detailed info about a single place."""
    place_id: str = Field(..., description="Google Place ID")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def search_businesses(input_data: SearchBusinessesInput) -> dict[str, Any]:
    """Search for businesses using Google Places Text Search."""
    # --- Real API call (Google Places API New — Text Search) ---
    api_key = settings.GOOGLE_PLACES_API_KEY
    if not api_key:
        return {"status": "error", "message": "GOOGLE_PLACES_API_KEY is not configured"}

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,"
            "places.rating,places.userRatingCount,places.types,"
            "places.nationalPhoneNumber,places.websiteUri"
        ),
    }
    body = {
        "textQuery": input_data.query,
        "maxResultCount": input_data.max_results,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=body, headers=headers, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()

            results: list[dict[str, Any]] = []
            for place in data.get("places", []):
                results.append({
                    "place_id": place.get("id", ""),
                    "name": place.get("displayName", {}).get("text", ""),
                    "formatted_address": place.get("formattedAddress", ""),
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("userRatingCount"),
                    "types": place.get("types", []),
                    "phone_number": place.get("nationalPhoneNumber"),
                    "website": place.get("websiteUri"),
                })

            return {
                "status": "success",
                "total_results": len(results),
                "results": results,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Google Places API HTTP error: %s", exc.response.text)
            return {"status": "error", "message": str(exc), "details": exc.response.text}
        except Exception as exc:
            logger.error("Google Places API error: %s", exc)
            return {"status": "error", "message": str(exc)}


async def get_place_details(input_data: GetPlaceDetailsInput) -> dict[str, Any]:
    """Fetch detailed information about a single place by its place_id."""
    api_key = settings.GOOGLE_PLACES_API_KEY
    if not api_key:
        return {"status": "error", "message": "GOOGLE_PLACES_API_KEY is not configured"}

    url = f"https://places.googleapis.com/v1/places/{input_data.place_id}"
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "id,displayName,formattedAddress,rating,userRatingCount,"
            "types,nationalPhoneNumber,websiteUri,currentOpeningHours"
        ),
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=15.0)
            resp.raise_for_status()
            place = resp.json()
            return {
                "status": "success",
                "data": {
                    "place_id": place.get("id", ""),
                    "name": place.get("displayName", {}).get("text", ""),
                    "formatted_address": place.get("formattedAddress", ""),
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("userRatingCount"),
                    "types": place.get("types", []),
                    "phone_number": place.get("nationalPhoneNumber"),
                    "website": place.get("websiteUri"),
                },
            }
        except httpx.HTTPStatusError as exc:
            return {"status": "error", "message": str(exc), "details": exc.response.text}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# Multi-query lead search — the Lead Agent's primary discovery skill
# ---------------------------------------------------------------------------

# Maps broad industry keywords to more specific search variations.
INDUSTRY_SYNONYMS: dict[str, list[str]] = {
    "tech": ["software companies", "IT services", "technology startups", "web development agencies"],
    "textile": ["textile mills", "fabric manufacturers", "garment factories", "clothing exporters"],
    "healthcare": ["clinics", "hospitals", "diagnostic labs", "medical centers"],
    "food": ["restaurants", "food manufacturers", "catering services", "bakeries"],
    "construction": ["construction companies", "builders", "real estate developers", "architecture firms"],
    "education": ["schools", "training institutes", "coaching centers", "universities"],
    "retail": ["retail stores", "wholesale dealers", "shopping centers", "supermarkets"],
    "manufacturing": ["factories", "manufacturing plants", "industrial units", "production houses"],
    "logistics": ["courier services", "freight companies", "warehousing", "transport companies"],
    "finance": ["accounting firms", "insurance agencies", "microfinance", "investment companies"],
}


class SearchLeadsMultiInput(BaseModel):
    """Multi-query lead search: fans out 3-4 keyword variations for maximum coverage."""

    industry: str = Field(..., description="Industry/niche keyword, e.g. 'textile', 'healthcare'")
    location: str = Field(..., description="Target city or area, e.g. 'Karachi', 'Gulberg Lahore'")
    max_results_per_query: int = Field(
        10, ge=1, le=20, description="Max results per individual query"
    )


async def search_leads_multi(input_data: SearchLeadsMultiInput) -> dict[str, Any]:
    """Run 3-4 search query variations in parallel and return deduplicated results.

    Strategy:
      1. Look up synonyms for the industry keyword (or use the keyword as-is).
      2. Build 3-4 queries combining synonyms with the location.
      3. Fire all queries concurrently via ``search_businesses``.
      4. Merge, deduplicate by place_id, and sort by rating descending.
    """
    industry_lower = input_data.industry.lower().strip()

    # Generate query variations
    synonyms = INDUSTRY_SYNONYMS.get(industry_lower, [])
    queries: list[str] = [f"{input_data.industry} in {input_data.location}"]

    if synonyms:
        # Pick up to 3 synonyms so total queries = 4 max
        for syn in synonyms[:3]:
            queries.append(f"{syn} in {input_data.location}")
    else:
        # No known synonyms — generate simple variations
        queries.append(f"{industry_lower} services in {input_data.location}")
        queries.append(f"{industry_lower} companies in {input_data.location}")
        queries.append(f"best {industry_lower} in {input_data.location}")

    logger.info(
        "search_leads_multi: running %d query variations for '%s' in '%s'",
        len(queries), input_data.industry, input_data.location,
    )

    # Run all queries concurrently
    tasks = [
        search_businesses(
            SearchBusinessesInput(
                query=q,
                max_results=input_data.max_results_per_query,
            )
        )
        for q in queries
    ]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge and deduplicate by place_id
    seen_ids: set[str] = set()
    merged: list[dict[str, Any]] = []
    queries_used: list[str] = []

    for idx, res in enumerate(results_list):
        if isinstance(res, Exception):
            logger.warning("Query #%d failed: %s", idx, res)
            continue
        if isinstance(res, dict) and res.get("status") == "success":
            queries_used.append(queries[idx])
            for place in res.get("results", []):
                pid = place.get("place_id", "")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    merged.append(place)

    # Sort by rating descending (None → 0)
    merged.sort(key=lambda p: (p.get("rating") or 0), reverse=True)

    return {
        "status": "success",
        "queries_used": queries_used,
        "total_unique_results": len(merged),
        "results": merged,
    }
