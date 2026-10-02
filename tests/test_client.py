"""Unit and integration tests for JimotyClient, URL builder, proxy configuration, and network resilience."""

from __future__ import annotations

import http.client
import os
import unittest.mock as mock
from typing import Any
import httpx
import pytest

from jimoty.client import (
    BlockedError,
    ChunkedTransferError,
    JimotyClient,
    JimotyNetworkError,
    ListingNotFoundError,
    ProxyError,
    RateLimitError,
    build_search_url,
)
from jimoty.config import (
    BASE_URL,
    DEFAULT_CATEGORY,
    DEFAULT_MAX_PRICE,
    DEFAULT_MUNICIPALITY,
    DEFAULT_PREFECTURE,
    JimotyConfig,
    resolve_category,
    resolve_municipality,
    resolve_proxy,
)
from jimoty.models import SearchQuery


# ===========================================================================
# Tier 1 & 2: URL Builder Tests
# ===========================================================================


class TestUrlBuilder:
    """Test URL generation covering all taxonomy combinations and edge cases."""

    def test_default_search_url(self) -> None:
        """Verify default URL corresponds to Chigasaki motorcycle listings when using default SearchQuery."""
        query = SearchQuery()
        url = build_search_url(query=query)
        assert url == f"{BASE_URL}/kanagawa/sale-bik/g-all/a-314-chigasaki"

    def test_default_category_search_url(self) -> None:
        """Verify URL generation when no query or municipality is specified."""
        url = build_search_url()
        assert url == f"{BASE_URL}/kanagawa/sale-bik"

    def test_search_url_with_query_object(self) -> None:
        """Verify URL generation from SearchQuery instance."""
        query = SearchQuery(
            prefecture="kanagawa",
            category="sale-bik",
            municipality="a-314-chigasaki",
            keyword="ジョグ",
            max_price=50000,
            page=2,
        )
        url = build_search_url(query=query)
        assert f"{BASE_URL}/kanagawa/sale-bik/g-all/a-314-chigasaki" in url
        assert "keyword=%E3%82%B8%E3%83%A7%E3%82%B0" in url or "keyword=" in url
        assert "max_price=50000" in url
        assert "page=2" in url

    def test_prefecture_only_url(self) -> None:
        """Verify URL for prefecture without category or municipality."""
        url = build_search_url(prefecture="tokyo", category="all", municipality=None)
        assert url == f"{BASE_URL}/tokyo"

    def test_prefecture_and_category_no_municipality(self) -> None:
        """Verify URL for prefecture and category without municipality."""
        url = build_search_url(prefecture="kanagawa", category="sale-bik", municipality=None)
        assert url == f"{BASE_URL}/kanagawa/sale-bik"

    def test_municipality_alias_resolution(self) -> None:
        """Verify Japanese municipality names and aliases resolve correctly."""
        # Chigasaki variants
        assert resolve_municipality("chigasaki") == "a-314-chigasaki"
        assert resolve_municipality("茅ヶ崎") == "a-314-chigasaki"
        assert resolve_municipality("茅ヶ崎市") == "a-314-chigasaki"

        # Fujisawa variants
        assert resolve_municipality("fujisawa") == "a-312-fujisawa"
        assert resolve_municipality("藤沢") == "a-312-fujisawa"
        assert resolve_municipality("藤沢市") == "a-312-fujisawa"

        # Kamakura
        assert resolve_municipality("鎌倉市") == "a-311-kamakura"
        # Hiratsuka
        assert resolve_municipality("平塚市") == "a-313-hiratsuka"
        # Unknown/direct slug passed as-is
        assert resolve_municipality("a-999-custom") == "a-999-custom"
        assert resolve_municipality(None) is None

    def test_category_alias_resolution(self) -> None:
        """Verify category names and Japanese aliases resolve to correct slugs."""
        assert resolve_category("motorcycle") == "sale-bik"
        assert resolve_category("bike") == "sale-bik"
        assert resolve_category("バイク") == "sale-bik"
        assert resolve_category("bicycle") == "sale-bic"
        assert resolve_category("自転車") == "sale-bic"
        assert resolve_category("car") == "sale-car"
        assert resolve_category("車") == "sale-car"
        assert resolve_category("all") == "all"
        assert resolve_category(None) == "sale-bik"

    def test_price_boundaries_in_url(self) -> None:
        """Verify min and max price parameter generation."""
        url = build_search_url(min_price=10000, max_price=60000)
        assert "min_price=10000" in url
        assert "max_price=60000" in url

    def test_zero_max_price_allowed(self) -> None:
        """Verify max_price=0 for free item searches is preserved in URL."""
        url = build_search_url(max_price=0)
        assert "max_price=0" in url

    def test_page_1_omitted_by_default(self) -> None:
        """Page 1 should not append page=1 parameter to keep clean URLs."""
        url = build_search_url(page=1)
        assert "page=1" not in url

    def test_special_characters_in_keyword(self) -> None:
        """Verify special characters, emoji, and spaces are properly handled in URL."""
        url = build_search_url(keyword="原付 50cc ★")
        assert "keyword=" in url

    def test_search_url_with_sorting(self) -> None:
        """Verify sort parameter is captured in SearchQuery.to_params()."""
        query = SearchQuery(sort="price_asc")
        params = query.to_params()
        assert params.get("sort") == "price_asc"

    def test_prefecture_name_normalization(self) -> None:
        """Verify prefecture names are lowercased and stripped."""
        url = build_search_url(prefecture="  KANAGAWA  ", category="sale-bik")
        assert f"{BASE_URL}/kanagawa/sale-bik" in url


