"""Unit and integration tests for Jimoty parser layer: SSR search listing cards and __NEXT_DATA__ detail extraction."""

from __future__ import annotations

import json
from typing import Any, Dict
import pytest

from jimoty.models import ListingDetail, ListingSummary, Location, SellerProfile
from jimoty.parser import (
    ParserError,
    clean_text,
    extract_price,
    parse_datetime,
    parse_detail_page,
    parse_location_hierarchy,
    parse_search_page,
)


# ===========================================================================
# Tier 1 & 2: Search Listing Parser Tests
# ===========================================================================


class TestSearchListingParser:
    """Test SSR HTML search results parsing, card extraction rate, and field normalization."""

    def test_search_card_extraction_rate(self, search_bikes_html: str) -> None:
        """Verify 100% extraction rate of all 7 listing items from the Chigasaki fixture."""
        items = parse_search_page(search_bikes_html)
        assert len(items) == 7

    def test_search_item_ids(self, search_bikes_html: str) -> None:
        """Verify IDs are extracted accurately from data-article-id or URLs."""
        items = parse_search_page(search_bikes_html)
        ids = [item.id for item in items]
        expected_ids = [
            "article-18jog",
            "article-22today",
            "article-33lets",
            "article-44cub",
            "article-55address",
            "article-99junk",
            "article-00vino",
        ]
        for exp in expected_ids:
            assert any(exp in item_id for item_id in ids), f"Expected ID {exp} not found in {ids}"

    def test_search_item_prices(self, search_bikes_html: str) -> None:
        """Verify numeric price extraction and formatting."""
        items = parse_search_page(search_bikes_html)
        price_map = {item.id: item.price for item in items}
        assert price_map.get("article-18jog") == 38000
        assert price_map.get("article-22today") == 8000
        assert price_map.get("article-33lets") == 25000
        assert price_map.get("article-44cub") == 55000
        assert price_map.get("article-55address") == 42000
        assert price_map.get("article-99junk") == 1000
        assert price_map.get("article-00vino") == 0

    def test_search_free_item_flag(self, search_bikes_html: str) -> None:
        """Verify 0-yen listing is correctly flagged as is_free=True."""
        items = parse_search_page(search_bikes_html)
        vino_item = next(i for i in items if "vino" in i.id or "00vino" in i.id)
        assert vino_item.price == 0
        assert vino_item.is_free is True

    def test_search_item_locations(self, search_bikes_html: str) -> None:
        """Verify hierarchical location parsing on search cards."""
        items = parse_search_page(search_bikes_html)
        jog_item = next(i for i in items if "18jog" in i.id)
        assert jog_item.location is not None
        assert jog_item.location.city == "茅ヶ崎市"
        assert jog_item.location.station == "茅ヶ崎駅"

    def test_search_empty_html_returns_empty_list(self) -> None:
        """Verify empty or whitespace HTML returns an empty list without error."""
        assert parse_search_page("") == []
        assert parse_search_page("   \n\t  ") == []

    def test_search_html_with_no_cards_returns_empty_list(self) -> None:
        """Verify valid HTML without listing cards returns an empty list."""
        empty_page = "<html><body><div class='header'>No items found</div></body></html>"
        assert parse_search_page(empty_page) == []

    def test_search_item_to_dict_serializable(self, search_bikes_html: str) -> None:
        """Verify ListingSummary.to_dict produces JSON-serializable output."""
        items = parse_search_page(search_bikes_html)
        d = items[0].to_dict()
        assert isinstance(d, dict)
        assert "id" in d
        assert "title" in d
        assert "price" in d
        # Ensure json.dumps works without error
        json_str = json.dumps(d)
        assert len(json_str) > 0


# ===========================================================================
# Tier 1 & 2: __NEXT_DATA__ Detail Page Extractor Tests
# ===========================================================================


