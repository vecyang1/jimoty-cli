"""Resilient HTTP client for Jimoty (jmty.jp) with proxy routing, backoff, and error handling."""

from __future__ import annotations

import http.client
import logging
import random
import re
import time
from typing import Any, Dict, Optional, Union
from urllib.parse import urlencode, urljoin

import httpx

from jimoty.config import (
    BASE_URL,
    DEFAULT_BACKOFF_FACTOR,
    DEFAULT_HEADERS,
    DEFAULT_JITTER_MAX,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    JimotyConfig,
    resolve_category,
    resolve_municipality,
    resolve_proxy,
)
from jimoty.models import SearchQuery

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class JimotyError(Exception):
    """Base exception for all Jimoty operations."""


class JimotyNetworkError(JimotyError):
    """Base exception for network and transport failures."""


class RateLimitError(JimotyNetworkError):
    """Raised when HTTP 429 (Too Many Requests) is encountered and retries are exhausted."""


class BlockedError(JimotyNetworkError):
    """Raised when HTTP 403 (Forbidden / WAF / Geo-blocking) is returned by Jimoty."""


class ListingNotFoundError(JimotyError):
    """Raised when a listing returns HTTP 404 Not Found."""


class ChunkedTransferError(JimotyNetworkError):
    """Raised when chunked transfer IncompleteRead occurs during streaming."""


class ProxyError(JimotyNetworkError):
    """Raised when connecting through the configured proxy fails."""


# ---------------------------------------------------------------------------
# URL Builder Helpers
# ---------------------------------------------------------------------------


def build_search_url(
    query: Optional[SearchQuery] = None,
    prefecture: Optional[str] = None,
    category: Optional[str] = None,
    municipality: Optional[str] = None,
    keyword: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    page: Optional[int] = None,
    sort: Optional[str] = None,
    base_url: str = BASE_URL,
) -> str:
    """
    Construct a canonical Jimoty search URL according to Jimoty routing rules.

    Routing rules:
      - Prefecture only: `/{prefecture}`
      - Prefecture + Category: `/{prefecture}/{category}`
      - Prefecture + Category + Municipality: `/{prefecture}/{category}/g-all/{municipality}`
      - Motorcycle category is `sale-bik`
      - Municipality URLs require `/g-all/`: e.g. `/kanagawa/sale-bik/g-all/a-314-chigasaki`
      - Query params: `keyword`, `min_price`, `max_price`, `page`, `sort`
    """
    if query is not None:
        p = query.prefecture or prefecture or "kanagawa"
        c = query.category or category or "sale-bik"
        m = query.municipality if query.municipality is not None else municipality
        k = query.keyword if query.keyword is not None else keyword
        min_p = query.min_price if query.min_price is not None else min_price
        max_p = query.max_price if query.max_price is not None else max_price
        pg = query.page if query.page is not None else (page or 1)
        s = query.sort if query.sort is not None else sort
    else:
        p = prefecture or "kanagawa"
        c = category or "sale-bik"
        m = municipality
        k = keyword
        min_p = min_price
        max_p = max_price
        pg = page or 1
        s = sort

    # Clean and resolve
    p = p.strip().lower()
    c = resolve_category(c)
    m = resolve_municipality(m)

    # Build path
    # Category "all" or specific
    cat_segment = c if c and c != "all" else ""

    if m and cat_segment:
        path = f"/{p}/{cat_segment}/g-all/{m}"
    elif m and not cat_segment:
        path = f"/{p}/all/g-all/{m}"
    elif cat_segment:
        path = f"/{p}/{cat_segment}"
    else:
        path = f"/{p}"

    # Build query params
    params: Dict[str, Any] = {}
    if k and str(k).strip():
        params["keyword"] = str(k).strip()
    if min_p is not None:
        params["min_price"] = int(min_p)
    if max_p is not None:
        params["max_price"] = int(max_p)
    if pg and int(pg) > 1:
        params["page"] = int(pg)
    if s and str(s).strip():
        params["sort"] = str(s).strip()

    full_url = urljoin(base_url, path)
    if params:
        query_string = urlencode(params)
        full_url = f"{full_url}?{query_string}"

    return full_url


