"""Configuration and Single Source of Truth (SSOT) constants for jimoty-cli."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# Base URL for Jimoty platform
BASE_URL = "https://jmty.jp"

# Default operational search parameters
DEFAULT_PREFECTURE = "kanagawa"
DEFAULT_MUNICIPALITY = "a-314-chigasaki"
DEFAULT_CATEGORY = "sale-bik"  # Motorcycles (バイク)
DEFAULT_MAX_PRICE = 60000

# Network client defaults
DEFAULT_TIMEOUT = 15.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 1.5
DEFAULT_JITTER_MAX = 0.5

# Modern desktop browser headers for Jimoty SSR
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Known municipality aliases and codes (Shonan / Kanagawa / Kanto)
MUNICIPALITIES: Dict[str, str] = {
    # Shonan & Kanagawa
    "chigasaki": "a-314-chigasaki",
    "茅ヶ崎": "a-314-chigasaki",
    "茅ヶ崎市": "a-314-chigasaki",
    "fujisawa": "a-312-fujisawa",
    "藤沢": "a-312-fujisawa",
    "藤沢市": "a-312-fujisawa",
    "kamakura": "a-311-kamakura",
    "鎌倉": "a-311-kamakura",
    "鎌倉市": "a-311-kamakura",
    "hiratsuka": "a-313-hiratsuka",
    "平塚": "a-313-hiratsuka",
    "平塚市": "a-313-hiratsuka",
    "samukawa": "a-315-samukawa",
    "寒川": "a-315-samukawa",
    "寒川町": "a-315-samukawa",
    "oiso": "a-316-oiso",
    "大磯": "a-316-oiso",
    "大磯町": "a-316-oiso",
    "yokohama": "a-301-yokohama",
    "横浜": "a-301-yokohama",
    "横浜市": "a-301-yokohama",
    "kawasaki": "a-302-kawasaki",
    "川崎": "a-302-kawasaki",
    "川崎市": "a-302-kawasaki",
    "odawara": "a-305-odawara",
    "小田原": "a-305-odawara",
    "小田原市": "a-305-odawara",
    "atsugi": "a-307-atsugi",
    "厚木": "a-307-atsugi",
    "厚木市": "a-307-atsugi",
    "ebina": "a-308-ebina",
    "海老名": "a-308-ebina",
    "海老名市": "a-308-ebina",
}

# Known categories
CATEGORIES: Dict[str, str] = {
    "motorcycle": "sale-bik",
    "bike": "sale-bik",
    "バイク": "sale-bik",
    "bicycle": "sale-bic",
    "自転車": "sale-bic",
    "car": "sale-car",
    "車": "sale-car",
    "auto_parts": "sale-par",
    "パーツ": "sale-par",
    "all": "all",
}


def resolve_proxy(explicit_proxy: Optional[str] = None) -> Optional[str]:
    """
    Resolve proxy URL with separation of sensitive network config from code.
    Priority:
      1. explicit_proxy argument (CLI parameter)
      2. JIMOTY_PROXY environment variable
      3. HTTPS_PROXY / https_proxy
      4. HTTP_PROXY / http_proxy
      5. ALL_PROXY / all_proxy
    Returns None if no proxy is configured.
    """
    if explicit_proxy and explicit_proxy.strip():
        return explicit_proxy.strip()

    proxy_keys = [
        "JIMOTY_PROXY",
        "HTTPS_PROXY",
        "https_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "ALL_PROXY",
        "all_proxy",
    ]
    for key in proxy_keys:
        val = os.getenv(key)
        if val and val.strip():
            return val.strip()

    return None


def resolve_municipality(name_or_code: Optional[str]) -> Optional[str]:
    """Resolve a municipality name, Japanese kanji, or code into Jimoty URL slug."""
    if not name_or_code:
        return None
    cleaned = name_or_code.strip().lower()
    # Check dictionary
    if cleaned in MUNICIPALITIES:
        return MUNICIPALITIES[cleaned]
    if name_or_code.strip() in MUNICIPALITIES:
        return MUNICIPALITIES[name_or_code.strip()]
    # If already formatted as a-XXX-slug
    return name_or_code.strip()


def resolve_category(category_or_name: Optional[str]) -> str:
    """Resolve category name or alias into Jimoty category path."""
    if not category_or_name:
        return DEFAULT_CATEGORY
    cleaned = category_or_name.strip().lower()
    return CATEGORIES.get(cleaned, CATEGORIES.get(category_or_name.strip(), category_or_name.strip()))


@dataclass
class JimotyConfig:
    """Operational configuration container for jimoty-cli."""

    base_url: str = BASE_URL
    default_prefecture: str = DEFAULT_PREFECTURE
    default_municipality: str = DEFAULT_MUNICIPALITY
    default_category: str = DEFAULT_CATEGORY
    default_max_price: Optional[int] = DEFAULT_MAX_PRICE
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR
    headers: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HEADERS))
    proxy: Optional[str] = None

    def __post_init__(self) -> None:
        if self.proxy is None:
            self.proxy = resolve_proxy()

    @classmethod
    def from_env(cls) -> JimotyConfig:
        """Create configuration reading operational defaults and proxies from environment."""
        pref = os.getenv("JIMOTY_PREFECTURE", DEFAULT_PREFECTURE)
        muni = os.getenv("JIMOTY_MUNICIPALITY", DEFAULT_MUNICIPALITY)
        cat = os.getenv("JIMOTY_CATEGORY", DEFAULT_CATEGORY)
        max_p_str = os.getenv("JIMOTY_MAX_PRICE")
        max_p = int(max_p_str) if max_p_str and max_p_str.isdigit() else DEFAULT_MAX_PRICE
        timeout_str = os.getenv("JIMOTY_TIMEOUT")
        timeout = float(timeout_str) if timeout_str else DEFAULT_TIMEOUT
        proxy = resolve_proxy()
        return cls(
            default_prefecture=pref,
            default_municipality=muni,
            default_category=cat,
            default_max_price=max_p,
            timeout=timeout,
            proxy=proxy,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (masking sensitive credentials in proxy)."""
        proxy_display = None
        if self.proxy:
            # Mask user:password if present
            if "@" in self.proxy:
                proto, rest = self.proxy.split("://", 1) if "://" in self.proxy else ("", self.proxy)
                userpass, hostport = rest.split("@", 1)
                user = userpass.split(":", 1)[0]
                proxy_display = f"{proto}://{user}:****@{hostport}" if proto else f"{user}:****@{hostport}"
            else:
                proxy_display = self.proxy

        return {
            "base_url": self.base_url,
            "default_prefecture": self.default_prefecture,
            "default_municipality": self.default_municipality,
            "default_category": self.default_category,
            "default_max_price": self.default_max_price,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "backoff_factor": self.backoff_factor,
            "proxy_configured": bool(self.proxy),
            "proxy": proxy_display,
        }
