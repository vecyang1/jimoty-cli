---
name: jimoty-cli
description: Agent-native CLI tool and Python capability for searching, scraping, monitoring, and evaluating vehicle and goods listings on Japan's Jimoty (jmty.jp) platform. Features SSR and __NEXT_DATA__ extraction, deterministic safety/scam diagnostic triage, polite Japanese marketplace inquiry templates, on-site physical inspection checklists, and residential proxy routing.
triggers:
  - search Jimoty listings or scrape jmty.jp
  - find used 50cc scooters, mopeds (原付), motorcycles (バイク), bicycles, or vehicles in Japan
  - search Shonan, Kanagawa, Chigasaki, Fujisawa, Kamakura listings on Jimoty
  - diagnose vehicle listings for missing paperwork (書類なし), stolen bike risks, or engine seizure (不動 / 焼き付き)
  - audit seller identity verification status (本人確認済) and ratings
  - generate polite Japanese marketplace inquiry messages (敬語 / 直接引き取り)
  - prepare on-site physical vehicle pickup safety checklist (cold start, lights, tire wear, frame, VIN check)
  - configure Japanese residential proxy or troubleshoot Jimoty CloudFront 403 / 429 errors
---

# Jimoty CLI & Capability (`jimoty-cli`)

## 1. Overview & Platform Context

**Jimoty (`jmty.jp` / ジモティー)** is Japan's premier local classifieds bulletin board (クラシファイドサービス), centered on community-level transactions, in-person pickups (**直接引き取り**), and zero-commission secondhand goods.

The vehicle segment (motorcycles `バイク`, mopeds `原付`, motorized bicycles `原動機付自転車`, and cars `中古車`) represents one of Jimoty's highest-volume, highest-savings categories, but it is accompanied by distinct operational and cultural nuances:

1. **Local Direct Transfer (直接引き取り)**: Unlike Mercari or Yahoo Auctions, transactions on Jimoty predominantly occur in person. Buyers travel to the seller's location, inspect the vehicle, exchange cash, and load it into a van/truck or ride it home.
2. **Paperwork & Legal Registration**: Japanese municipal mopeds (<50cc / <125cc) require specific deregistration paperwork (**廃車申告受付書**) and transfer certificate (**譲渡証明書**) with the seller's seal/signature. Purchasing a bike marked "書類なし" (no paperwork) carries severe legal risk, including possession of stolen property (**盗難車リスク**) or impossibility of municipal registration.
3. **Mechanical Diversity**: Listings span well-maintained 4-stroke Electronic Fuel Injection (4スト FI) daily commuters, vintage 2-stroke carbureted bikes requiring premix/2T oil, and non-running project bikes labeled "不動" (non-running) or "部品取り" (parts only).
4. **Cultural Etiquette (Keigo & Trust)**: Polite Japanese (`敬語`), prompt appointment confirmations, and respect for seller time are essential. Unverified accounts or rude phrasing frequently result in rejected inquiries.

`jimoty-cli` equips autonomous agents and developers with the tools to safely query, extract, triage, and execute transactions on Jimoty without human trial-and-error.

---

## 2. When to Use & Triggers

Activate `jimoty-cli` whenever a task involves:
- **Listing Search**: Retrieving live items by prefecture, municipality slug (e.g. `a-314-chigasaki`), category (`sale-bik`), keywords, and price ceiling.
- **Deep Extraction**: Scraping complete structured item schemas, images, timestamps, and seller profiles from Next.js embedded `<script id="__NEXT_DATA__">` JSON.
- **Safety & Scam Diagnostics**: Running deterministic evaluations to immediately flag fatal defects ("書類なし", "不動", "焼き付き") or assign `RECOMMENDED` status.
- **Buyer Communication**: Generating culturally appropriate Japanese messages for initial contact, document verification, or meetup logistics.
- **Physical Pickup Guarding**: Generating step-by-step physical inspection checklists (cold start test, light checks, VIN stamping verification).
- **Geo-Routing & Proxies**: Overcoming Jimoty's CloudFront geo-blocking and rate limits using Japanese residential proxies.

---

## 3. CLI Command Reference