# ---------------------------------------------------------------------------
# JimotyClient
# ---------------------------------------------------------------------------


class JimotyClient:
    """
    Production-grade HTTP client for Jimoty with proxy routing, backoff,
    and resilience against CDN rate-limits and chunked transfer errors.
    """

    def __init__(
        self,
        config: Optional[JimotyConfig] = None,
        proxy: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        headers: Optional[Dict[str, str]] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.config = config or JimotyConfig.from_env()
        self.proxy = resolve_proxy(proxy or self.config.proxy)
        self.timeout = timeout if timeout is not None else self.config.timeout
        self.max_retries = max_retries if max_retries is not None else self.config.max_retries
        self.backoff_factor = backoff_factor if backoff_factor is not None else self.config.backoff_factor
        self.headers = dict(headers or self.config.headers)
        self._transport = transport
        self._session: Optional[httpx.Client] = None

    def _create_session(self, proxy_override: Optional[str] = None) -> httpx.Client:
        """Create a new httpx.Client with configured proxy and headers."""
        target_proxy = proxy_override or self.proxy
        kwargs: Dict[str, Any] = {
            "headers": self.headers,
            "timeout": httpx.Timeout(self.timeout),
            "follow_redirects": True,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        elif target_proxy:
            kwargs["proxy"] = target_proxy

        return httpx.Client(**kwargs)

    @property
    def session(self) -> httpx.Client:
        """Return cached or new session."""
        if self._session is None or self._session.is_closed:
            self._session = self._create_session()
        return self._session

    def close(self) -> None:
        """Close active session and release network resources."""
        if self._session and not self._session.is_closed:
            self._session.close()
            self._session = None

    def __enter__(self) -> JimotyClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _sleep_backoff(self, attempt: int, response: Optional[httpx.Response] = None) -> None:
        """Calculate and execute exponential backoff with jitter or Retry-After."""
        if response is not None and "retry-after" in response.headers:
            retry_after = response.headers["retry-after"]
            try:
                delay = float(retry_after)
                logger.warning("Rate limit Retry-After header detected: sleeping for %.1f seconds", delay)
                time.sleep(delay)
                return
            except ValueError:
                pass

        jitter = random.uniform(0.1, DEFAULT_JITTER_MAX)
        delay = (self.backoff_factor * (2 ** attempt)) + jitter
        logger.warning("Retrying request (attempt %d/%d) after %.2fs delay", attempt + 1, self.max_retries, delay)
        time.sleep(delay)

    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        proxy: Optional[str] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Execute an HTTP request with automatic retry on 429, 5xx, and chunked IncompleteRead.
        Handles HTTP 403 with informative diagnostic error.
        """
        resolved_req_proxy = resolve_proxy(proxy) if proxy else self.proxy
        # If per-request proxy differs from client default, create dedicated client
        client_to_use = self._create_session(resolved_req_proxy) if proxy else self.session

        last_exception: Optional[Exception] = None
        response: Optional[httpx.Response] = None

        for attempt in range(self.max_retries + 1):
            try:
                response = client_to_use.request(method, url, params=params, **kwargs)

                # Check HTTP status codes
                if response.status_code == 200:
                    return response

                if response.status_code == 404:
                    raise ListingNotFoundError(f"Jimoty page not found (HTTP 404): {url}")

                if response.status_code == 403:
                    raise BlockedError(
                        f"Access forbidden (HTTP 403) for {url}. "
                        "Jimoty may be geo-blocking your IP address or challenging your user agent. "
                        "Please configure a Japanese residential proxy via --proxy or JIMOTY_PROXY."
                    )

                if response.status_code == 429:
                    if attempt < self.max_retries:
                        self._sleep_backoff(attempt, response)
                        continue
                    raise RateLimitError(
                        f"HTTP 429 Too Many Requests from Jimoty for {url} after {self.max_retries} retries."
                    )

                if response.status_code in (500, 502, 503, 504):
                    if attempt < self.max_retries:
                        self._sleep_backoff(attempt, response)
                        continue
                    response.raise_for_status()

                response.raise_for_status()
                return response

            except (BlockedError, ListingNotFoundError, RateLimitError):
                # Don't retry fatal 403 or 404, or re-raised RateLimitError
                raise

            except (
                httpx.RemoteProtocolError,
                httpx.ReadError,
                http.client.IncompleteRead,
                ChunkedTransferError,
            ) as e:
                # Chunked transfer IncompleteRead / protocol interruption
                last_exception = ChunkedTransferError(
                    f"Chunked transfer IncompleteRead or protocol error for {url}: {e}"
                )
                if attempt < self.max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise last_exception from e

            except (httpx.ProxyError, httpx.ConnectError) as e:
                err_str = str(e).lower()
                if "proxy" in err_str or resolved_req_proxy:
                    last_exception = ProxyError(f"Proxy error connecting to {url} via {resolved_req_proxy}: {e}")
                else:
                    last_exception = JimotyNetworkError(f"Connection error to {url}: {e}")

                if attempt < self.max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise last_exception from e

            except httpx.TimeoutException as e:
                last_exception = JimotyNetworkError(f"Request timeout connecting to {url}: {e}")
                if attempt < self.max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise last_exception from e

            except httpx.HTTPStatusError as e:
                last_exception = JimotyNetworkError(f"HTTP error {e.response.status_code} for {url}: {e}")
                if attempt < self.max_retries:
                    self._sleep_backoff(attempt, e.response)
                    continue
                raise last_exception from e

            except Exception as e:
                last_exception = JimotyNetworkError(f"Unexpected network failure for {url}: {e}")
                if attempt < self.max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise last_exception from e

            finally:
                if proxy and client_to_use is not self.session:
                    client_to_use.close()

        if last_exception:
            raise last_exception
        if response is not None:
            response.raise_for_status()
            return response

        raise JimotyNetworkError(f"Failed to fetch {url} after {self.max_retries} attempts.")

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        proxy: Optional[str] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Perform a GET request with resilient retries."""
        return self.request("GET", url, params=params, proxy=proxy, **kwargs)

    def build_search_url(self, query: SearchQuery) -> str:
        """Build search URL from a SearchQuery instance."""
        return build_search_url(query, base_url=self.config.base_url)

    def fetch_search_html(self, query: SearchQuery, proxy: Optional[str] = None) -> str:
        """Fetch search results page HTML for the given SearchQuery."""
        url = self.build_search_url(query)
        logger.info("Fetching search HTML: %s", url)
        response = self.get(url, proxy=proxy)
        return response.text

    def fetch_search_page(self, query_or_url: Union[SearchQuery, str], proxy: Optional[str] = None) -> str:
        """Fetch search results page HTML by query or URL (interface contract alias)."""
        if isinstance(query_or_url, SearchQuery):
            return self.fetch_search_html(query_or_url, proxy=proxy)
        logger.info("Fetching search HTML from URL: %s", query_or_url)
        return self.get(query_or_url, proxy=proxy).text

    def resolve_detail_url(self, url_or_key: str) -> str:
        """Resolve a listing ID, path, or URL into a canonical full detail URL."""
        cleaned = url_or_key.strip()
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned
        if cleaned.startswith("/"):
            return urljoin(self.config.base_url, cleaned)
        # If it is e.g. "article-1abcde" or "1abcde"
        return urljoin(self.config.base_url, f"/articles/{cleaned}")

    def fetch_detail_html(self, url_or_key: str, proxy: Optional[str] = None) -> str:
        """Fetch detail page HTML for a given listing URL or article key."""
        target_url = self.resolve_detail_url(url_or_key)
        logger.info("Fetching detail HTML: %s", target_url)
        response = self.get(target_url, proxy=proxy)
        return response.text

    def fetch_detail_page(self, url_or_key: str, proxy: Optional[str] = None) -> str:
        """Fetch detail page HTML by URL or key (interface contract alias)."""
        return self.fetch_detail_html(url_or_key, proxy=proxy)
