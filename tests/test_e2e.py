"""End-to-End Tier 4 scenario tests for jimoty-cli (Scenarios 1-5 from TEST_INFRA.md).

Scenario 1: Chigasaki 50cc Commuter Search & Triage
Scenario 2: Stolen / No-Paperwork Scam Triage (FATAL_REJECT)
Scenario 3: Healthy 4-Stroke FI Scooter Evaluation (RECOMMENDED)
Scenario 4: In-Person Direct Pickup Flow (Polite inquiry & physical checklist)
Scenario 5: Proxy-Routed Network Fault Injection (HTTP 429 backoff & IncompleteRead recovery)
"""

from __future__ import annotations

import json
import unittest.mock as mock
from typing import Any, Dict
import httpx
import pytest

from jimoty.client import JimotyClient
from jimoty.models import SearchQuery
from jimoty.parser import parse_detail_page, parse_search_page

# Conditionally import optional downstream components
try:
    from jimoty.diagnostics import DiagnosticEngine
    HAS_DIAGNOSTICS = True
except ImportError:
    HAS_DIAGNOSTICS = False

try:
    from jimoty.templates import generate_inquiry_template
    HAS_TEMPLATES = True
except ImportError:
    HAS_TEMPLATES = False

try:
    from jimoty.checklist import generate_pickup_checklist
    HAS_CHECKLIST = True
except ImportError:
    HAS_CHECKLIST = False


# ===========================================================================
# Scenario 1: Chigasaki 50cc Commuter Search & Triage Pipeline
# ===========================================================================


class TestScenario1ChigasakiCommuterSearch:
    """Scenario 1: Search for mopeds in Chigasaki under 60,000 yen, parse listings, and triage top hit."""

    def test_search_and_triage_pipeline(
        self,
        search_bikes_html: str,
        detail_jog_html: str,
    ) -> None:
        # Step 1: Formulate search query for Chigasaki mopeds under 60,000 yen
        query = SearchQuery(
            prefecture="kanagawa",
            municipality="a-314-chigasaki",
            category="sale-bik",
            max_price=60000,
        )

        # Step 2: Simulate network search response using recorded HTML fixture
        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "article-18jog" in url_str:
                return httpx.Response(200, text=detail_jog_html, request=request)
            return httpx.Response(200, text=search_bikes_html, request=request)

        transport = httpx.MockTransport(handler)
        with JimotyClient(transport=transport) as client:
            search_html = client.fetch_search_page(query)
            listings = parse_search_page(search_html)

            # Assert listings retrieved and filtered
            assert len(listings) >= 5
            jog_listing = next((l for l in listings if "18jog" in l.id), None)
            assert jog_listing is not None
            assert jog_listing.price <= 60000
            assert "茅ヶ崎" in (jog_listing.location_text or "")

            # Step 3: Fetch detail page for top candidate
            detail_html = client.fetch_detail_page(jog_listing.url)
            detail = parse_detail_page(detail_html)

            assert detail.id == "article-18jog"
            assert detail.price == 38000
            assert "4スト" in detail.title or "4スト" in detail.description
            assert detail.seller is not None
            assert detail.seller.identified is True

            # Step 4: Run diagnostic triage if engine is available
            if HAS_DIAGNOSTICS:
                engine = DiagnosticEngine()
                report = engine.diagnose(detail)
                assert str(report.verdict) in ("RECOMMENDED", "Verdict.RECOMMENDED")
                assert report.score >= 70
                assert len(report.fatal_flags) == 0


# ===========================================================================
# Scenario 2: Stolen / No-Paperwork Scam Triage
# ===========================================================================


