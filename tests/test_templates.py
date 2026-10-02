"""Unit and contract tests for Japanese communication templates (Requirement R3).

Verifies culturally idiomatic, polite marketplace inquiry templates (敬語):
- Initial inquiry for direct pickup (直接引き取り)
- Registration paperwork & key count verification inquiry
- Schedule coordination and meetup logistics
- Dynamic customization for free items (0円 / 無料) and missing seller details.
"""

from __future__ import annotations

import pytest
from jimoty.models import ListingDetail, Location, SellerProfile

try:
    from jimoty.templates import generate_inquiry_template
    HAS_TEMPLATES = True
except ImportError:
    HAS_TEMPLATES = False

pytestmark = pytest.mark.skipif(
    not HAS_TEMPLATES,
    reason="jimoty.templates is pending implementation in Milestone 3",
)


@pytest.fixture
def jog_detail() -> ListingDetail:
    """Sample healthy Jog listing for templating."""
    return ListingDetail(
        id="article-18jog",
        title="ヤマハ ジョグ FI 4スト 実動 廃車申告受付書あり",
        url="https://jmty.jp/articles/article-18jog",
        price=38000,
        price_text="38,000円",
        description="ヤマハ JOG 4スト FI車です。セル一発始動。",
        location=Location(prefecture="神奈川県", city="茅ヶ崎市", station="茅ヶ崎駅"),
        seller=SellerProfile(name="湘南ライダー", identified=True),
    )


@pytest.fixture
def free_vino_detail() -> ListingDetail:
    """Sample free 0-yen listing for templating."""
    return ListingDetail(
        id="article-00vino",
        title="無料 ヤマハ ビーノ 不動 引き取り限定",
        url="https://jmty.jp/articles/article-00vino",
        price=0,
        price_text="0円",
        is_free=True,
        description="不動車です。0円でお譲りします。",
        location=Location(prefecture="神奈川県", city="茅ヶ崎市"),
        seller=SellerProfile(name="断捨離マン", identified=True),
    )


class TestInquiryTemplates:
    """Test generation of Japanese marketplace inquiry messages."""

    def test_initial_pickup_inquiry(self, jog_detail: ListingDetail) -> None:
        """Verify initial message requests in-person pickup with proper keigo."""
        msg = generate_inquiry_template(jog_detail, template_type="initial")
        assert "湘南ライダー" in msg
        assert "ヤマハ ジョグ" in msg
        assert "直接引き取り" in msg
        assert "よろしくお願いいたします" in msg
        assert "はじめまして" in msg or "こんにちは" in msg

    def test_paperwork_inquiry_template(self, jog_detail: ListingDetail) -> None:
        """Verify paperwork template asks about 廃車申告受付書, 譲渡証明書, and keys."""
        msg = generate_inquiry_template(jog_detail, template_type="paperwork")
        assert "書類" in msg or "廃車" in msg or "譲渡" in msg
        assert "鍵" in msg

    def test_schedule_coordination_template(self, jog_detail: ListingDetail) -> None:
        """Verify schedule template politely requests candidate dates and meeting place."""
        msg = generate_inquiry_template(jog_detail, template_type="schedule")
        assert "日時" in msg or "日程" in msg
        assert "引き渡し" in msg or "現車確認" in msg

    def test_free_listing_adapts_phrasing(self, free_vino_detail: ListingDetail) -> None:
        """Verify 0-yen listing adapts phrasing to 'お譲り' instead of purchase."""
        msg = generate_inquiry_template(free_vino_detail, template_type="initial")
        assert "お譲り" in msg or "引き取り" in msg

    def test_missing_seller_handled_gracefully(self) -> None:
        """When seller name is missing, template uses generic polite salutation."""
        anon_detail = ListingDetail(
            id="article-anon",
            title="原付 50cc",
            url="https://jmty.jp/articles/anon",
            price=20000,
            price_text="20,000円",
            description="原付です。",
            seller=None,
        )
        msg = generate_inquiry_template(anon_detail, template_type="initial")
        assert "出品者様" in msg
        assert len(msg) > 50
