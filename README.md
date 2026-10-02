# jimoty-cli

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-100%2F100%20passing-brightgreen.svg)]()

> **Agent-native CLI tool and reusable Python library for searching, scraping, monitoring, and evaluating vehicle and goods listings on Japan's Jimoty (`jmty.jp`) platform.**

`jimoty-cli` provides an end-to-end toolkit designed for autonomous agents and engineers to navigate Japanese local C2C transactions with high confidence: SSR and Next.js embedded `__NEXT_DATA__` extraction, deterministic safety and paperwork scam triage, polite Japanese communication template generation (`敬語`), on-site physical pickup inspection checklists, and residential proxy routing.

---

## Table of Contents

- [Key Features](#key-features)
- [Architecture & Layers](#architecture--layers)
- [Installation](#installation)
- [Quickstart CLI Guide](#quickstart-cli-guide)
  - [1. Searching Listings (`search`)](#1-searching-listings-search)
  - [2. Inspecting Details (`get`)](#2-inspecting-details-get)
  - [3. Deterministic Safety Triage (`diagnose`)](#3-deterministic-safety-triage-diagnose)
  - [4. Japanese Inquiry Messages (`template`)](#4-japanese-inquiry-messages-template)
  - [5. Physical On-Site Inspection Checklist (`checklist`)](#5-physical-on-site-inspection-checklist-checklist)
  - [6. Operational Configuration (`config`)](#6-operational-configuration-config)
- [Python SDK Usage](#python-sdk-usage)
  - [Search & Extraction](#search--extraction)
  - [Running Diagnostics](#running-diagnostics)
  - [Generating Templates & Checklists](#generating-templates--checklists)
- [Diagnostic Rule Catalog](#diagnostic-rule-catalog)
- [Network Resilience & Proxy Routing](#network-resilience--proxy-routing)
- [Testing](#testing)
- [License](#license)

---

## Key Features

- **SSR & `__NEXT_DATA__` Ingestion**: Extracts 100% structured data from Next.js `<script id="__NEXT_DATA__">` JSON payloads without headless browser overhead, with resilient BeautifulSoup fallback for non-Next.js pages.
- **Deterministic Diagnostic Engine**: Rule-based triage system scoring items (0–100) and assigning explicit verdicts (`RECOMMENDED`, `CAUTION`, `FATAL_REJECT`). Detects stolen bike risks (`書類なし`), engine seizures (`不動 / 焼き付き`), powertrain classification (4-stroke FI vs 2-stroke carb), and seller verification (`本人確認済`).
- **Cultural Communication Engine**: Generates polite keigo (`敬語`) marketplace inquiry messages for in-person direct pickup (`直接引き取り`), document verification, and appointment scheduling.
- **Physical Inspection Checklist**: Comprehensive on-site physical inspection checklist (cold start, VIN matching, front fork seals, tire wear, electricals) exportable in Terminal, Markdown, or JSON formats.
- **Network Resilience**: Handles CloudFront 403 geo-blocking via Japanese residential proxies (`JIMOTY_PROXY` / `--proxy`), recovers automatically from chunked transfer `IncompleteRead`, and applies exponential backoff with jitter on HTTP 429.
- **Dual Interface**: Full CLI commands (`jimoty` and `jimoty-cli`) and exportable Python library (`import jimoty`).

---

## Architecture & Layers

```
jimoty-cli
├── Network Layer (jimoty.client)
│   ├── Httpx Client with Desktop Headers & ja-JP Locale
│   ├── Resilient Retry (HTTP 429 Backoff, Chunked Transfer IncompleteRead Recovery)
│   └── Proxy Adapter (JIMOTY_PROXY / HTTPS_PROXY / --proxy)
├── Parser Layer (jimoty.parser)
│   ├── Search Listing Parser (p-articles-list-item SSR cards)
│   ├── __NEXT_DATA__ Extractor (props.pageProps.articleResults.article)
│   └── HTML Fallback Parser (BeautifulSoup)
├── Diagnostic & Triage Engine (jimoty.diagnostics)
│   ├── Document & Legal Audit (DOC-001, DOC-002, DOC-003)
│   ├── Mechanical Condition Triage (MECH-001, MECH-002, MECH-003, MECH-004)
│   ├── Powertrain Classification (ENG-001, ENG-002)
│   ├── Seller Integrity Score (SELLER-001, SELLER-002, SELLER-003)
│   └── Deterministic Scoring & Verdicts (RECOMMENDED, CAUTION, FATAL_REJECT)
├── Cultural Comms & Safety (jimoty.templates, jimoty.checklist)
│   ├── Japanese Keigo Inquiry Templates (initial, paperwork, schedule)
│   └── Physical On-Site Inspection Checklist (cold start, lights, tires, VIN match)
└── Operational Layer (jimoty.config, jimoty.cli)
    ├── Single Source of Truth (SSOT) Defaults & Municipality Aliases
    └── CLI Subcommands (search, get, diagnose, template, checklist, config)
```

---

## Installation

### From Source (Editable Mode)

```bash
git clone https://github.com/vecyang1/vec-skills.git
cd vec-skills/skills/jimoty-cli
pip install -e .
```

### With Test Dependencies

```bash
pip install -e ".[test]"
```

Both `jimoty` and `jimoty-cli` binary commands will be installed into your Python environment.

---

## Quickstart CLI Guide

### 1. Searching Listings (`search`)

Search Jimoty listings with automatic municipality code resolution, price bounds, and keywords:

```bash
# Search 50cc scooters in Chigasaki under 50,000 JPY
jimoty search -m chigasaki -k "原付" -p 50000

# Search by Japanese municipality name and output structured JSON
jimoty search -m 茅ヶ崎市 -k "ジョグ" -p 60000 --json

# Search Fujisawa with custom category and limit
jimoty search -m fujisawa --category bicycle --limit 5
```

Supported municipality aliases include `chigasaki` (`茅ヶ崎市`, `a-314-chigasaki`), `fujisawa` (`藤沢市`, `a-312-fujisawa`), `kamakura` (`鎌倉市`, `a-311-kamakura`), `hiratsuka` (`平塚市`, `a-313-hiratsuka`), `yokohama` (`横浜市`, `a-301-yokohama`), `kawasaki` (`川崎市`, `a-302-kawasaki`), etc.

### 2. Inspecting Details (`get`)

Fetch and parse structured item details, images, seller profile, and ratings:

```bash
# Fetch live listing by URL
jimoty get https://jmty.jp/kanagawa/sale-bik/article-18jog

# Fetch using local HTML fixture
jimoty get tests/fixtures/detail_4st_fi_jog.html

# Fetch formatted as JSON
jimoty get tests/fixtures/detail_4st_fi_jog.html --json
```

### 3. Deterministic Safety Triage (`diagnose`)

Run the rule-based diagnostic engine against a listing URL or local HTML file:

```bash
# Terminal summary table
jimoty diagnose tests/fixtures/detail_4st_fi_jog.html

# Machine-readable JSON output (ideal for automated agent pipelines)
jimoty diagnose tests/fixtures/detail_junk_no_papers.html --json
```

Example JSON diagnostic output:
```json
{
  "item_id": "article-junk",
  "title": "Junk Scooter - 不動 書類なし",
  "price": 8000,
  "verdict": "FATAL_REJECT",
  "score": 15,
  "fatal_flags": [
    "【致命的欠陥】廃車証明書・譲渡証明書等の登録書類が欠落しているか再登録不可です（盗難車の可能性または公道走行不可）。",
    "【致命的欠陥】エンジン不動・焼き付き・ジャンク品と明記されています（走行不可）。"
  ],
  "warning_flags": [
    "【警告】出品者の本人確認が未完了です。"
  ],
  "info_flags": [],
  "rules_evaluated": [
    {
      "rule_id": "DOC-001-MISSING_PAPERS",
      "name": "登録書類欠落・盗難リスク検査",
      "passed": false,
      "severity": "FATAL",
      "message": "登録書類がありません。"
    }
  ],
  "summary": "判定: FATAL_REJECT (スコア: 15/100) - 致命的欠陥が検出されました。購入は推奨されません。"
}
```

### 4. Japanese Inquiry Messages (`template`)

Generate context-aware, respectful Japanese keigo (`敬語`) messages for marketplace communication:

```bash
# 1. Initial direct pickup inquiry
jimoty template tests/fixtures/detail_4st_fi_jog.html --type initial --buyer-name "田中"

# 2. Document & key count verification
jimoty template tests/fixtures/detail_4st_fi_jog.html --type paperwork

# 3. Schedule coordination for meetup & inspection
jimoty template tests/fixtures/detail_4st_fi_jog.html --type schedule --date "今週土曜日 14:00"
```

### 5. Physical On-Site Inspection Checklist (`checklist`)

Generate a 5-category safety checklist to guard against defects during in-person pickup:

```bash
# Terminal formatted checklist
jimoty checklist tests/fixtures/detail_4st_fi_jog.html

# Markdown formatted checklist (save for mobile inspection notes)
jimoty checklist tests/fixtures/detail_4st_fi_jog.html --format markdown > inspection.md

# Raw JSON inspection checklist
jimoty checklist --json
```

### 6. Operational Configuration (`config`)

Inspect the Single Source of Truth (SSOT) configuration and verify proxy resolution:

```bash
# Display all operational parameters
jimoty config

# Query single configuration parameter
jimoty config get --key default_municipality

# Output configuration as JSON
jimoty config --json
```

---

## Python SDK Usage

`jimoty` is fully importable as a Python library:

### Search & Extraction

```python
from jimoty.client import JimotyClient
from jimoty.config import JimotyConfig
from jimoty.models import SearchQuery
from jimoty.parser import parse_search_page, parse_detail_page

config = JimotyConfig(default_municipality="a-314-chigasaki", default_max_price=50000)
client = JimotyClient(config=config)

query = SearchQuery(
    prefecture="kanagawa",
    municipality="a-314-chigasaki",
    keyword="原付",
    max_price=50000,
)

# Fetch and parse search results
html = client.fetch_search_html(query)
listings = parse_search_page(html)

for item in listings:
    print(f"[{item.id}] {item.title} - {item.price_text} ({item.location_text})")
```

### Running Diagnostics

```python
from jimoty.diagnostics import DiagnosticEngine
from jimoty.parser import parse_detail_page

detail = parse_detail_page(open("detail.html").read())
engine = DiagnosticEngine()
report = engine.diagnose(detail)

print(f"Verdict: {report.verdict.value}")
print(f"Score:   {report.score}/100")
print(f"Summary: {report.summary}")

if report.fatal_flags:
    print("Fatal Flags:")
    for flag in report.fatal_flags:
        print(f" - {flag}")
```

### Generating Templates & Checklists

```python
from jimoty.templates import generate_inquiry_template
from jimoty.checklist import get_pickup_checklist, render_checklist_markdown

# Generate inquiry
msg = generate_inquiry_template(detail, template_type="initial", buyer_name="山田")
print(msg)

# Generate inspection checklist
items = get_pickup_checklist(detail)
md_checklist = render_checklist_markdown(items, detail)
print(md_checklist)
```

---

## Diagnostic Rule Catalog

| Rule ID | Category | Severity | Description & Conditions |
|---------|----------|----------|--------------------------|
| `DOC-001-MISSING_PAPERS` | Legal | **FATAL** | Flags `書類なし`, `書類紛失`, `登録不可`, `盗難車` risks. Triggers `FATAL_REJECT`. |
| `DOC-002-NO_KEYS` | Legal | WARNING | Flags missing keys (`鍵なし`, `キー欠品`), requiring replacement cylinders. |
| `DOC-003-VALID_PAPERS` | Legal | INFO / WARNING | Confirms presence of official papers (`廃車申告受付書`, `譲渡証明書`). Warns if unmentioned. |
| `MECH-001-ENGINE_SEIZED` | Mechanical | **FATAL** | Flags seized engines (`焼き付き`, `クランク固着`, `キック降りない`). |
| `MECH-002-NON_RUNNING` | Mechanical | **FATAL** | Flags non-running vehicles (`不動`, `ジャンク`, `部品取り`). |
| `MECH-003-RUNNING_CONFIRMED` | Mechanical | INFO | Boosts score when confirmed running (`実動`, `セル一発`, `キック一発`). |
| `MECH-004-BATTERY_ISSUE` | Mechanical | WARNING | Warns on drained battery (`バッテリー上がり`), manageable low-cost fix. |
| `ENGINE-ENG-001-4S_FI` | Powertrain | INFO | Identifies modern, reliable 4-stroke Electronic Fuel Injection (4スト FI). |
| `ENGINE-ENG-002-2S_CARB` | Powertrain | INFO | Identifies 2-stroke carbureted engine requiring 2T oil and seasonal carb maintenance. |
| `SELLER-001-VERIFIED_ID` | Seller | INFO / WARNING | Audits Jimoty verified identity badge (`本人確認済`). Flags unverified sellers. |
| `SELLER-002-RATING_RATIO` | Seller | INFO / WARNING | Evaluates positive/negative rating ratios (penalizes high bad rating percentage). |
| `SELLER-003-UNVERIFIED_SUSPICIOUS` | Seller | WARNING | Flags unverified sellers with zero or poor transaction history. |

---

## Network Resilience & Proxy Routing

Jimoty (`jmty.jp`) enforces strict CloudFront rate limiting and geo-blocking against non-Japanese IP ranges. `jimoty-cli` has built-in network fault tolerance:

### Japanese Residential Proxy

Configure proxy resolution via environment variable or CLI argument:

```bash
# Environment variable (Highest precedence)
export JIMOTY_PROXY="http://user:password@proxy.example.com:8080"

# CLI argument override
jimoty search -m chigasaki --proxy "http://127.0.0.1:1080"
```

The client automatically masks sensitive credentials when logging or displaying configuration via `jimoty config`.

### Chunked Transfer Recovery

Jimoty servers occasionally terminate HTTP chunked transfer responses prematurely. `JimotyClient` catches `httpcore.RemoteProtocolError` / `httpx.ReadError` (`IncompleteRead`), executing up to 3 automatic retries with exponential backoff and jitter.

### HTTP 429 Rate Limiting Backoff

When receiving HTTP 429 Too Many Requests, `JimotyClient` parses `Retry-After` headers and applies exponential backoff (`backoff_factor=1.5`) before retrying.

---

## Testing

The test suite contains 100 comprehensive tests with 100% pass rate:

```bash
# Run all tests
python3 -m pytest -v tests

# Run specific module tests
python3 -m pytest -v tests/test_diagnostics.py
python3 -m pytest -v tests/test_parser.py
python3 -m pytest -v tests/test_client.py
python3 -m pytest -v tests/test_e2e.py
```

All test cases run fully offline using realistic recorded fixtures in `tests/fixtures/`.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
