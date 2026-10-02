"""Comprehensive test suite for Jimoty diagnostic & triage engine (Requirement R2).

Tests deterministic evaluation rules:
- Document & Legal Audit (廃車申告受付書, 譲渡証明書, 書類なし -> FATAL_REJECT)
- Mechanical Condition Triage (不動, ジャンク, 焼き付き vs 実動, セル一発)
- Powertrain Classification (4st FI vs 2st Carb)
- Seller Integrity Score (本人確認済 badge, good/bad ratios)
- Deterministic scoring, verdict rules, and --json output schema compliance.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict
import pytest

from jimoty.models import ListingDetail, Location, SellerProfile

try:
    from jimoty.diagnostics import (
        DiagnosticEngine,
        DiagnosticReport,
        RuleEvaluation,
        Verdict,
    )
    HAS_DIAGNOSTICS = True
except ImportError:
    HAS_DIAGNOSTICS = False

pytestmark = pytest.mark.skipif(
    not HAS_DIAGNOSTICS,
    reason="jimoty.diagnostics is pending implementation in Milestone 2",
)


# ===========================================================================
# Fixture Helpers
# ===========================================================================


@pytest.fixture
def engine() -> Any:
    """Instantiate DiagnosticEngine."""
    return DiagnosticEngine()


@pytest.fixture
def sample_jog_detail() -> ListingDetail:
    """Healthy 4-stroke FI Yamaha Jog with verified seller and full paperwork."""
    return ListingDetail(
        id="article-18jog",
        title="ヤマハ ジョグ FI 4スト 実動 廃車申告受付書あり",
        url="https://jmty.jp/articles/article-18jog",
        price=38000,
        price_text="38,000円",
        description=(
            "ヤマハ JOG (AY01型) 4スト FI車です。\n"
            "セル・キックともに一発始動、走る曲がる止まる問題ありません。\n"
            "廃車申告受付書、譲渡証明書あります。\n"
            "自賠責保険はありません。直接引き取り希望です。"
        ),
        location=Location(prefecture="神奈川県", city="茅ヶ崎市", station="茅ヶ崎駅"),
        seller=SellerProfile(
            id="u98765",
            name="湘南ライダー",
            identified=True,
            good_ratings=65,
            bad_ratings=0,
            total_ratings=65,
        ),
    )


@pytest.fixture
def sample_junk_detail() -> ListingDetail:
    """Non-running junk motorcycle with no papers and unverified seller."""
    return ListingDetail(
        id="article-99junk",
        title="不動 / 書類なし / 鍵なし ジャンク 部品取りに",
        url="https://jmty.jp/articles/article-99junk",
        price=1000,
        price_text="1,000円",
        description=(
            "不動です。キック降りません。エンジン焼き付きと思われます。書類なし、鍵なしです。\n"
            "再登録はできませんので部品取り専用ジャンク品としてノークレームノーリターンでお願いします。"
        ),
        location=Location(prefecture="神奈川県", city="茅ヶ崎市"),
        seller=SellerProfile(
            id="u11111",
            name="あやしい出品者",
            identified=False,
            good_ratings=2,
            bad_ratings=3,
            total_ratings=5,
        ),
    )


@pytest.fixture
def sample_lets2_detail() -> ListingDetail:
    """2-stroke carbureted Suzuki Let's 2 scooter, running with paperwork."""
    return ListingDetail(
        id="article-33lets",
        title="スズキ レッツ2 CA1PA 2スト キャブ 実動",
        url="https://jmty.jp/articles/article-33lets",
        price=25000,
        price_text="25,000円",
        description=(
            "スズキ レッツ2 (CA1PA) 2スト キャブレター車です。\n"
            "キック一発始動、2スト特有の力強い加速で快調に走ります。\n"
            "灯火類問題なし、前後ブレーキ効きます。\n"
            "廃車申告受付書、譲渡証明書あります。"
        ),
        location=Location(prefecture="神奈川県", city="茅ヶ崎市", station="辻堂駅"),
        seller=SellerProfile(
            id="u44332",
            name="湘南通勤ライダー",
            identified=True,
            good_ratings=15,
            bad_ratings=0,
            total_ratings=15,
        ),
    )


# ===========================================================================
# Tier 1 & 2: Legal & Paperwork Audit Tests
# ===========================================================================


