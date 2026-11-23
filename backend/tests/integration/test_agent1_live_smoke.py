import httpx
import pytest

from backend.app.integrations.crm.hubspot import HubSpotAdapter
from backend.app.integrations.research.gdelt import GdeltDocAdapter
from backend.app.integrations.research.job_boards import GreenhouseAdapter, LeverAdapter
from backend.app.integrations.research.regulatory import RegulatoryAdapter
from backend.app.integrations.research.sec_edgar import SecEdgarAdapter


@pytest.mark.asyncio
async def test_mode_b_gdelt_smoke():
    """Verify GDELT DOC 2.0 API bounded query or graceful network/error handling."""
    adapter = GdeltDocAdapter()
    try:
        articles, status = await adapter.search_growth_news("Microsoft", max_records=3)
        assert isinstance(articles, list)
        assert status in ("VERIFIED", "NO_MATCH", "SOURCE_FAILED", "NOT_CONFIGURED")
        if articles:
            first = articles[0]
            assert "title" in first
            assert "url" in first
            assert first["source_provider"] == "gdelt"
            assert first["signal_type"] == "growth"
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError):
        pytest.skip("GDELT outbound network call blocked by sandbox/firewall")

@pytest.mark.asyncio
async def test_mode_b_sec_edgar_smoke():
    """Verify SEC EDGAR compliance with User-Agent and CIK querying."""
    adapter = SecEdgarAdapter()
    assert len(adapter.identity) > 5
    assert "@" in adapter.identity

    # Test CIK resolution and text inspection logic
    cik = adapter.resolve_cik("JPMorgan Chase")
    assert cik == "0000019617"  # JPM is public CIK 19617

    try:
        filing_meta = await adapter.fetch_recent_10k_metadata("0000019617")
        if filing_meta:
            assert filing_meta["cik"] == "0000019617"
            assert filing_meta["form"] == "10-K"
            assert "url" in filing_meta
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError):
        pytest.skip("SEC EDGAR outbound network call blocked by sandbox/firewall")

@pytest.mark.asyncio
async def test_mode_b_job_boards_smoke():
    """Verify ATS Greenhouse/Lever adapter query and missing board graceful response."""
    gh_adapter = GreenhouseAdapter()
    lever_adapter = LeverAdapter()

    # Test graceful handling of non-existent board
    jobs_gh = await gh_adapter.fetch_jobs("non-existent-co-xyz-999")
    assert jobs_gh == []

    postings_lever = await lever_adapter.fetch_postings("non-existent-co-xyz-999")
    assert postings_lever == []

    # Test live query if network available
    try:
        gh_jobs = await gh_adapter.fetch_jobs("github")
        assert isinstance(gh_jobs, list)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError):
        pytest.skip("Greenhouse outbound network call blocked by sandbox/firewall")

@pytest.mark.asyncio
async def test_mode_b_regulatory_smoke():
    """Verify Regulatory adapter rule engine and dataset integrity."""
    adapter = RegulatoryAdapter()
    rules = adapter.get_cached_rules()
    assert len(rules) >= 3

    # Payer gets CMS rule
    payer_signals = adapter.evaluate_account_applicability(
        account_id="acc-payer",
        company_name="Humana Health Plan",
        industry="Health Insurance",
        keywords="medicare advantage payer health plan",
    )
    assert any("CMS-0057-F" in s.get("signal_subtype", "") or "CMS-9115-F" in s.get("signal_subtype", "") for s in payer_signals)

    # Acute hospital does NOT get CMS rule
    hospital_signals = adapter.evaluate_account_applicability(
        account_id="acc-hosp",
        company_name="St. Jude Children's Research Hospital",
        industry="Hospital & Health Care",
        keywords="pediatric cancer hospital clinical",
    )
    assert not any("CMS-0057-F" in s.get("signal_subtype", "") for s in hospital_signals)

    # Bank gets FinCEN / OCC rules
    bank_signals = adapter.evaluate_account_applicability(
        account_id="acc-bank",
        company_name="JPMorgan Chase Bank",
        industry="Financial Services",
        keywords="commercial banking lending",
    )
    assert any("FINCEN" in s.get("signal_subtype", "") or "OCC" in s.get("signal_subtype", "") for s in bank_signals)

@pytest.mark.asyncio
async def test_mode_b_hubspot_unconfigured_smoke():
    """Verify HubSpot adapter safely returns empty signals without fabricating when unconfigured."""
    adapter = HubSpotAdapter()
    result = await adapter.fetch_company_intent("any-company.com", account_id="acc-123")
    assert result is None, "HubSpot must return None without fabricating signals when unconfigured/disabled"