The command-line tool is accessible as both `jimoty` and `jimoty-cli`.

### Command Overview
```
jimoty [--version] [-h] <subcommand> [options]

Subcommands:
  search      Search Jimoty listings with SSR HTML parsing, municipality codes, and price filters
  get         Retrieve full structured details for a specific listing URL, article ID, or HTML file
  diagnose    Run deterministic diagnostic triage auditing legal paperwork, mechanics, and seller trust
  photos      List high-res photo URLs, discover external media (YouTube/Google Drive), or download offline
  seller      Audit seller identity (ID/SMS badges), transaction policy, and recent buyer reviews
  watch       Continuously monitor search results for new listings, running automated diagnostic triage
  template    Generate culturally polite Japanese inquiry messages tailored to the listing
  checklist   Generate physical on-site inspection safety checklist for vehicle pickup
  config      Display or query operational configuration defaults (SSOT) and masked proxy
```

---

### Subcommand 1: `search`

Searches listings matching municipality, category, price, and keywords.

```bash
# Search 50cc scooters in Chigasaki under 50,000 JPY
jimoty search -m a-314-chigasaki -k "原付" -p 50000

# Search using Japanese municipality name and output structured JSON
jimoty search -m "茅ヶ崎市" -k "ジョグ" -p 60000 --json

# Limit results and specify custom category (bicycle, car, parts)
jimoty search -m "藤沢市" --category bicycle --limit 5

# Search with proxy override
jimoty search -m chigasaki --proxy "http://127.0.0.1:1080"
```

**Options:**
- `-k, --keyword KEYWORD`: Search keyword (e.g. `原付 50cc`, `トゥデイ`, `レッツ`).
- `-m, --municipality MUNICIPALITY`: Municipality code or Japanese name (default: `a-314-chigasaki`). Supports aliases: `chigasaki`, `茅ヶ崎市`, `fujisawa`, `藤沢市`, `kamakura`, `鎌倉市`, `hiratsuka`, `平塚市`, `yokohama`, `横浜市`, etc.
- `--prefecture PREFECTURE`: Target prefecture (default: `kanagawa`).
- `--category CATEGORY`: Category slug or alias (default: `sale-bik`, supports `bike`, `bicycle`, `car`, `parts`).
- `-p, --max-price MAX_PRICE`: Maximum price ceiling in JPY (default: `60000`).
- `--min-price MIN_PRICE`: Minimum price floor in JPY.
- `--limit LIMIT`: Maximum number of results to display.
- `--sort SORT`: Sort order (`price_asc`, `price_desc`, `date_desc`).
- `--json`: Output structured JSON array.
- `--proxy PROXY`: HTTP/HTTPS or residential proxy URL override.

---

### Subcommand 2: `get`

Fetches and parses complete structured details for a listing from live URL, article ID, or local HTML fixture.

```bash
# Fetch live listing by URL
jimoty get https://jmty.jp/kanagawa/sale-bik/article-18jog

# Fetch using local HTML fixture
jimoty get tests/fixtures/detail_4st_fi_jog.html

# Fetch formatted as raw JSON dictionary
jimoty get tests/fixtures/detail_4st_fi_jog.html --json
```

---

### Subcommand 3: `diagnose`

Audits a listing against legal, mechanical, powertrain, and seller trust rules, outputting a score (0–100) and verdict (`RECOMMENDED`, `CAUTION`, `FATAL_REJECT`).

```bash
# Terminal summary table with flags and rule evaluation
jimoty diagnose tests/fixtures/detail_4st_fi_jog.html

# Full machine-readable JSON report for agent reasoning
jimoty diagnose tests/fixtures/detail_junk_no_papers.html --json
```

**Example JSON Response:**
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

---

### Subcommand 4: `photos`

Inspects high-resolution images (`large_url`, `slide_url`), discovers linked video demonstrations (YouTube) or external cloud condition albums (Google Drive), and downloads photos offline for condition evaluation.