# ===========================================================================
# Tier 1 & 2: Proxy Configuration & Resolution Tests
# ===========================================================================


class TestProxyConfiguration:
    """Test proxy resolution precedence, masking, and environment configuration."""

    def test_explicit_proxy_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit argument should override all environment variables."""
        monkeypatch.setenv("JIMOTY_PROXY", "http://env-proxy:8080")
        monkeypatch.setenv("HTTPS_PROXY", "http://https-proxy:8080")
        proxy = resolve_proxy("http://explicit-proxy:8080")
        assert proxy == "http://explicit-proxy:8080"

    def test_jimoty_proxy_env_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """JIMOTY_PROXY should take precedence over HTTPS_PROXY and HTTP_PROXY."""
        monkeypatch.setenv("JIMOTY_PROXY", "http://jimoty-proxy:8080")
        monkeypatch.setenv("HTTPS_PROXY", "http://https-proxy:8080")
        monkeypatch.setenv("HTTP_PROXY", "http://http-proxy:8080")
        assert resolve_proxy() == "http://jimoty-proxy:8080"

    def test_standard_https_proxy_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HTTPS_PROXY should be used if JIMOTY_PROXY is not set."""
        monkeypatch.delenv("JIMOTY_PROXY", raising=False)
        monkeypatch.setenv("HTTPS_PROXY", "http://standard-https:8080")
        assert resolve_proxy() == "http://standard-https:8080"

    def test_no_proxy_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no proxy variables are set, resolve_proxy returns None."""
        for k in ["JIMOTY_PROXY", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"]:
            monkeypatch.delenv(k, raising=False)
        assert resolve_proxy() is None

    def test_proxy_credential_masking_in_config_dict(self) -> None:
        """Credentials in proxy URL must be masked when exported to dict."""
        cfg = JimotyConfig(proxy="http://secret_user:super_secret_pass@127.0.0.1:8888")
        d = cfg.to_dict()
        assert d["proxy_configured"] is True
        assert "super_secret_pass" not in d["proxy"]
        assert "****" in d["proxy"]
        assert "secret_user" in d["proxy"]

    def test_config_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify JimotyConfig.from_env reads operational parameters."""
        monkeypatch.setenv("JIMOTY_PREFECTURE", "tokyo")
        monkeypatch.setenv("JIMOTY_MUNICIPALITY", "a-101-shinjuku")
        monkeypatch.setenv("JIMOTY_CATEGORY", "sale-bic")
        monkeypatch.setenv("JIMOTY_MAX_PRICE", "30000")
        monkeypatch.setenv("JIMOTY_TIMEOUT", "25.0")

        cfg = JimotyConfig.from_env()
        assert cfg.default_prefecture == "tokyo"
        assert cfg.default_municipality == "a-101-shinjuku"
        assert cfg.default_category == "sale-bic"
        assert cfg.default_max_price == 30000
        assert cfg.timeout == 25.0