class TestNextDataDetailParser:
    """Test Next.js embedded __NEXT_DATA__ parsing across healthy, junk, and edge-case listings."""

    def test_parse_healthy_4st_fi_jog(self, detail_jog_html: str) -> None:
        """Verify full extraction of healthy 4-stroke FI Yamaha Jog detail page."""
        detail = parse_detail_page(detail_jog_html)
        assert detail.id == "article-18jog"
        assert "ヤマハ" in detail.title
        assert "ジョグ" in detail.title
        assert detail.price == 38000
        assert detail.price_text == "38,000円"
        assert detail.is_free is False
        assert "AY01" in detail.description
        assert "廃車申告受付書" in detail.description
        assert len(detail.image_urls) == 2
        assert detail.image_url == detail.image_urls[0]

        # Location
        assert detail.location is not None
        assert detail.location.city == "茅ヶ崎市"
        assert detail.location.station == "茅ヶ崎駅"

        # Seller Profile
        assert detail.seller is not None
        assert detail.seller.name == "湘南ライダー"
        assert detail.seller.identified is True
        assert detail.seller.good_ratings == 65
        assert detail.seller.normal_ratings == 1
        assert detail.seller.bad_ratings == 0
        assert detail.seller.total_ratings == 66
        assert detail.seller.positive_ratio == pytest.approx(65 / 66, rel=1e-3)

    def test_parse_junk_no_papers(self, detail_junk_html: str) -> None:
        """Verify extraction of non-running junk bike with missing papers."""
        detail = parse_detail_page(detail_junk_html)
        assert detail.id == "article-99junk"
        assert detail.price == 1000
        assert "不動" in detail.title or "不動" in detail.description
        assert "書類なし" in detail.description
        assert "鍵なし" in detail.description

        # Seller
        assert detail.seller is not None
        assert detail.seller.name == "あやしい出品者"
        assert detail.seller.identified is False
        assert detail.seller.good_ratings == 2
        assert detail.seller.bad_ratings == 3
        assert detail.seller.positive_ratio == 2 / 5

    def test_parse_2st_carb_lets2(self, detail_lets2_html: str) -> None:
        """Verify extraction of 2-stroke carbureted scooter."""
        detail = parse_detail_page(detail_lets2_html)
        assert detail.id == "article-33lets"
        assert detail.price == 25000
        assert "レッツ2" in detail.title
        assert "2スト" in detail.description
        assert "キャブレター" in detail.description
        assert detail.seller is not None
        assert detail.seller.identified is True

    def test_parse_fallback_html_without_next_data(self, detail_fallback_html: str) -> None:
        """Verify BeautifulSoup fallback parser extracts core fields when __NEXT_DATA__ is absent."""
        detail = parse_detail_page(detail_fallback_html)
        assert "スーパーカブ50" in detail.title
        assert detail.price == 55000
        assert "カブ" in detail.description
        assert detail.seller is not None
        assert detail.seller.name == "カブ主"
        assert detail.seller.identified is True
        assert detail.seller.good_ratings == 30

    def test_empty_html_raises_parser_error(self) -> None:
        """Verify empty HTML string raises ParserError."""
        with pytest.raises(ParserError):
            parse_detail_page("")


# ===========================================================================
# Tier 2: Edge Cases & Boundary Values (next_data_samples.json)
# ===========================================================================