```bash
# List all photo URLs and external video/cloud albums
jimoty photos https://jmty.jp/kanagawa/sale-bik/article-1s8b3o

# Download all photos into a local directory for detailed offline visual inspection
jimoty photos https://jmty.jp/kanagawa/sale-bik/article-1s8b3o --download-dir ./bike_photos

# Output photo metadata and media links as JSON
jimoty photos https://jmty.jp/kanagawa/sale-bik/article-1s8b3o --json
```

---

### Subcommand 5: `seller`

Audits seller trustworthiness dossier, including verified government identity badges (`本人確認済`), SMS authentication status (`電話番号認証済`), rating breakdown (good/normal/bad), seller bio policy (pickup hours, delivery availability, no claims), and recent buyer evaluations.

```bash
# Display terminal formatted seller reputation dossier
jimoty seller https://jmty.jp/kanagawa/sale-bik/article-1s8b3o

# Output seller dossier as structured JSON
jimoty seller https://jmty.jp/kanagawa/sale-bik/article-1s8b3o --json
```

---

### Subcommand 6: `watch`

Continuous real-time monitoring daemon that periodically polls search queries, tracks seen article IDs, and automatically executes diagnostic triage on new arrivals.

```bash
# One-shot monitor pass over Chigasaki scooters under 60,000 JPY
jimoty watch --municipality chigasaki --max-price 60000 --once

# Continuous live daemon polling every 30s
jimoty watch --municipality chigasaki --max-price 50000 --interval 30
```

---

### Subcommand 7: `template`

Generates culturally idiomatic Japanese inquiry messages (`敬語`) tailored to the specific seller, vehicle, price, and location. Automatically adapts to late-night courtesy greetings (`夜分遅くに恐れ入ります`) and stale listing inquiry (`まだお手元にございますでしょうか`).

```bash
# 1. Initial direct pickup inquiry
jimoty template tests/fixtures/detail_4st_fi_jog.html --type initial --buyer-name "田中"

# 2. Document & key count verification
jimoty template tests/fixtures/detail_4st_fi_jog.html --type paperwork

# 3. Schedule coordination for meetup & inspection
jimoty template tests/fixtures/detail_4st_fi_jog.html --type schedule --date "今週土曜日 14:00"

# Output as JSON
jimoty template tests/fixtures/detail_4st_fi_jog.html --type initial --json
```

**Template Types:**
- `initial`: Courteous initial contact expressing interest in buying/taking over with direct in-person pickup (`直接引き取り`).
- `paperwork`: Detailed verification of registration papers (`廃車申告受付書`, `譲渡証明書`), key count, and mechanical condition.
- `schedule`: Clear date, time, and location coordination for in-person meetup.

---

### Subcommand 8: `checklist`

Generates an on-site physical vehicle pickup safety checklist guarding the buyer against hidden defects, mechanical breakdowns, and legal issues.

```bash
# Human-friendly terminal formatted checklist
jimoty checklist tests/fixtures/detail_4st_fi_jog.html

# Markdown formatted checklist (save or send to buyer)
jimoty checklist tests/fixtures/detail_4st_fi_jog.html --format markdown

# Structured JSON format
jimoty checklist --json
```

The checklist dynamically adapts to vehicle attributes:
- If a 2-stroke scooter is detected, it automatically injects 2-stroke oil level and excessive white exhaust smoke checks.
- If a non-running bike is detected, it swaps running checks for rolling/transport readiness tests.

---

### Subcommand 9: `config`

Queries the Single Source of Truth (SSOT) configuration and verifies proxy masking:

```bash
# Show current configuration table
jimoty config

# Query specific key
jimoty config get --key default_municipality

# Output configuration as JSON
jimoty config --json
```

---

## 4. Python Library API Usage

`jimoty` is fully importable as a standard Python package.