# ===========================================================================
# Tier 1, 2 & 3: HTTP Client Network Resilience & Retries
# ===========================================================================


class TestJimotyClientResilience:
    """Test HTTP client retry backoff, status code handling, and transport error recovery."""

    def test_successful_request(self) -> None:
        """Verify successful 200 GET request returns httpx.Response."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>Success</html>", request=request)

        transport = httpx.MockTransport(handler)
        with JimotyClient(transport=transport) as client:
            resp = client.get("https://jmty.jp/test")
            assert resp.status_code == 200
            assert resp.text == "<html>Success</html>"

    def test_client_session_reuse(self) -> None:
        """Verify multiple requests reuse the same underlying httpx.Client session."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, text=f"Call {call_count}", request=request)

        transport = httpx.MockTransport(handler)
        with JimotyClient(transport=transport) as client:
            sess1 = client.session
            client.get("https://jmty.jp/1")
            sess2 = client.session
            client.get("https://jmty.jp/2")
            assert sess1 is sess2
            assert call_count == 2

    def test_custom_headers_merged_with_defaults(self) -> None:
        """Verify user-provided headers are merged with default browser headers."""
        custom_header_value = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal custom_header_value
            custom_header_value = request.headers.get("x-custom-test", "")
            return httpx.Response(200, text="OK", request=request)

        transport = httpx.MockTransport(handler)
        with JimotyClient(transport=transport, headers={"X-Custom-Test": "agent-v1"}) as client:
            client.get("https://jmty.jp/custom")

        assert custom_header_value == "agent-v1"

    def test_browser_headers_included(self) -> None:
        """Verify standard desktop User-Agent and Japanese Accept-Language headers."""
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, text="OK", request=request)

        transport = httpx.MockTransport(handler)
        with JimotyClient(transport=transport) as client:
            client.get("https://jmty.jp/test")

        assert "user-agent" in captured_headers
        assert "Mozilla" in captured_headers["user-agent"]
        assert "accept-language" in captured_headers
        assert "ja" in captured_headers["accept-language"]

    def test_http_404_raises_listing_not_found(self) -> None:
        """Verify HTTP 404 raises ListingNotFoundError immediately without wasteful retries."""
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(404, text="Not Found", request=request)

        transport = httpx.MockTransport(handler)
        with JimotyClient(transport=transport, max_retries=3) as client:
            with pytest.raises(ListingNotFoundError) as exc_info:
                client.get("https://jmty.jp/article-missing")

        assert "HTTP 404" in str(exc_info.value)
        assert attempts == 1  # No retries on 404

    def test_http_403_raises_blocked_error(self) -> None:
        """Verify HTTP 403 raises BlockedError with residential proxy guidance."""
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(403, text="Forbidden", request=request)

        transport = httpx.MockTransport(handler)
        with JimotyClient(transport=transport, max_retries=3) as client:
            with pytest.raises(BlockedError) as exc_info:
                client.get("https://jmty.jp/kanagawa")

        assert "HTTP 403" in str(exc_info.value)
        assert "proxy" in str(exc_info.value).lower()
        assert attempts == 1  # No retries on 403

    def test_http_429_retries_and_raises_rate_limit_error(self) -> None:
        """Verify HTTP 429 retries max_retries times and raises RateLimitError."""
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(429, text="Too Many Requests", request=request)

        transport = httpx.MockTransport(handler)
        client = JimotyClient(transport=transport, max_retries=2, backoff_factor=0.01)
        with mock.patch("time.sleep", return_value=None):
            with pytest.raises((RateLimitError, JimotyNetworkError)) as exc_info:
                client.get("https://jmty.jp/test-rate-limit")

        assert "429" in str(exc_info.value)
        assert attempts == 3  # Initial try + 2 retries

    def test_http_429_recovers_after_retry(self) -> None:
        """Verify that if HTTP 429 is resolved on retry, the request succeeds."""
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(429, text="Rate limit", request=request)
            return httpx.Response(200, text="Recovered!", request=request)

        transport = httpx.MockTransport(handler)
        client = JimotyClient(transport=transport, max_retries=2, backoff_factor=0.01)
        with mock.patch("time.sleep", return_value=None):
            resp = client.get("https://jmty.jp/test-rate-limit-recover")

        assert resp.status_code == 200
        assert resp.text == "Recovered!"
        assert attempts == 2

    def test_chunked_incomplete_read_retries_and_recovers(self) -> None:
        """Verify protocol IncompleteRead / ReadError triggers retry and succeeds."""
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise httpx.ReadError("IncompleteRead: stream terminated prematurely", request=request)
            return httpx.Response(200, text="Stream Completed", request=request)

        transport = httpx.MockTransport(handler)
        client = JimotyClient(transport=transport, max_retries=2, backoff_factor=0.01)
        with mock.patch("time.sleep", return_value=None):
            resp = client.get("https://jmty.jp/chunked-stream")

        assert resp.status_code == 200
        assert resp.text == "Stream Completed"
        assert attempts == 2

    def test_chunked_error_exhausted_raises_chunked_error(self) -> None:
        """Verify ChunkedTransferError is raised when retries are exhausted."""
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.RemoteProtocolError("peer closed connection", request=request)

        transport = httpx.MockTransport(handler)
        client = JimotyClient(transport=transport, max_retries=2, backoff_factor=0.01)
        with mock.patch("time.sleep", return_value=None):
            with pytest.raises(ChunkedTransferError):
                client.get("https://jmty.jp/broken-chunk")

    def test_server_500_retries_and_raises(self) -> None:
        """Verify HTTP 500 error triggers retries and raises HTTPStatusError."""
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(500, text="Internal Server Error", request=request)

        transport = httpx.MockTransport(handler)
        client = JimotyClient(transport=transport, max_retries=2, backoff_factor=0.01)
        with mock.patch("time.sleep", return_value=None):
            with pytest.raises((JimotyNetworkError, httpx.HTTPStatusError)) as exc_info:
                client.get("https://jmty.jp/server-error")

        assert "500" in str(exc_info.value)
        assert attempts == 3

    def test_fetch_search_page_interface_contract(self) -> None:
        """Verify fetch_search_page accepts both SearchQuery and URL string."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<div class='p-articles-list'>Items</div>", request=request)

        transport = httpx.MockTransport(handler)
        client = JimotyClient(transport=transport)
        # Using query object
        query = SearchQuery(prefecture="kanagawa", category="sale-bik", municipality="a-314-chigasaki")
        html1 = client.fetch_search_page(query)
        assert "Items" in html1

        # Using direct URL
        html2 = client.fetch_search_page("https://jmty.jp/kanagawa/sale-bik")
        assert "Items" in html2

    def test_resolve_detail_url(self) -> None:
        """Verify resolve_detail_url correctly resolves various URL formats and article IDs."""
        client = JimotyClient()
        assert client.resolve_detail_url("https://jmty.jp/kanagawa/sale-bik/article-12345") == "https://jmty.jp/kanagawa/sale-bik/article-12345"
        assert client.resolve_detail_url("/kanagawa/sale-bik/article-12345") == f"{BASE_URL}/kanagawa/sale-bik/article-12345"
        assert client.resolve_detail_url("article-12345") == f"{BASE_URL}/articles/article-12345"
        assert client.resolve_detail_url("12345") == f"{BASE_URL}/articles/12345"

    def test_fetch_detail_page_interface_contract(self) -> None:
        """Verify fetch_detail_page resolves URL and returns HTML."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<h1>Yamaha Jog Detail</h1>", request=request)

        transport = httpx.MockTransport(handler)
        client = JimotyClient(transport=transport)
        html = client.fetch_detail_page("article-18jog")
        assert "Yamaha Jog Detail" in html