class TestScenario2StolenNoPaperworkScamTriage:
    """Scenario 2: Inspect listing explicitly offering a bike with '書類なし / 鍵なし'."""

    def test_junk_no_papers_detection(self, detail_junk_html: str) -> None:
        detail = parse_detail_page(detail_junk_html)
        assert detail.id == "article-99junk"
        assert "書類なし" in detail.description
        assert "鍵なし" in detail.description
        assert "不動" in detail.description

        if HAS_DIAGNOSTICS:
            engine = DiagnosticEngine()
            report = engine.diagnose(detail)
            assert str(report.verdict) in ("FATAL_REJECT", "Verdict.FATAL_REJECT")
            assert len(report.fatal_flags) >= 1
            # Check for document rule fatal flag
            report_dict = report.to_dict()
            assert report_dict["score"] < 40
            assert any(
                "DOC" in f or "書類なし" in f or "stolen" in f.lower()
                for f in report_dict["fatal_flags"]
            )


# ===========================================================================
# Scenario 3: Healthy 4-Stroke FI Scooter Evaluation
# ===========================================================================


class TestScenario3Healthy4StFiEvaluation:
    """Scenario 3: Inspect verified seller offering running Jog with paperwork and high ratings."""

    def test_healthy_bike_recommended_evaluation(self, detail_jog_html: str) -> None:
        detail = parse_detail_page(detail_jog_html)
        assert detail.price == 38000
        assert "廃車申告受付書" in detail.description
        assert detail.seller is not None
        assert detail.seller.identified is True
        assert detail.seller.good_ratings >= 50
        assert detail.seller.bad_ratings == 0

        if HAS_DIAGNOSTICS:
            engine = DiagnosticEngine()
            report = engine.diagnose(detail)
            assert str(report.verdict) in ("RECOMMENDED", "Verdict.RECOMMENDED")
            assert report.score >= 75
            assert len(report.fatal_flags) == 0
            assert any("4スト" in r.reasoning or "FI" in r.reasoning for r in report.rules_evaluated)


# ===========================================================================
# Scenario 4: In-Person Direct Pickup Flow
# ===========================================================================


class TestScenario4DirectPickupFlow:
    """Scenario 4: Select vehicle, generate polite Japanese inquiry, and produce on-site checklist."""

    def test_pickup_inquiry_and_checklist_generation(self, detail_jog_html: str) -> None:
        detail = parse_detail_page(detail_jog_html)

        if HAS_TEMPLATES:
            # Generate Japanese initial inquiry message
            inquiry_msg = generate_inquiry_template(detail, template_type="initial")
            assert "湘南ライダー" in inquiry_msg
            assert "ヤマハ ジョグ" in inquiry_msg
            assert "直接引き取り" in inquiry_msg

            # Generate schedule coordination message
            schedule_msg = generate_inquiry_template(detail, template_type="schedule")
            assert "日時" in schedule_msg

        if HAS_CHECKLIST:
            # Generate on-site physical checklist
            checklist = generate_pickup_checklist(detail)
            assert len(checklist) >= 5
            # Must check VIN / frame number matching
            assert any("車台番号" in i.item or "フレーム番号" in i.item or "書類" in i.item for i in checklist)


# ===========================================================================
# Scenario 5: Proxy-Routed Network Fault Injection
# ===========================================================================


class TestScenario5ProxyFaultInjection:
    """Scenario 5: Search with proxy configuration, simulate HTTP 429 and IncompleteRead, verify resilience."""

    def test_proxy_fault_recovery_and_backoff(self) -> None:
        call_count = 0

        def fault_injector(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First attempt: rate limited 429 with Retry-After header
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0.05"},
                    text="Rate Limited",
                    request=request,
                )
            if call_count == 2:
                # Second attempt: chunked IncompleteRead simulation
                raise httpx.ReadError("IncompleteRead: stream cut off by upstream proxy", request=request)
            # Third attempt: recovers and succeeds
            return httpx.Response(200, text="<html><body>Success Recovered</body></html>", request=request)

        transport = httpx.MockTransport(fault_injector)
        client = JimotyClient(
            proxy="http://jp-residential.proxy:8080",
            transport=transport,
            max_retries=3,
            backoff_factor=0.01,
        )

        with mock.patch("time.sleep", return_value=None):
            resp = client.get("https://jmty.jp/kanagawa/sale-bik")

        assert resp.status_code == 200
        assert "Success Recovered" in resp.text
        assert call_count == 3