### Basic Extraction Flow
```python
from jimoty.client import JimotyClient
from jimoty.config import JimotyConfig
from jimoty.models import SearchQuery
from jimoty.parser import parse_search_page, parse_detail_page

# 1. Initialize client with custom configuration
cfg = JimotyConfig(
    default_prefecture="kanagawa",
    default_municipality="a-314-chigasaki",
    default_max_price=50000,
)
client = JimotyClient(config=cfg)

# 2. Search listings
query = SearchQuery(
    prefecture="kanagawa",
    municipality="a-314-chigasaki",
    keyword="原付",
    max_price=50000,
)
html = client.fetch_search_html(query)
listings = parse_search_page(html)

for item in listings:
    print(f"[{item.id}] {item.title} -> {item.price_text}")

# 3. Retrieve and parse detail page
detail_html = client.fetch_detail_page(listings[0].url)
detail = parse_detail_page(detail_html)
print(f"Seller: {detail.seller.name}, Verified: {detail.seller.identified}")
```

### Programmatic Diagnostics & Templates
```python
from jimoty.diagnostics import DiagnosticEngine
from jimoty.templates import generate_inquiry_template
from jimoty.checklist import get_pickup_checklist

# Run diagnostics
engine = DiagnosticEngine()
report = engine.diagnose(detail)

if report.verdict.value == "RECOMMENDED":
    # Generate inquiry message
    message = generate_inquiry_template(detail, template_type="initial", buyer_name="佐藤")
    print("Inquiry Message:\n", message)

    # Generate inspection checklist
    checklist_items = get_pickup_checklist(detail)
    print(f"Generated {len(checklist_items)} inspection checkpoints.")
```

---

## 5. Diagnostic Rules Reference

The triage engine enforces a deterministic rule catalog across five distinct domains:

### 1. Legal & Paperwork Rules
- **`DOC-001-MISSING_PAPERS`** (**FATAL**):
  - *Trigger keywords*: `書類なし`, `書類紛失`, `登録不可`, `再登録不可`, `盗難車`, `ナンバー取得不可`.
  - *Verdict*: Immediately causes `FATAL_REJECT`. Never purchase a vehicle without papers, as riding an unregistered vehicle is illegal under Japan's Road Transport Vehicle Act (道路運送車両法), and purchasing stolen property constitutes a crime (盗品等関与罪).
- **`DOC-002-NO_KEYS`** (WARNING):
  - *Trigger keywords*: `鍵なし`, `キー欠品`, `キーなし`.
  - *Effect*: Flags high maintenance expense for replacing the key cylinder, ignition, and fuel tank locks.
- **`DOC-003-VALID_PAPERS`** (INFO / WARNING):
  - *Trigger keywords*: `廃車証明書`, `廃車申告受付書`, `譲渡証明書`, `標識交付証明書`, `販売証明書`, `登録書類`, `バイク登録書類`, `廃車済み`, `返納証明書`.
  - *Effect*: Confirms presence of official municipal paperwork or dealer sales certificate. If paperwork is unmentioned, raises a WARNING cautioning the buyer to verify with the seller before meetup.

### 2. Mechanical Triage Rules
- **`MECH-001-ENGINE_SEIZED`** (**FATAL**):
  - *Trigger keywords*: `焼き付き`, `クランク固着`, `キック降りない`.
  - *Verdict*: Triggers `FATAL_REJECT`. Piston/cylinder seizure requires engine replacement or complete overhaul.
- **`MECH-002-NON_RUNNING`** (**FATAL**):
  - *Trigger keywords*: `不動`, `ジャンク`, `部品取り`, `かからない`, `エンジンかかりません`.
  - *Verdict*: Triggers `FATAL_REJECT` for users seeking operational daily transportation.
- **`MECH-003-RUNNING_CONFIRMED`** (INFO / Score Boost):
  - *Trigger keywords*: `実動`, `セル一発`, `キック一発`, `走る曲がる止まる`, `好調`, `走行できます`, `走行可能`, `走行確認`, `セル・キック始動`, `セル始動`, `キック始動`, `試乗ok`, `最高速度`.
  - *Effect*: Adds positive score points, confirming operational road readiness and successful test riding.
- **`MECH-004-BATTERY_ISSUE`** (WARNING):
  - *Trigger keywords*: `バッテリー上がり`, `バッテリー要交換`, `バッテリー死んでます`.
  - *Effect*: Highlights a minor, manageable issue that does not disqualify the vehicle if kick-start or engine compression is functional.