class TestParserEdgeCases:
    """Test edge cases: 0-yen listings, missing fields, extreme ratings, unicode normalization."""

    def test_edge_case_free_zero_yen(self, next_data_samples: Dict[str, Any]) -> None:
        """Verify 0-yen / 無料 listing in __NEXT_DATA__ payload."""
        sample = next_data_samples["free_zero_yen"]
        html = f"""<html><body><script id="__NEXT_DATA__" type="application/json">
        {{"props": {{"pageProps": {{"articleResults": {json.dumps(sample)}}}}}}}
        </script></body></html>"""
        detail = parse_detail_page(html)
        assert detail.price == 0
        assert detail.is_free is True
        assert "無料" in detail.title

    def test_edge_case_missing_fields(self, next_data_samples: Dict[str, Any]) -> None:
        """Verify graceful handling of minimal payload with null location, images, and user."""
        sample = next_data_samples["missing_fields"]
        html = f"""<html><body><script id="__NEXT_DATA__" type="application/json">
        {{"props": {{"pageProps": {{"articleResults": {json.dumps(sample)}}}}}}}
        </script></body></html>"""
        detail = parse_detail_page(html)
        assert detail.id == "article-min"
        assert detail.title == "バイク 部品"
        assert detail.price == 3000
        assert detail.description == ""
        assert detail.image_urls == []

    def test_edge_case_extreme_ratings_high(self, next_data_samples: Dict[str, Any]) -> None:
        """Verify handling of professional seller with thousands of ratings and antique dealer badge."""
        sample = next_data_samples["extreme_ratings_high"]
        html = f"""<html><body><script id="__NEXT_DATA__" type="application/json">
        {{"props": {{"pageProps": {{"articleResults": {json.dumps(sample)}}}}}}}
        </script></body></html>"""
        detail = parse_detail_page(html)
        assert detail.seller is not None
        assert detail.seller.good_ratings == 2540
        assert detail.seller.bad_ratings == 1
        assert detail.seller.is_antique_dealer is True
        assert detail.seller.positive_ratio > 0.99

    def test_edge_case_extreme_ratings_low(self, next_data_samples: Dict[str, Any]) -> None:
        """Verify seller with only bad ratings (0 good, 18 bad)."""
        sample = next_data_samples["extreme_ratings_low"]
        html = f"""<html><body><script id="__NEXT_DATA__" type="application/json">
        {{"props": {{"pageProps": {{"articleResults": {json.dumps(sample)}}}}}}}
        </script></body></html>"""
        detail = parse_detail_page(html)
        assert detail.seller is not None
        assert detail.seller.good_ratings == 0
        assert detail.seller.bad_ratings == 18
        assert detail.seller.positive_ratio == 0.0

    def test_edge_case_unicode_and_fullwidth(self, next_data_samples: Dict[str, Any]) -> None:
        """Verify NFKC normalization of Japanese fullwidth alphanumeric characters and emojis."""
        sample = next_data_samples["unicode_and_special_chars"]
        html = f"""<html><body><script id="__NEXT_DATA__" type="application/json">
        {{"props": {{"pageProps": {{"articleResults": {json.dumps(sample)}}}}}}}
        </script></body></html>"""
        detail = parse_detail_page(html)
        assert "50cc" in detail.title or "50cc" in detail.description
        assert "FI" in detail.title or "FI" in detail.description

    def test_corrupted_next_data_json_triggers_html_fallback(self) -> None:
        """Verify malformed JSON in __NEXT_DATA__ does not crash and falls back to HTML parsing."""
        corrupted_html = """<html><body>
        <h1>ホンダ トゥデイ 50cc 実動</h1>
        <div class="price">15,000円</div>
        <div class="p-article-description">快調に動きます。</div>
        <script id="__NEXT_DATA__" type="application/json">{invalid json content</script>
        </body></html>"""
        detail = parse_detail_page(corrupted_html)
        assert detail.title == "ホンダ トゥデイ 50cc 実動"
        assert detail.price == 15000
        assert "快調に動きます" in detail.description

    def test_html_entities_in_description_unescaped(self) -> None:
        """Verify HTML entities like &amp;, &lt;, &gt;, &quot; are properly decoded."""
        html_with_entities = """<html><body>
        <h1>テスト車両 &amp; 特選車</h1>
        <div class="price">20,000円</div>
        <div class="p-article-description">&lt;極上車&gt; &quot;早い者勝ち&quot; &amp; 格安！</div>
        </body></html>"""
        detail = parse_detail_page(html_with_entities)
        assert "&" in detail.title or "＆" in detail.title
        assert "<極上車>" in detail.description
        assert '"早い者勝ち"' in detail.description

    def test_model_property_convenience_accessors(self) -> None:
        """Verify image_url convenience property and to_dict methods on models."""
        loc = Location(prefecture="神奈川県", city="茅ヶ崎市")
        assert loc.to_dict()["city"] == "茅ヶ崎市"

        seller = SellerProfile(name="テスト", good_ratings=0, bad_ratings=0)
        assert seller.positive_ratio == 0.0
        assert seller.to_dict()["positive_ratio"] == 0.0

        detail = ListingDetail(
            id="1",
            title="テスト",
            url="https://jmty.jp/1",
            price=10000,
            price_text="10,000円",
            description="desc",
            image_urls=["https://img.jmty.jp/1.jpg", "https://img.jmty.jp/2.jpg"],
        )
        assert detail.image_url == "https://img.jmty.jp/1.jpg"
        assert detail.to_dict()["price"] == 10000


