"""Pytest configuration, shared fixtures, and mock factories for jimoty-cli test suite."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Generator
import pytest

# Ensure skill package directory is on Python search path
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return absolute Path to the fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def search_bikes_html(fixtures_dir: Path) -> str:
    """Raw HTML content of Chigasaki motorcycle search listings page."""
    path = fixtures_dir / "search_chigasaki_bikes.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def detail_jog_html(fixtures_dir: Path) -> str:
    """Raw HTML content of healthy 4-stroke FI Yamaha Jog detail page."""
    path = fixtures_dir / "detail_4st_fi_jog.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def detail_junk_html(fixtures_dir: Path) -> str:
    """Raw HTML content of non-running junk motorcycle without paperwork."""
    path = fixtures_dir / "detail_junk_no_papers.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def detail_lets2_html(fixtures_dir: Path) -> str:
    """Raw HTML content of 2-stroke carbureted Suzuki Let's 2 scooter."""
    path = fixtures_dir / "detail_2st_carb_lets2.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def detail_fallback_html(fixtures_dir: Path) -> str:
    """Raw HTML content of detail page without __NEXT_DATA__ for fallback parsing."""
    path = fixtures_dir / "detail_fallback_no_next_data.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def next_data_samples(fixtures_dir: Path) -> Dict[str, Any]:
    """Parsed JSON dictionary of edge-case Next.js article payloads."""
    path = fixtures_dir / "next_data_samples.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def clean_proxy_env() -> Generator[None, None, None]:
    """Temporary context manager ensuring proxy environment variables are clean."""
    proxy_vars = [
        "JIMOTY_PROXY",
        "HTTPS_PROXY",
        "https_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "ALL_PROXY",
        "all_proxy",
    ]
    saved = {k: os.environ.get(k) for k in proxy_vars}
    for k in proxy_vars:
        if k in os.environ:
            del os.environ[k]
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
            elif k in os.environ:
                del os.environ[k]