### 3. Powertrain Classification Rules
- **`ENGINE-ENG-001-4S_FI`** (INFO):
  - *Trigger keywords*: `4スト`, `4st`, `4サイクル`, `FI`, `インジェクション`.
  - *Classification*: Modern 4-stroke Electronic Fuel Injection. High fuel efficiency (50+ km/L), low emissions, excellent cold-weather reliability, ideal for daily commuters (Honda Today AF67, Yamaha Jog SA36J/SA39J/SA55J).
- **`ENGINE-ENG-002-2S_CARB`** (INFO):
  - *Trigger keywords*: `2スト`, `2st`, `2サイクル`, `キャブ`, `キャブレター`.
  - *Classification*: 2-stroke carbureted engine. Rapid acceleration and light weight, but requires separate 2-stroke engine oil refills, has higher fuel consumption, and requires seasonal carburetor tuning.

### 4. Seller Integrity Rules
- **`SELLER-001-VERIFIED_ID`** (INFO / WARNING):
  - *Audit*: Inspects the `identified` flag (`本人確認済` badge).
  - *Effect*: Unverified sellers receive a penalty warning, as Jimoty identity verification requires government ID submission.
- **`SELLER-002-RATING_RATIO`** (INFO / WARNING):
  - *Audit*: Computes ratio of good to total reviews (`good_ratings / (good_ratings + normal_ratings + bad_ratings)`).
  - *Effect*: Sellers with a bad rating ratio > 10% receive a cautionary warning.
- **`SELLER-003-UNVERIFIED_SUSPICIOUS`** (WARNING):
  - *Audit*: Flags accounts with zero ratings and no identity verification selling high-value goods.

### 5. Listing Freshness & Activity Rules
- **`ACTIVITY-001-STALE_LISTING`** (INFO):
  - *Audit*: Evaluates elapsed days since posting (flags listings older than 30 days).
  - *Effect*: Informs buyer that vehicle may have sat idle or battery may have discharged; suggests asking if vehicle is still available (`まだお手元にございますでしょうか`).
- **`ACTIVITY-002-POPULAR_RUSH`** (INFO / Score Boost):
  - *Audit*: Evaluates favorites count (`favorites_count >= 10`) or inquiry rush badge (`inquiry_rush=True`).
  - *Effect*: Informs buyer of high market competition, recommending prompt initial message and quick meetup proposal.

---

## 6. Cultural Communication Etiquette

Transactions on Jimoty are governed by Japanese cultural expectations of courtesy, punctuality, and mutual trust:

1. **Use Formal Keigo (敬語)**:
   - Always open with a polite greeting: `はじめまして。出品を拝見し、購入を検討しております。`
   - Express sincere appreciation for their time: `ご多忙のところ恐れ入りますが、ご検討のほどよろしくお願い申し上げます。`
2. **State Direct Pickup Immediately (直接引き取り)**:
   - Sellers strongly prefer buyers who can pick up in person without requesting complex shipping: `当方、直接引き取り（〇〇市周辺までのお伺い）が可能です。`
3. **Explicitly Confirm Documents in Advance**:
   - Confirm paperwork before traveling: `廃車申告受付書（または標識交付証明書）および譲渡証明書の原本をお手元にご用意いただくことは可能でしょうか。`
4. **Payment Protocols**:
   - In-person cash payment at the time of vehicle handover (`当日現金手渡し`) is the standard custom on Jimoty. Bring the exact amount in cash to avoid requiring change.
5. **Prompt Punctuality**:
   - Arriving on time at the designated location is mandatory. If delayed by traffic, send a message immediately.

---

## 7. On-Site Inspection Checklist

When meeting the seller, follow the 5-point physical verification protocol before handing over cash:

1. **Category 1: Documents & VIN Matching ([!] CRITICAL)**:
   - **Check**: Compare the stamped frame/VIN number (located on the steering head pipe or under the footboard access panel) with the number printed on the **廃車申告受付書** (Deregistration Certificate).
   - **Warning signs**: The stamp has been ground off, re-stamped, or does not match the certificate exactly. **Walk away immediately if numbers do not match.**
   - **Transfer Deed**: Verify that the **譲渡証明書** (Transfer Certificate) has the previous owner's name, address, and seal/signature (**押印**).