# ===========================================================================
# Tier 1 & 2: Utility Function Unit Tests
# ===========================================================================


class TestUtilityFunctions:
    """Test price extractor, text cleaner, datetime parser, and location parser utilities."""

    @pytest.mark.parametrize(
        "raw_input,expected_price,expected_free",
        [
            (38000, 38000, False),
            ("38,000円", 38000, False),
            ("¥50,000", 50000, False),
            ("￥50,000", 50000, False),
            (0, 0, True),
            ("0円", 0, True),
            ("無料", 0, True),
            ("0", 0, True),
            (None, 0, True),
            ("要相談", 0, False),
        ],
    )
    def test_extract_price_matrix(self, raw_input: Any, expected_price: int, expected_free: bool) -> None:
        """Test extract_price across various Japanese price formatting conventions."""
        p_val, p_text, is_free = extract_price(raw_input)
        assert p_val == expected_price
        assert is_free == expected_free

    def test_clean_text_normalizes_whitespace(self) -> None:
        """Verify fullwidth spaces, multiple consecutive spaces, and trailing whitespace are cleaned."""
        raw = "  ホンダ　　スーパーカブ　５０ｃｃ  \n\t"
        cleaned = clean_text(raw)
        assert cleaned == "ホンダ スーパーカブ 50cc"

    def test_clean_text_handles_none(self) -> None:
        """Verify clean_text with None or empty string returns empty string."""
        assert clean_text(None) == ""
        assert clean_text("") == ""

    def test_parse_location_hierarchy(self) -> None:
        """Verify location text parsing into prefecture, city, station."""
        loc = parse_location_hierarchy("神奈川県 茅ヶ崎市 茅ヶ崎駅")
        assert loc.prefecture == "神奈川県"
        assert loc.city == "茅ヶ崎市"
        assert loc.station == "茅ヶ崎駅"

    def test_extract_video_and_drive_links(self) -> None:
        """Verify extraction of YouTube operational videos and Google Drive albums from description."""
        html = """<html><body><script id="__NEXT_DATA__" type="application/json">
        {"props": {"pageProps": {"articleResults": {
            "article": {
                "id": "test-vid",
                "title": "ヤマハ JOG 動画あり",
                "price": 50000,
                "text": "動作動画はこちら\\nhttps://youtu.be/test12345\\n追加画像フォルダ\\nhttps://drive.google.com/drive/folders/abcdef"
            }
        }}}}
        </script></body></html>"""
        detail = parse_detail_page(html)
        assert len(detail.video_urls) == 1
        assert "youtu.be/test12345" in detail.video_urls[0]
        assert len(detail.drive_urls) == 1
        assert "drive.google.com" in detail.drive_urls[0]

    def test_filter_alliance_ads_in_search_results(self) -> None:
        """Verify commercial recruitment and sponsored alliance ads are filtered from search listings."""
        html = """<html><body>
        <div class="p-articles-list">
          <div class="p-articles-list-item">
            <div class="p-item-title"><a href="/kanagawa/sale-bik/article-bike01">実動バイク</a></div>
            <div class="p-item-most-important">30,000円</div>
          </div>
          <div class="p-articles-list-item">
            <div class="p-item-alliance-tag">PR</div>
            <div class="p-item-title"><a href="/kanagawa/rec-lig/alliance-rec_123">工場組立ワーク募集</a></div>
            <div class="p-item-most-important">月給25万円</div>
          </div>
        </div>
        </body></html>"""
        items = parse_search_page(html)
        assert len(items) == 1
        assert items[0].id == "bike01"
        assert items[0].title == "実動バイク"