class TestLegalPaperworkAudit:
    """Test verification of registration documents and stolen vehicle risk heuristics."""

    def test_complete_paperwork_passes(self, engine: Any, sample_jog_detail: ListingDetail) -> None:
        """Verify presence of 廃車申告受付書 and 譲渡証明書 passes paperwork audit."""
        report = engine.diagnose(sample_jog_detail)
        assert not any("DOC" in flag for flag in report.fatal_flags)
        doc_rules = [r for r in report.rules_evaluated if "DOC" in r.rule_id or "PAPER" in r.rule_id]
        assert any(r.passed for r in doc_rules)

    def test_no_papers_triggers_fatal_reject(self, engine: Any, sample_junk_detail: ListingDetail) -> None:
        """Verify '書類なし' explicitly triggers fatal reject with legal/stolen warning."""
        report = engine.diagnose(sample_junk_detail)
        assert report.verdict in ("FATAL_REJECT", Verdict.FATAL_REJECT)
        assert len(report.fatal_flags) > 0
        assert any("書類なし" in f or "DOC" in f or "stolen" in f.lower() for f in report.fatal_flags)

    def test_paperwork_unmentioned_triggers_caution(self, engine: Any) -> None:
        """When paperwork is neither confirmed nor denied, raise a warning flag for inquiry."""
        detail = ListingDetail(
            id="article-nopapers-mentioned",
            title="ホンダ ディオ 実動 茅ヶ崎",
            url="https://jmty.jp/articles/123",
            price=30000,
            price_text="30,000円",
            description="走る曲がる止まる問題ありません。ヘルメットおまけします。",
            seller=SellerProfile(name="一般出品者", identified=True, good_ratings=10),
        )
        report = engine.diagnose(detail)
        assert any("書類" in f or "DOC" in f or "paper" in f.lower() for f in report.warning_flags)


# ===========================================================================
# Tier 1 & 2: Mechanical Condition Triage Tests
# ===========================================================================


class TestMechanicalTriage:
    """Test triage for running vs non-running / junk / seized engines."""

    def test_running_engine_passes(self, engine: Any, sample_jog_detail: ListingDetail) -> None:
        """Verify 実動, セル一発始動 scores positively on mechanical condition."""
        report = engine.diagnose(sample_jog_detail)
        mech_rules = [r for r in report.rules_evaluated if "MECH" in r.rule_id]
        assert any(r.passed for r in mech_rules)
        assert not any("不動" in f for f in report.fatal_flags)

    def test_non_running_junk_triggers_fatal_flag(self, engine: Any, sample_junk_detail: ListingDetail) -> None:
        """Verify 不動, キック降りない, 焼き付き triggers fatal flag."""
        report = engine.diagnose(sample_junk_detail)
        assert any("不動" in f or "MECH" in f or "junk" in f.lower() for f in report.fatal_flags)

    def test_battery_dead_triggers_warning_only(self, engine: Any) -> None:
        """Verify fixable issues like 'バッテリー上がり' trigger caution/warning, not fatal reject."""
        detail = ListingDetail(
            id="article-dead-battery",
            title="ヤマハ ビーノ 実動 バッテリー上がり キック始動OK 書類あり",
            url="https://jmty.jp/articles/vino-bat",
            price=28000,
            price_text="28,000円",
            description="現在バッテリーが上がっておりセル回りませんが、キックで一発始動します。書類完備。",
            seller=SellerProfile(name="学生ライダー", identified=True, good_ratings=8),
        )
        report = engine.diagnose(detail)
        assert report.verdict != "FATAL_REJECT"
        assert any("バッテリー" in f or "BATTERY" in f for f in report.warning_flags + report.info_flags)


# ===========================================================================
# Tier 1 & 2: Powertrain Classification Tests
# ===========================================================================


class TestPowertrainClassification:
    """Test distinction between 4-stroke Electronic Fuel Injection and 2-stroke Carburetors."""

    def test_4st_fi_identified(self, engine: Any, sample_jog_detail: ListingDetail) -> None:
        """Verify 4-stroke FI is detected and recognized for high reliability/clean emissions."""
        report = engine.diagnose(sample_jog_detail)
        pt_rules = [r for r in report.rules_evaluated if "POWERTRAIN" in r.rule_id or "ENGINE" in r.rule_id]
        assert any("4" in str(r) or "FI" in str(r) for r in pt_rules)

    def test_2st_carb_identified(self, engine: Any, sample_lets2_detail: ListingDetail) -> None:
        """Verify 2-stroke Carburetor is detected with maintenance advisory."""
        report = engine.diagnose(sample_lets2_detail)
        combined_text = " ".join([r.reasoning for r in report.rules_evaluated] + report.info_flags + report.warning_flags)
        assert "2スト" in combined_text or "2-stroke" in combined_text or "キャブ" in combined_text


# ===========================================================================
# Tier 1 & 2: Seller Integrity Audit Tests
# ===========================================================================


class TestSellerIntegrityAudit:
    """Test seller verification badges, rating ratios, and suspicious account detection."""

    def test_verified_seller_high_rating_passes(self, engine: Any, sample_jog_detail: ListingDetail) -> None:
        """Verify verified seller (本人確認済) with 100% positive ratings scores top points."""
        report = engine.diagnose(sample_jog_detail)
        seller_rules = [r for r in report.rules_evaluated if "SELLER" in r.rule_id]
        assert any(r.passed for r in seller_rules)

    def test_unverified_bad_seller_penalized(self, engine: Any, sample_junk_detail: ListingDetail) -> None:
        """Verify unverified seller with high bad ratings ratio triggers warnings."""
        report = engine.diagnose(sample_junk_detail)
        assert any("未認証" in f or "SELLER" in f or "unverified" in f.lower() for f in report.warning_flags + report.fatal_flags)


# ===========================================================================
# Tier 1 & 2: Scoring Model & Output Schema Tests
# ===========================================================================