2. **Category 2: Engine & Cold Start ([!] CRITICAL)**:
   - **Check**: Touch the exhaust pipe / cylinder head before starting. Ensure the engine is completely cold.
   - **Warning signs**: The engine is already warm (the seller may have warmed it up to conceal hard cold-starting or carburetor clogs).
   - **Smoke**: White/blue oily exhaust smoke on a 4-stroke engine indicates piston ring wear or valve seal failure (オイル上がり／下がり).
3. **Category 3: Electrical Systems & Lights**:
   - **Check**: Test headlight Hi/Lo beam, front/rear turn signals, horn, and especially the **brake light** operated independently by both the front hand lever and rear brake lever/pedal.
   - **Warning signs**: Brake light fails to illuminate on one lever (defective microswitch or wiring fault).
4. **Category 4: Chassis, Suspension, Tires & Brakes**:
   - **Front Fork**: Check fork inner tubes for rust pitting or leaking fork oil seals.
   - **Tires**: Inspect remaining tread depth and check sidewalls for dry rot cracks (オゾンクラック).
   - **Brakes**: Push the bike with brakes applied and released. Ensure neither wheel drags or binds.
   - **Fuel Tank**: Open the fuel cap with a flashlight and check the tank interior for orange rust powder or varnish odor.
5. **Category 5: Frame Alignment & Handling**:
   - Grip the front brake and rock the scooter forward and backward forcefully. Feel for play or clunking in the steering stem bearings.

---

## 8. Gotchas & Operational Edge Cases

### CloudFront 403 Geo-Blocking
- **Symptom**: `httpx.HTTPStatusError: 403 Forbidden` with CloudFront error HTML.
- **Root Cause**: Jimoty blocks non-Japanese IP ranges and certain cloud hosting providers (AWS, GCP, DigitalOcean).
- **Remedy**:
  - Configure a Japanese residential or proxy endpoint:
    ```bash
    export JIMOTY_PROXY="http://user:password@japan-proxy.example.com:8080"
    ```
  - Or supply the `--proxy` argument on the CLI:
    ```bash
    jimoty search -m chigasaki --proxy "http://127.0.0.1:1080"
    ```

### Chunked Transfer `IncompleteRead`
- **Symptom**: `httpx.ReadError` or `IncompleteRead` during high-traffic SSR responses.
- **Remedy**: `jimoty-cli` has built-in retry handling (`ChunkedTransferError`) that automatically retries the request up to 3 times with exponential backoff and jitter.

### 0-Yen Listings (無料 / 譲ります)
- **Symptom**: Items listed with price `0円` or `無料`.
- **Handling**: `extract_price()` marks `is_free=True` and sets `price=0`. `jimoty template` automatically adapts phrasing from "購入" (purchase) to "お譲り" (take over / receive), matching Jimoty etiquette.

### Stolen Vehicle Risks ("書類なし")
- **Symptom**: Sellers listing motorbikes cheaply with descriptions stating `書類はありません` or `鍵なし書類なし`.
- **Remedy**: Under Japanese law, you cannot register a motorized vehicle with a municipal tax office without a certificate of deregistration or proof of legitimate ownership. The diagnostic engine flags `DOC-001-MISSING_PAPERS` with `FATAL_REJECT`. **Never purchase a vehicle with "書類なし".**

---

## 9. Environment Variables & SSOT Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `JIMOTY_PREFECTURE` | `kanagawa` | Default target prefecture |
| `JIMOTY_MUNICIPALITY` | `a-314-chigasaki` | Default target municipality slug |
| `JIMOTY_CATEGORY` | `sale-bik` | Default category (`sale-bik` for motorcycles) |
| `JIMOTY_MAX_PRICE` | `60000` | Default price ceiling in JPY |
| `JIMOTY_TIMEOUT` | `15.0` | HTTP request timeout in seconds |
| `JIMOTY_PROXY` | `None` | Japanese residential or HTTP/HTTPS proxy URL |
| `HTTPS_PROXY` / `HTTP_PROXY` | `None` | Fallback proxy configuration |
