"""Command-line interface (CLI) entry point for jimoty-cli.

Provides subcommands:
- search: Search listings by municipality, price bounds, category, keywords
- get: Fetch and parse listing details
- diagnose: Deterministic evaluation and triage engine
- template: Generate culturally polite Japanese inquiry messages
- checklist: On-site physical inspection safety checklist
- config: Display or query operational defaults and masked proxy
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

from jimoty.checklist import (
    get_pickup_checklist,
    render_checklist_markdown,
    render_checklist_terminal,
)
from jimoty.client import JimotyClient, JimotyError
from jimoty.config import (
    DEFAULT_CATEGORY,
    DEFAULT_MAX_PRICE,
    DEFAULT_MUNICIPALITY,
    DEFAULT_PREFECTURE,
    JimotyConfig,
    resolve_category,
    resolve_municipality,
)
from jimoty.diagnostics import DiagnosticEngine
from jimoty.models import ListingDetail, SearchQuery
from jimoty.parser import ParserError, parse_detail_page, parse_search_page
from jimoty.templates import generate_inquiry_template, list_template_types


def _load_detail(url_or_id_or_file: str, proxy: Optional[str] = None) -> ListingDetail:
    """Load and parse ListingDetail from a local HTML file or remote Jimoty URL/ID."""
    if os.path.isfile(url_or_id_or_file):
        with open(url_or_id_or_file, "r", encoding="utf-8") as f:
            html = f.read()
    else:
        cfg = JimotyConfig.from_env()
        if proxy:
            cfg.proxy = proxy
        client = JimotyClient(config=cfg)
        html = client.fetch_detail_page(url_or_id_or_file, proxy=proxy)

    return parse_detail_page(html)


def _handle_search(args: argparse.Namespace) -> int:
    """Handle `jimoty search` subcommand."""
    muni = resolve_municipality(args.municipality) if args.municipality else None
    cat = resolve_category(args.category) if args.category else DEFAULT_CATEGORY

    query = SearchQuery(
        prefecture=args.prefecture or DEFAULT_PREFECTURE,
        category=cat,
        municipality=muni,
        keyword=args.keyword,
        min_price=args.min_price,
        max_price=args.max_price,
        sort=args.sort,
    )

    cfg = JimotyConfig.from_env()
    if args.proxy:
        cfg.proxy = args.proxy

    client = JimotyClient(config=cfg)
    html = client.fetch_search_html(query, proxy=args.proxy)
    items = parse_search_page(html, base_url=cfg.base_url)

    if args.limit is not None and args.limit > 0:
        items = items[: args.limit]

    if args.json:
        payload = [item.to_dict() for item in items]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if not items:
            print("No listings found matching criteria.")
            return 0

        target_muni = muni or "all"
        print(f"Found {len(items)} listing(s) in {query.prefecture}/{target_muni}:")
        print("=" * 78)
        for item in items:
            price_disp = "無料 (0円)" if item.is_free else item.price_text
            loc_disp = item.location_text or "N/A"
            date_disp = item.created_at_text or (item.created_at.strftime("%Y-%m-%d") if item.created_at else None)
            print(f"[{item.id}] {item.title}")
            print(f"  Price:    {price_disp}")
            print(f"  Location: {loc_disp}")
            if date_disp:
                print(f"  Timeline: {date_disp}")
            print(f"  URL:      {item.url}")
            print("-" * 78)

    return 0


def _handle_get(args: argparse.Namespace) -> int:
    """Handle `jimoty get` subcommand."""
    detail = _load_detail(args.url_or_id, proxy=args.proxy)

    if args.json:
        print(json.dumps(detail.to_dict(), ensure_ascii=False, indent=2))
    else:
        price_disp = "無料 (0円)" if detail.is_free else detail.price_text
        seller_name = detail.seller.name if detail.seller else "N/A"
        seller_ident = (
            "本人確認済"
            if (detail.seller and detail.seller.identified)
            else "未認証"
        )
        ratings_disp = (
            f"良い:{detail.seller.good_ratings} / 悪い:{detail.seller.bad_ratings}"
            if detail.seller
            else "N/A"
        )

        print("=" * 78)
        print(f"  JIMOTY LISTING DETAIL: [{detail.id}]")
        print("=" * 78)
        print(f"  Title:       {detail.title}")
        print(f"  Price:       {price_disp}")
        print(f"  Location:    {detail.location_text or 'N/A'}")
        if detail.created_at:
            post_str = detail.created_at.strftime("%Y-%m-%d %H:%M")
            up_str = detail.updated_at.strftime("%Y-%m-%d %H:%M") if detail.updated_at else "なし"
            print(f"  Timeline:    投稿: {post_str} | 最終更新: {up_str}")
        print(f"  Seller:      {seller_name} ({seller_ident}, {ratings_disp})")
        print(f"  URL:         {detail.url}")
        print("-" * 78)
        print("  Description:")
        for line in detail.description.splitlines():
            print(f"    {line}")
        print("=" * 78)

    return 0


def _handle_diagnose(args: argparse.Namespace) -> int:
    """Handle `jimoty diagnose` subcommand."""
    detail = _load_detail(args.url_or_id_or_file, proxy=args.proxy)
    engine = DiagnosticEngine()
    report = engine.diagnose(detail)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(report.format_terminal())

    return 0


def _handle_template(args: argparse.Namespace) -> int:
    """Handle `jimoty template` subcommand."""
    detail = _load_detail(args.url_or_id_or_file, proxy=args.proxy)

    kwargs: Dict[str, Any] = {}
    if args.buyer_name:
        kwargs["buyer_name"] = args.buyer_name
    if args.date:
        kwargs["candidate_dates"] = [args.date]

    text = generate_inquiry_template(detail, template_type=args.type, **kwargs)

    if args.json:
        payload = {
            "type": args.type,
            "item_id": detail.id,
            "title": detail.title,
            "seller_name": detail.seller.name if detail.seller else "",
            "template": text,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text)

    return 0


def _handle_checklist(args: argparse.Namespace) -> int:
    """Handle `jimoty checklist` subcommand."""
    detail: Optional[ListingDetail] = None
    if args.url_or_id_or_file:
        detail = _load_detail(args.url_or_id_or_file, proxy=args.proxy)

    items = get_pickup_checklist(detail)

    if args.json or args.format == "json":
        payload = [item.to_dict() for item in items]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.format == "markdown":
        print(render_checklist_markdown(items, detail))
    else:
        print(render_checklist_terminal(items, detail))

    return 0


def _handle_config(args: argparse.Namespace) -> int:
    """Handle `jimoty config` subcommand."""
    cfg = JimotyConfig.from_env()

    if args.action == "get" and args.key:
        cfg_dict = cfg.to_dict()
        val = cfg_dict.get(args.key)
        if val is not None:
            print(val)
            return 0
        sys.stderr.write(f"Unknown config key: {args.key}\n")
        return 1

    if args.action == "set" and args.key:
        sys.stderr.write("Config persist to file is not supported; set environment variables instead.\n")
        return 0

    if args.json:
        print(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2))
    else:
        proxy_disp = cfg.to_dict()["proxy"] or "None"
        proxy_status = "Yes (Configured)" if cfg.proxy else "No (Direct)"
        max_price_disp = f"{cfg.default_max_price:,}円" if cfg.default_max_price is not None else "None"

        print("=" * 78)
        print("  JIMOTY OPERATIONAL CONFIGURATION (SSOT)")
        print("=" * 78)
        print(f"  Base URL:             {cfg.base_url}")
        print(f"  Default Prefecture:   {cfg.default_prefecture}")
        print(f"  Default Municipality: {cfg.default_municipality} (茅ヶ崎市 / Chigasaki)")
        print(f"  Default Category:     {cfg.default_category} (バイク / Motorcycles)")
        print(f"  Default Max Price:    {max_price_disp}")
        print(f"  Proxy Active:         {proxy_status}")
        print(f"  Proxy URL:            {proxy_disp}")
        print(f"  HTTP Timeout:         {cfg.timeout}s")
        print(f"  Max Retries:          {cfg.max_retries}")
        print("=" * 78)

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build and configure the top-level CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="jimoty",
        description="jimoty-cli: Agent-native CLI tool for searching, scraping, and evaluating Japan Jimoty (jmty.jp) listings.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="jimoty-cli 0.1.0",
    )

    subparsers = parser.add_subparsers(
        title="Subcommands",
        dest="subcommand",
        metavar="<command>",
    )

    # -------------------------------------------------------------------------
    # Subcommand: search
    # -------------------------------------------------------------------------
    search_parser = subparsers.add_parser(
        "search",
        help="Search Jimoty listings by municipality, price bounds, category, keywords",
        description="Search Jimoty listings with SSR HTML parsing, municipality codes, and price filters.",
    )
    search_parser.add_argument(
        "-k",
        "--keyword",
        type=str,
        default=None,
        help="Search keywords (e.g. '原付 50cc', 'ジョグ')",
    )
    search_parser.add_argument(
        "-m",
        "--municipality",
        type=str,
        default=DEFAULT_MUNICIPALITY,
        help=f"Municipality name or slug (default: {DEFAULT_MUNICIPALITY}, e.g. 'chigasaki', 'fujisawa', '茅ヶ崎市')",
    )
    search_parser.add_argument(
        "--prefecture",
        type=str,
        default=DEFAULT_PREFECTURE,
        help=f"Target prefecture (default: {DEFAULT_PREFECTURE})",
    )
    search_parser.add_argument(
        "--category",
        type=str,
        default=DEFAULT_CATEGORY,
        help=f"Category slug or Japanese alias (default: {DEFAULT_CATEGORY}, 'bike', 'bicycle', 'car')",
    )
    search_parser.add_argument(
        "--min-price",
        type=int,
        default=None,
        help="Minimum price filter in JPY",
    )
    search_parser.add_argument(
        "-p",
        "--max-price",
        type=int,
        default=DEFAULT_MAX_PRICE,
        help=f"Maximum price filter in JPY (default: {DEFAULT_MAX_PRICE})",
    )
    search_parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="Japanese residential or HTTP/HTTPS proxy URL override",
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of listings to return",
    )
    search_parser.add_argument(
        "--sort",
        type=str,
        default=None,
        help="Sorting order (e.g. 'price_asc', 'price_desc', 'date_desc')",
    )
    search_parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw structured JSON array",
    )

    # -------------------------------------------------------------------------
    # Subcommand: get
    # -------------------------------------------------------------------------
    get_parser = subparsers.add_parser(
        "get",
        help="Retrieve full structured details for a specific listing",
        description="Retrieve full details from embedded __NEXT_DATA__ JSON or HTML fallback.",
    )
    get_parser.add_argument(
        "url_or_id",
        metavar="URL_OR_ID",
        help="Jimoty listing URL, article key/ID (e.g. 'article-18jog'), or local HTML file path",
    )
    get_parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="Proxy URL override",
    )
    get_parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON dictionary",
    )

    # -------------------------------------------------------------------------
    # Subcommand: diagnose
    # -------------------------------------------------------------------------
    diag_parser = subparsers.add_parser(
        "diagnose",
        help="Run deterministic diagnostic triage and scam evaluation on a listing",
        description="Run deterministic diagnostic triage auditing legal paperwork, mechanical status, powertrain, and seller trust.",
    )
    diag_parser.add_argument(
        "url_or_id_or_file",
        metavar="URL_OR_ID_OR_FILE",
        help="Jimoty listing URL, article ID, or HTML fixture file path",
    )
    diag_parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="Proxy URL override",
    )
    diag_parser.add_argument(
        "--json",
        action="store_true",
        help="Output full diagnostic report as JSON dictionary with rule evaluations",
    )

    # -------------------------------------------------------------------------
    # Subcommand: template
    # -------------------------------------------------------------------------
    tmpl_parser = subparsers.add_parser(
        "template",
        help="Generate culturally polite Japanese inquiry message for a listing",
        description="Generate polite Japanese keigo marketplace messages tailored to the listing.",
    )
    tmpl_parser.add_argument(
        "url_or_id_or_file",
        metavar="URL_OR_ID_OR_FILE",
        help="Jimoty listing URL, article ID, or HTML fixture file path",
    )
    tmpl_parser.add_argument(
        "--type",
        choices=list_template_types(),
        default="initial",
        help="Template type: 'initial' (first contact), 'paperwork' (documents & keys), 'schedule' (meetup coordination)",
    )
    tmpl_parser.add_argument(
        "--buyer-name",
        type=str,
        default="",
        help="Buyer name to sign at the end of the inquiry",
    )
    tmpl_parser.add_argument(
        "--date",
        type=str,
        default="",
        help="Candidate inspection/pickup date (e.g. '今週土曜 14:00')",
    )
    tmpl_parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="Proxy URL override",
    )
    tmpl_parser.add_argument(
        "--json",
        action="store_true",
        help="Output inquiry template as JSON",
    )

    # -------------------------------------------------------------------------
    # Subcommand: checklist
    # -------------------------------------------------------------------------
    check_parser = subparsers.add_parser(
        "checklist",
        help="Generate physical on-site inspection checklist for vehicle pickup",
        description="Generate physical on-site inspection safety checklist for vehicle pickup.",
    )
    check_parser.add_argument(
        "url_or_id_or_file",
        nargs="?",
        default=None,
        metavar="URL_OR_ID_OR_FILE",
        help="Optional Jimoty listing URL, article ID, or HTML file to adapt checklist for vehicle attributes",
    )
    check_parser.add_argument(
        "--format",
        choices=["terminal", "markdown", "json"],
        default="terminal",
        help="Output format: 'terminal' (default), 'markdown', or 'json'",
    )
    check_parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="Proxy URL override",
    )
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="Output checklist items as JSON array (shorthand for --format json)",
    )

    # -------------------------------------------------------------------------
    # Subcommand: config
    # -------------------------------------------------------------------------
    cfg_parser = subparsers.add_parser(
        "config",
        help="Display or query operational configuration defaults and masked proxy",
        description="Display or query operational configuration defaults (SSOT) and masked proxy.",
    )
    cfg_parser.add_argument(
        "action",
        nargs="?",
        choices=["show", "get", "set"],
        default="show",
        help="Config action: 'show' (default), 'get', or 'set'",
    )
    cfg_parser.add_argument(
        "--key",
        type=str,
        default=None,
        help="Config parameter key for get/set",
    )
    cfg_parser.add_argument(
        "--value",
        type=str,
        default=None,
        help="Config parameter value for set",
    )
    cfg_parser.add_argument(
        "--json",
        action="store_true",
        help="Output configuration as JSON",
    )

    return parser


def main(args: Optional[List[str]] = None) -> int:
    """Main CLI entry point.

    Args:
        args: Optional command line argument list. If None, sys.argv[1:] is used.

    Returns:
        Exit code: 0 on success, 1 on operational/network failure, 2 on syntax error.
    """
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if not parsed_args.subcommand:
        parser.print_help()
        return 0

    handlers = {
        "search": _handle_search,
        "get": _handle_get,
        "diagnose": _handle_diagnose,
        "template": _handle_template,
        "checklist": _handle_checklist,
        "config": _handle_config,
    }

    handler = handlers.get(parsed_args.subcommand)
    if not handler:
        parser.print_help()
        return 2

    try:
        return handler(parsed_args)
    except (JimotyError, ParserError, FileNotFoundError, ValueError) as err:
        sys.stderr.write(f"Error: {err}\n")
        return 1
    except Exception as err:
        sys.stderr.write(f"Unexpected error: {err}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
