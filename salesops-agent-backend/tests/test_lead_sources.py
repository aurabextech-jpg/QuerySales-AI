"""Unit tests for the lead-source and dork-search pure helpers (no network)."""

import pytest

from mcp_tools.google_dork import DorkSearchInput, _dork_creds, dork_search
from mcp_tools.lead_sources import (
    MAX_SITES,
    SearchSourceSitesInput,
    _keywords,
    _match_snippets,
    _matching_links,
    _source_urls,
    _visible_text,
    search_source_sites,
)


class FakeCreds:
    """Stands in for core.user_config.ResolvedIntegration."""

    def __init__(self, **values: str):
        self._values = values

    def get(self, name: str, default: str = "") -> str:
        return self._values.get(name) or default


# ── Source URL parsing ─────────────────────────────────────────────────────

def test_source_urls_splits_lines_and_trims():
    creds = FakeCreds(site_urls=" https://a.example/x \n\nhttps://b.example/y\n")
    assert _source_urls(creds) == ["https://a.example/x", "https://b.example/y"]


def test_source_urls_rejects_non_http_entries():
    creds = FakeCreds(site_urls="ftp://a.example\njavascript:alert(1)\nhttps://ok.example")
    assert _source_urls(creds) == ["https://ok.example"]


def test_source_urls_caps_the_list():
    creds = FakeCreds(site_urls="\n".join(f"https://s{i}.example" for i in range(30)))
    assert len(_source_urls(creds)) == MAX_SITES


def test_source_urls_without_credentials_is_empty():
    assert _source_urls(None) == []


# ── HTML reduction and matching ────────────────────────────────────────────

def test_visible_text_drops_scripts_and_tags():
    html = "<div>Acme <script>var x = 'hidden';</script><b>Textiles</b></div>"
    text = _visible_text(html)
    assert "hidden" not in text
    assert "<" not in text
    assert "Acme" in text and "Textiles" in text


def test_keywords_drops_short_filler_words():
    assert _keywords("a CFO in the Textile co") == ["cfo", "the", "textile"]


def test_match_snippets_returns_context_around_hits():
    text = "prefix " * 40 + "Acme Textiles Ltd" + " suffix" * 40
    snippets = _match_snippets(text, ["textiles"], limit=5)
    assert len(snippets) == 1
    assert "Acme Textiles Ltd" in snippets[0]


def test_match_snippets_respects_the_limit():
    # Hits spaced wider than the snippet window, so each is its own passage.
    text = ("textiles" + " filler" * 100) * 6
    assert len(_match_snippets(text, ["textiles"], limit=3)) == 3


def test_match_snippets_collapses_overlapping_hits():
    # Repeated hits inside one window are one passage, not near-duplicates.
    text = " ".join(["textiles"] * 20)
    assert len(_match_snippets(text, ["textiles"], limit=10)) == 1


def test_match_snippets_no_hit_returns_empty():
    assert _match_snippets("nothing relevant here", ["textiles"], limit=5) == []


def test_matching_links_resolves_relative_hrefs():
    html = '<a href="/members/acme">Acme Textiles</a><a href="/other">Unrelated</a>'
    links = _matching_links(html, "https://directory.example/list", ["textiles"], limit=5)
    assert links == [
        {"label": "Acme Textiles", "url": "https://directory.example/members/acme"}
    ]


def test_matching_links_skips_anchors_and_mailto():
    html = '<a href="#top">Textiles</a><a href="mailto:x@y.z">Textiles</a>'
    assert _matching_links(html, "https://directory.example", ["textiles"], limit=5) == []


# ── Unconfigured contract — must degrade, never raise (rule §3.5) ──────────

@pytest.mark.asyncio
async def test_search_source_sites_unconfigured_returns_reason():
    result = await search_source_sites(SearchSourceSitesInput(query="textiles"), None)
    assert result["status"] == "error"
    assert result["reason"] == "not_configured"


@pytest.mark.asyncio
async def test_search_source_sites_rejects_query_without_usable_terms():
    creds = FakeCreds(site_urls="https://a.example")
    result = await search_source_sites(SearchSourceSitesInput(query="a b"), creds)
    assert result["status"] == "error"
    assert result.get("reason") != "not_configured"


def test_dork_creds_without_configuration_is_empty():
    assert _dork_creds(None) == ("", "")
    assert _dork_creds(FakeCreds(api_key="k")) == ("k", "")


@pytest.mark.asyncio
async def test_dork_search_unconfigured_returns_reason():
    result = await dork_search(DorkSearchInput(query='site:example.com "cfo"'), None)
    assert result["status"] == "error"
    assert result["reason"] == "not_configured"


def test_dork_search_input_caps_results_at_googles_limit():
    with pytest.raises(ValueError):
        DorkSearchInput(query="x", max_results=50)
