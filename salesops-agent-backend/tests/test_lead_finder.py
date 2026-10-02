"""Offline tests for mcp_tools/lead_finder.py and search-block detection."""

import asyncio

import httpx
import pytest

from mcp_tools import lead_finder
from mcp_tools.lead_finder import FindLeadsInput, _company_name, _matching_option, find_leads
from mcp_tools.web_research import SearchBlocked, _search_ddg


def test_company_name_drops_generic_title_parts():
    assert _company_name("Contact Us - Indus-group", "indus-group.com") == "Indus-group"
    assert _company_name("Skyways - Manufacturers (Pvt.) Ltd", "skyways.com.pk") == "Skyways"
    assert _company_name("Home", "mehran-plastic.pk") == "Mehran Plastic"


def test_matching_option_is_case_insensitive_both_ways():
    options = ["Fintech", "Manufacturing", "Retail"]
    assert _matching_option(options, "manufacturing") == "Manufacturing"
    assert _matching_option(["Karachi", "Lahore"], "karachi, pakistan") == "Karachi"
    assert _matching_option(options, "textiles") is None


def test_ddg_challenge_page_raises_instead_of_returning_no_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, text="<html>anomaly challenge</html>")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await _search_ddg(client, "anything", 5)

    with pytest.raises(SearchBlocked):
        asyncio.run(run())


def test_directory_with_zero_filtered_results_reports_it(monkeypatch):
    pages = {
        "https://dir.example/list": {
            "status": "success",
            "filters": {"industry": ["Manufacturing"], "location": ["Karachi"]},
            "listings": [{"label": "Somewhere Else Ltd", "url": "https://dir.example/list/x"}],
        },
        "https://dir.example/list?industry=Manufacturing&location=Karachi": {
            "status": "success",
        },
    }

    async def fake_scrape(input_data):
        return pages[input_data.url]

    async def fake_web(industry, city, limit, creds):
        return [], ["Web search: 0"]

    monkeypatch.setattr(lead_finder, "scrape_page", fake_scrape)
    monkeypatch.setattr(lead_finder, "_from_web", fake_web)

    result = asyncio.run(find_leads(FindLeadsInput(
        industry="manufacturing", city="Karachi", source_url="https://dir.example/list",
    )))
    assert result["leads"] == []
    assert any("lists 0 companies" in n for n in result["notes"])