class TestScoringModelAndOutputSchema:
    """Test deterministic scoring math, verdict boundaries, and --json output structure."""

    def test_healthy_bike_recommended_verdict(self, engine: Any, sample_jog_detail: ListingDetail) -> None:
        """Healthy 4st FI scooter with paperwork and good seller must be RECOMMENDED with score >= 70."""
        report = engine.diagnose(sample_jog_detail)
        assert str(report.verdict) in ("RECOMMENDED", "Verdict.RECOMMENDED")
        assert report.score >= 70

    def test_junk_no_papers_fatal_reject_verdict(self, engine: Any, sample_junk_detail: ListingDetail) -> None:
        """Junk bike with no paperwork must be FATAL_REJECT with score < 40."""
        report = engine.diagnose(sample_junk_detail)
        assert str(report.verdict) in ("FATAL_REJECT", "Verdict.FATAL_REJECT")
        assert report.score < 40

    def test_json_output_schema_compliance(self, engine: Any, sample_jog_detail: ListingDetail) -> None:
        """Verify report.to_dict() complies with contract-first JSON schema."""
        report = engine.diagnose(sample_jog_detail)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "item_id" in d
        assert "title" in d
        assert "verdict" in d
        assert "score" in d
        assert "rules_evaluated" in d
        assert "fatal_flags" in d
        assert "warning_flags" in d
        assert "summary" in d

        # Every evaluated rule must contain rule_id, passed, and reasoning
        for rule in d["rules_evaluated"]:
            assert "rule_id" in rule
            assert "passed" in rule
            assert "reasoning" in rule

        # Must be valid json
        serialized = json.dumps(d)
        assert len(serialized) > 0


# ===========================================================================
# Activity & Contact Timing Audit Tests
# ===========================================================================


class TestActivityAndContactTiming:
    """Test auditing of listing freshness, stale post penalty, and contact timing etiquette."""

    def test_fresh_listing_scores_bonus(self, engine: Any, sample_jog_detail: ListingDetail) -> None:
        """A listing updated 2 days ago receives fresh listing bonus and passes activity audit."""
        sample_jog_detail.updated_at = datetime.now(timezone.utc) - timedelta(days=2)
        report = engine.diagnose(sample_jog_detail)
        activity_rules = [r for r in report.rules_evaluated if "ACTIVITY-001" in r.rule_id]
        assert len(activity_rules) == 1
        assert activity_rules[0].passed is True
        assert activity_rules[0].score_impact == 10
        assert report.posted_at is not None or report.updated_at is not None

    def test_stale_listing_penalized_and_caps_verdict(self, engine: Any, sample_jog_detail: ListingDetail) -> None:
        """A listing updated 75 days ago triggers warning penalty and prevents RECOMMENDED verdict."""
        sample_jog_detail.updated_at = datetime.now(timezone.utc) - timedelta(days=75)
        report = engine.diagnose(sample_jog_detail)
        activity_rules = [r for r in report.rules_evaluated if "ACTIVITY-001" in r.rule_id]
        assert len(activity_rules) == 1
        assert activity_rules[0].passed is False
        assert activity_rules[0].score_impact == -10
        assert any("ACTIVITY-001" in f or "更新滞留" in f for f in report.warning_flags)
        # Even with high base score, verdict is capped at CAUTION
        assert report.verdict == Verdict.CAUTION

    def test_severely_stale_listing_heavy_penalty(self, engine: Any, sample_jog_detail: ListingDetail) -> None:
        """A listing updated 130 days ago triggers high staleness penalty (-20)."""
        sample_jog_detail.updated_at = datetime.now(timezone.utc) - timedelta(days=130)
        report = engine.diagnose(sample_jog_detail)
        activity_rules = [r for r in report.rules_evaluated if "ACTIVITY-001" in r.rule_id]
        assert len(activity_rules) == 1
        assert activity_rules[0].passed is False
        assert activity_rules[0].score_impact == -20
        assert any("放置" in f for f in report.warning_flags)

    def test_contact_timing_rule_evaluates_jst(self, engine: Any, sample_jog_detail: ListingDetail) -> None:
        """Verify contact timing rule evaluates current JST hour and gives etiquette guidance."""
        report = engine.diagnose(sample_jog_detail)
        timing_rules = [r for r in report.rules_evaluated if "ACTIVITY-002" in r.rule_id]
        assert len(timing_rules) == 1
        assert timing_rules[0].passed is True
        assert "日本時間" in timing_rules[0].reasoning

    def test_report_timeline_fields_in_json(self, engine: Any, sample_jog_detail: ListingDetail) -> None:
        """Verify report dictionary contains posted_at and updated_at fields."""
        sample_jog_detail.created_at = datetime(2026, 7, 16, 10, 42, tzinfo=timezone.utc)
        sample_jog_detail.updated_at = datetime(2026, 7, 17, 2, 48, tzinfo=timezone.utc)
        report = engine.diagnose(sample_jog_detail)
        d = report.to_dict()
        assert "posted_at" in d
        assert "updated_at" in d
        assert d["posted_at"] == sample_jog_detail.created_at.isoformat()
        assert d["updated_at"] == sample_jog_detail.updated_at.isoformat()

