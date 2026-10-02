"""Offline tests for mcp_tools/web_research.py — extraction, scoring, SSRF guard."""

import asyncio

import pytest

from mcp_tools.web_research import (
    UnsafeUrl,
    _assert_public,
    _contacts,
    _extract,
    _listings,
    _absolute_links,
    _pick_official,
    _score,
    _social_links,
    directory_structure,
)

PROFILE_PAGE = """
<html><head><title>Crest LED | Directory</title>
<meta name="description" content="LED lights manufacturer.">
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "LocalBusiness", "name": "Crest LED",
 "telephone": "0301 4086773", "email": "mailto:info@crestled.com",
 "address": {"@type": "PostalAddress", "addressLocality": "Lahore", "addressCountry": "PK"},
 "aggregateRating": {"ratingValue": "4.6", "reviewCount": "1,204"}}
</script></head>
<body><a href="tel:%20+92-61-4589999">Call</a>
<a href="mailto:%20sales@crestled.com">Mail</a>
<a href="https://www.facebook.com/sharer/sharer.php?u=x">Share</a>
<a href="https://www.facebook.com/CrestLed/">Facebook</a>
<a href="/contact-us">Contact</a></body></html>
"""

DIRECTORY_PAGE = """
<form><select name="industry"><option value="all">All</option>
<option value="Manufacturing">Manufacturing</option></select></form>
<a href="/business-directory">Directory</a>
<a href="/business-directory/crest-led">Crest LED</a>
<a href="/business-directory/home-innovators">Home Innovators</a>
<a href="/business-directory?page=2">2</a>
<a href="/login">Login</a>
<a href="https://www.crestled.com/">crestled.com</a>
"""
DIRECTORY_URL = "https://portal.example/business-directory"


def test_extract_prefers_structured_data_and_decodes_links():
    data = _extract(PROFILE_PAGE, "https://portal.example/business-directory/crest-led")
    assert data["name"] == "Crest LED"
    assert data["emails"][0] == "info@crestled.com"
    assert "sales@crestled.com" in data["emails"]  # %20 decoded, not "%20sales@"
    assert "+92614589999" in data["phones"]        # tel:%20+92… decoded
    assert data["rating"] == 4.6 and data["review_count"] == 1204
    assert "Lahore" in data["address"]
    assert data["contact_page"].endswith("/contact-us")


def test_share_buttons_are_not_social_profiles():
    links = _absolute_links(PROFILE_PAGE, "https://portal.example/")
    assert _social_links(links) == {"facebook": "https://www.facebook.com/CrestLed/"}


def test_text_phones_need_a_label_and_a_real_prefix():
    _, phones = _contacts("", "Phone: +92 21 3456 7890. Order ID 2024 1234 5678 9")
    assert phones == ["+922134567890"]


def test_directory_structure_splits_listings_from_navigation():
    listings, external, pages = _listings(_absolute_links(DIRECTORY_PAGE, DIRECTORY_URL), DIRECTORY_URL)
    assert [l["label"] for l in listings] == ["Crest LED", "Home Innovators"]
    assert pages == ["https://portal.example/business-directory?page=2"]
    assert external == [{"label": "crestled.com", "url": "https://www.crestled.com/"}]
    assert directory_structure(DIRECTORY_PAGE, DIRECTORY_URL)["filters"] == {
        "industry": ["Manufacturing"]
    }


def test_pick_official_skips_directories_and_social():
    results = [
        {"url": "https://www.facebook.com/engro", "domain": "facebook.com"},
        {"url": "https://bizsouthasia.com/engro", "domain": "bizsouthasia.com"},
        {"url": "https://www.engropolymer.com/about", "domain": "engropolymer.com"},
    ]
    assert _pick_official(results, "Engro Polymer and Chemicals") == "https://www.engropolymer.com/"
    assert _pick_official(results[:1], "Engro Polymer and Chemicals") is None


def test_score_is_explained_and_tiered():
    full = {"website": "x", "emails": ["a"], "phones": ["b"], "address": "c",
            "social": {"f": "g"}, "description": "d", "rating": 4.5, "review_count": 120}
    score, breakdown, tier = _score(full)
    assert (score, tier) == (100, "High")
    assert sum(breakdown.values()) == 100
    assert _score({})[2] == "Low"
    assert _score({"website": "x", "emails": ["a"], "phones": ["b"]})[2] == "Medium"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",
    "http://169.254.169.254/latest/meta-data",
    "http://10.0.0.5/",
    "file:///etc/passwd",
    "ftp://example.com/",
])
def test_ssrf_guard_rejects_non_public_targets(url):
    with pytest.raises(UnsafeUrl):
        asyncio.run(_assert_public(url))
