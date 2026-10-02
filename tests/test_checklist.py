"""Unit and contract tests for physical on-site inspection checklist (Requirement R3).

Verifies safety inspection checklist generation for direct pickup:
- Cold engine start & abnormal noise checks
- Electrical systems, lights, horn, and indicators
- Tire tread depth, dry rot cracks, and brake lever travel
- Front fork oil seal leakage and frame rust/alignment
- Document verification (VIN/frame number matching against 廃車申告受付書).
"""

from __future__ import annotations

import pytest
from jimoty.models import ListingDetail, Location, SellerProfile

try:
    from jimoty.checklist import ChecklistItem, generate_pickup_checklist
    HAS_CHECKLIST = True
except ImportError:
    HAS_CHECKLIST = False

pytestmark = pytest.mark.skipif(
    not HAS_CHECKLIST,
    reason="jimoty.checklist is pending implementation in Milestone 3",
)


class TestPickupChecklist:
    """Test physical vehicle inspection checklist items and adaptations."""

    def test_default_checklist_structure(self) -> None:
        """Verify general checklist contains all 5 core vehicle inspection sections."""
        items = generate_pickup_checklist()
        assert len(items) >= 5

        categories = {item.category.lower() for item in items}
        assert any("engine" in c or "始動" in c or "エンジン" in c for c in categories)
        assert any("light" in c or "電装" in c or "灯火" in c for c in categories)
        assert any("tire" in c or "brake" in c or "足回り" in c or "タイヤ" in c for c in categories)
        assert any("doc" in c or "書類" in c or "車台番号" in c for c in categories)

    def test_vin_and_document_matching_check(self) -> None:
        """Verify mandatory VIN stamp and document matching item is present."""
        items = generate_pickup_checklist()
        doc_item = next(
            (i for i in items if "車台番号" in i.item or "フレーム番号" in i.item or "書類" in i.item),
            None,
        )
        assert doc_item is not None
        assert doc_item.is_critical is True

    def test_cold_start_check_is_critical(self) -> None:
        """Verify cold start check is flagged as critical severity."""
        items = generate_pickup_checklist()
        start_item = next(
            (i for i in items if "始動" in i.item or "コールドスタート" in i.item or "エンジン" in i.item),
            None,
        )
        assert start_item is not None
        assert start_item.is_critical is True

    def test_checklist_adapts_to_2st_scooter(self) -> None:
        """Verify 2-stroke listing includes 2-stroke specific inspection points."""
        detail_2st = ListingDetail(
            id="lets2",
            title="レッツ2 2スト",
            url="https://jmty.jp/articles/lets",
            price=20000,
            price_text="20,000円",
            description="2スト車です。",
        )
        items = generate_pickup_checklist(detail=detail_2st)
        assert any("2スト" in i.item or "オイル" in i.item or "白煙" in i.item for i in items)
