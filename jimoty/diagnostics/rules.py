"""Deterministic diagnostic and triage rules for Jimoty vehicle and goods listings (Milestone 2).

Rule Catalog:
- Legal & Paperwork:
  * DOC-001-MISSING_PAPERS (FATAL)
  * DOC-002-NO_KEYS (WARNING)
  * DOC-003-VALID_PAPERS (INFO / WARNING when unmentioned)
- Mechanical Triage:
  * MECH-001-ENGINE_SEIZED (FATAL)
  * MECH-002-NON_RUNNING (FATAL)
  * MECH-003-RUNNING_CONFIRMED (INFO / score boost)
  * MECH-004-BATTERY_ISSUE (WARNING)
- Powertrain Classification:
  * ENGINE-ENG-001-4S_FI (INFO / score boost)
  * ENGINE-ENG-002-2S_CARB (INFO / maintenance advisory)
- Seller Integrity:
  * SELLER-001-VERIFIED_ID (INFO / WARNING)
  * SELLER-002-RATING_RATIO (INFO / WARNING)
  * SELLER-003-UNVERIFIED_SUSPICIOUS (WARNING)
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import re
import unicodedata
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from jimoty.diagnostics.models import RuleCategory, RuleEvaluation, RuleSeverity
from jimoty.models import ListingDetail


def normalize_text(text: str) -> str:
    """Normalize Japanese text with NFKC (half-width katakana, full-width alnum conversion)."""
    if not text:
        return ""
    return unicodedata.normalize("NFKC", text)


class BaseRule(ABC):
    """Abstract base class for all deterministic diagnostic rules."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        category: RuleCategory,
        severity: RuleSeverity,
    ) -> None:
        self.rule_id = rule_id
        self.name = name
        self.category = category
        self.severity = severity

    @abstractmethod
    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        """Evaluate the rule against a ListingDetail instance."""
        raise NotImplementedError


# ===========================================================================
# Legal & Paperwork Rules
# ===========================================================================


class MissingPapersRule(BaseRule):
    """DOC-001: Audit for missing registration documents or stolen vehicle risk."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="DOC-001-MISSING_PAPERS",
            name="登録書類欠落・盗難リスク検査",
            category=RuleCategory.LEGAL,
            severity=RuleSeverity.FATAL,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        text = normalize_text(f"{detail.title or ''}\n{detail.description or ''}")

        missing_keywords = [
            "書類なし",
            "書類紛失",
            "書類無し",
            "書類ありません",
            "書類等なし",
            "登録不可",
            "再登録不可",
            "再登録はできません",
            "再登録できません",
            "盗難車",
            "ナンバー登録不可",
            "ナンバー取得不可",
            "抹消書なし",
            "書類は一切ありません",
            "書類ありません",
        ]

        found_keywords = [kw for kw in missing_keywords if kw in text]

        if found_keywords:
            flag_msg = "書類なし / 登録不可 (DOC-001: 盗難車リスク・公道再登録不可)"
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                reasoning=(
                    f"書類なし・再登録不可の文言が検出されました ({', '.join(found_keywords)})。"
                    "盗難車リスクおよび名義変更・公道登録不可のため購入不可です。"
                ),
                score_impact=-50,
                flags=[flag_msg],
                metadata={"matched_keywords": found_keywords},
            )

        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            reasoning="書類欠落や登録不可に関する明示的な警告文は見当たりません。",
            score_impact=0,
        )


class NoKeysRule(BaseRule):
    """DOC-002: Audit for missing ignition keys."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="DOC-002-NO_KEYS",
            name="鍵（キー）欠落検査",
            category=RuleCategory.LEGAL,
            severity=RuleSeverity.WARNING,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        text = normalize_text(f"{detail.title or ''}\n{detail.description or ''}")

        no_key_keywords = [
            "鍵なし",
            "カギなし",
            "キーなし",
            "鍵紛失",
            "カギ紛失",
            "キー紛失",
            "メインキーなし",
            "キー欠品",
        ]

        found_keywords = [kw for kw in no_key_keywords if kw in text]

        if found_keywords:
            flag_msg = "鍵なし (DOC-002: キーシリンダー交換または鍵作成費用が必要)"
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                reasoning=(
                    f"鍵なし・キー紛失の記載があります ({', '.join(found_keywords)})。"
                    "鍵作成またはシリンダー交換等の追加費用が発生します。"
                ),
                score_impact=-15,
                flags=[flag_msg],
                metadata={"matched_keywords": found_keywords},
            )

        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            reasoning="鍵の欠落に関する記載はありません。",
            score_impact=0,
        )


class ValidPapersRule(BaseRule):
    """DOC-003: Verify official vehicle registration and transfer paperwork."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="DOC-003-VALID_PAPERS",
            name="公的登録書類確認検査",
            category=RuleCategory.LEGAL,
            severity=RuleSeverity.INFO,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        text = normalize_text(f"{detail.title or ''}\n{detail.description or ''}")

        valid_keywords = [
            "廃車申告受付書",
            "廃車証明書",
            "譲渡証明書",
            "標識交付証明書",
            "廃車書",
            "書類あり",
            "書類あります",
            "書類完備",
            "登録書類あり",
            "返納証明書",
            "自動車検査証",
            "自賠責",
            "軽自動車届出済証",
        ]

        found_valid = [kw for kw in valid_keywords if kw in text]

        # Check if missing paperwork was already mentioned
        missing_markers = ["書類なし", "書類紛失", "書類無し", "登録不可", "再登録不可", "書類ありません"]
        has_missing = any(kw in text for kw in missing_markers)

        if found_valid and not has_missing:
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning=(
                    f"正規の登録書類（{', '.join(found_valid)}）の記載が確認できました。"
                    "再登録・名義変更手続きがスムーズです。"
                ),
                score_impact=20,
                flags=["登録書類あり (DOC-003: 廃車申告受付書・譲渡証明書等の記載を確認)"],
                metadata={"matched_valid": found_valid},
            )

        if has_missing:
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.FATAL,
                passed=False,
                reasoning="登録書類がありません (DOC-001により重大欠陥判定)。",
                score_impact=0,
            )

        # Unmentioned paperwork -> Warning for caution/inquiry
        flag_msg = "書類記載なし (DOC-003: 廃車申告受付書・譲渡証明書の有無を出品者に事前要確認)"
        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            category=self.category,
            severity=RuleSeverity.WARNING,
            passed=False,
            reasoning=(
                "登録書類（廃車申告受付書、譲渡証明書など）に関する明確な記載がありません。"
                "取引前に出品者への書類有無の確認が必須です。"
            ),
            score_impact=-15,
            flags=[flag_msg],
        )


# ===========================================================================
# Mechanical Triage Rules
# ===========================================================================


class EngineSeizedRule(BaseRule):
    """MECH-001: Detect engine seizure, no compression, or jammed kick lever."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="MECH-001-ENGINE_SEIZED",
            name="エンジン焼き付き・圧縮固着検査",
            category=RuleCategory.MECHANICAL,
            severity=RuleSeverity.FATAL,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        text = normalize_text(f"{detail.title or ''}\n{detail.description or ''}")

        seized_keywords = [
            "焼き付き",
            "焼付き",
            "圧縮なし",
            "キック降りない",
            "キック降りません",
            "キック固着",
            "エンジンブロー",
            "クランク焼き付き",
        ]

        found_keywords = [kw for kw in seized_keywords if kw in text]

        if found_keywords:
            flag_msg = "エンジン焼き付き・キック固着 (MECH-001: 重大故障・要OH/エンジン換装)"
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                reasoning=(
                    f"エンジン焼き付きまたはキック固着・圧縮なしの記述があります ({', '.join(found_keywords)})。"
                    "重大な機械的破損であり、要腰上OHまたはエンジン換装のリスクがあります。"
                ),
                score_impact=-50,
                flags=[flag_msg],
                metadata={"matched_keywords": found_keywords},
            )

        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            reasoning="エンジン焼き付きやキック固着等の致命的破損の記述はありません。",
            score_impact=0,
        )


class NonRunningRule(BaseRule):
    """MECH-002: Flag non-running, junk, or scrap vehicle listings."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="MECH-002-NON_RUNNING",
            name="不動・ジャンク・部品取り検査",
            category=RuleCategory.MECHANICAL,
            severity=RuleSeverity.FATAL,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        text = normalize_text(f"{detail.title or ''}\n{detail.description or ''}")

        junk_keywords = ["不動", "ジャンク", "部品取り", "レストアベース", "直せる方"]
        matched_junk = [kw for kw in junk_keywords if kw in text]

        # Battery explanation check for "セル回らない"
        starter_not_turning = any(kw in text for kw in ["セル回らない", "セル回りません", "セル回りず"])
        battery_dead = any(kw in text for kw in ["バッテリー上がり", "バッテリー上がって", "バッテリー要交換", "バッテリーあがり", "バッテリー弱"])
        kick_starts = any(kw in text for kw in ["キック始動", "キック一発", "キックで一発", "キックで始動"])
        running_confirmed = "実動" in text or "実働" in text

        # If it's explicitly junk/non-running
        if matched_junk:
            flag_msg = "不動車・ジャンク品 (MECH-002: 不動・部品取り扱い)"
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                reasoning=(
                    f"不動車または部品取り・ジャンク品として出品されています ({', '.join(matched_junk)})。"
                    "自走引取不可・公道走行不能リスクがあります。"
                ),
                score_impact=-40,
                flags=[flag_msg],
                metadata={"matched_keywords": matched_junk},
            )

        # Starter not turning without kick start or battery explanation
        if starter_not_turning and not (battery_dead or kick_starts or running_confirmed):
            flag_msg = "セル不作動・始動不能 (MECH-002: セル始動不能・原因不明)"
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                reasoning="セルが回らない記載があります。始動系統または電装の重大不具合の可能性があります。",
                score_impact=-30,
                flags=[flag_msg],
            )

        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            reasoning="不動・ジャンク・部品取りなどの非実動表記は見当たりません。",
            score_impact=0,
        )


class RunningConfirmedRule(BaseRule):
    """MECH-003: Verify confirmed running engine condition and drivability."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="MECH-003-RUNNING_CONFIRMED",
            name="実動・走行可能確認検査",
            category=RuleCategory.MECHANICAL,
            severity=RuleSeverity.INFO,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        text = normalize_text(f"{detail.title or ''}\n{detail.description or ''}")

        running_keywords = [
            "実動",
            "実働",
            "セル一発",
            "キック一発",
            "セル・キックともに一発",
            "走る曲がる止まる問題なし",
            "走る曲がる止まる",
            "エンジン好調",
            "機関良好",
            "一発始動",
            "快調",
            "好調",
        ]

        # Ignore if marked as junk or non-running
        is_junk = any(kw in text for kw in ["不動です", "ジャンク品", "部品取り専用"])
        found_running = [kw for kw in running_keywords if kw in text]

        if found_running and not is_junk:
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning=(
                    f"実動確認済み ({', '.join(found_running)}) です。"
                    "セル・キック始動、走る曲がる止まる動作が確認されています。"
                ),
                score_impact=20,
                flags=["実動確認済み (MECH-003: 始動・走行可能)"],
                metadata={"matched_keywords": found_running},
            )

        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            category=self.category,
            severity=RuleSeverity.WARNING,
            passed=False,
            reasoning="明確な実動・走行可能の記述が確認できません。現車確認での動作チェックが必要です。",
            score_impact=-10,
        )


class BatteryIssueRule(BaseRule):
    """MECH-004: Detect discharged or dead battery condition (warning only)."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="MECH-004-BATTERY_ISSUE",
            name="バッテリー状態検査",
            category=RuleCategory.MECHANICAL,
            severity=RuleSeverity.WARNING,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        text = normalize_text(f"{detail.title or ''}\n{detail.description or ''}")

        battery_keywords = [
            "バッテリー上がり",
            "バッテリー上がって",
            "バッテリー要交換",
            "バッテリーあがり",
            "バッテリー弱",
            "バッテリー死んで",
            "バッテリーNG",
        ]

        found_battery = [kw for kw in battery_keywords if kw in text]

        if found_battery:
            flag_msg = "バッテリー上がり (MECH-004: バッテリー要交換または充電)"
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.WARNING,
                passed=False,
                reasoning=(
                    f"バッテリー上がりの記載があります ({', '.join(found_battery)})。"
                    "バッテリー交換（費用3,000円〜）または充電が必要です。"
                ),
                score_impact=-5,
                flags=[flag_msg],
                metadata={"matched_keywords": found_battery},
            )

        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            category=self.category,
            severity=RuleSeverity.INFO,
            passed=True,
            reasoning="バッテリーの不具合に関する記載はありません。",
            score_impact=0,
        )


# ===========================================================================
# Powertrain Classification Rules
# ===========================================================================


class Powertrain4StFiRule(BaseRule):
    """ENGINE-ENG-001-4S_FI: Classify 4-stroke electronic fuel injection powertrain."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="ENGINE-ENG-001-4S_FI",
            name="4ストローク電子制御インジェクション (4st FI)",
            category=RuleCategory.POWERTRAIN,
            severity=RuleSeverity.INFO,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        text = normalize_text(f"{detail.title or ''}\n{detail.description or ''}")

        is_4st = bool(re.search(r"4スト|4st|4サイクル|4ストローク|4-stroke", text, re.IGNORECASE))
        is_fi = bool(re.search(r"\bFI\b|インジェクション|フューエルインジェクション|電子制御|PGM-FI", text, re.IGNORECASE))

        if is_4st or is_fi:
            flags = ["4ストFI (ENGINE-ENG-001: 始動性・燃費・耐久性に優れた4ストFI)"] if (is_4st and is_fi) else []
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning=(
                    "4ストローク電子制御燃料噴射 (4スト FI / 4st FI) 車両です。"
                    "冬季でも優れた始動性、高燃費、クリーンな排気、高い耐久性を持ちます。"
                ),
                score_impact=5,
                flags=flags,
                metadata={"is_4st": is_4st, "is_fi": is_fi},
            )

        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            category=self.category,
            severity=RuleSeverity.INFO,
            passed=False,
            reasoning="4ストロークFI車両の特定には至りませんでした。",
            score_impact=0,
        )


class Powertrain2StCarbRule(BaseRule):
    """ENGINE-ENG-002-2S_CARB: Classify 2-stroke or carbureted powertrain with maintenance advisory."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="ENGINE-ENG-002-2S_CARB",
            name="2ストローク・キャブレター車区分",
            category=RuleCategory.POWERTRAIN,
            severity=RuleSeverity.INFO,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        text = normalize_text(f"{detail.title or ''}\n{detail.description or ''}")

        is_2st = bool(re.search(r"2スト|2st|2サイクル|2ストローク|2-stroke", text, re.IGNORECASE))
        is_carb = bool(re.search(r"キャブ|キャブレター|キャブ車|carburetor", text, re.IGNORECASE))

        if is_2st or is_carb:
            flag_msg = "2スト・キャブ車 (ENGINE-ENG-002: 2ストオイル補充およびキャブメンテナンスが必要)"
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning=(
                    "2ストローク・キャブレター車 (2スト / キャブ) です。"
                    "力強い加速性能がありますが、2ストオイルの定期補充、冬季の暖機運転、"
                    "キャブレターの定期清掃・オーバーホール等の維持管理が必要です。"
                ),
                score_impact=-5,
                flags=[flag_msg],
                metadata={"is_2st": is_2st, "is_carb": is_carb},
            )

        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            category=self.category,
            severity=RuleSeverity.INFO,
            passed=False,
            reasoning="2ストロークまたはキャブレター車には該当しません。",
            score_impact=0,
        )


# ===========================================================================
# Seller Reputation Rules
# ===========================================================================


class SellerVerifiedIdRule(BaseRule):
    """SELLER-001: Verify identity certification badge (本人確認済)."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="SELLER-001-VERIFIED_ID",
            name="出品者本人確認（身元確認）検査",
            category=RuleCategory.SELLER,
            severity=RuleSeverity.WARNING,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        seller = detail.seller

        if seller and seller.identified:
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning="出品者は本人確認済みです (本人確認済バッジあり)。取引信頼性が高いです。",
                score_impact=5,
                flags=["本人確認済 (SELLER-001: 出品者の身元確認完了)"],
            )

        flag_msg = "出品者未認証 (SELLER-001: 本人確認未完了のアカウント)"
        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            category=self.category,
            severity=RuleSeverity.WARNING,
            passed=False,
            reasoning="出品者の本人確認が完了していません (未認証アカウント)。直接取引の際は身元確認にご注意ください。",
            score_impact=-10,
            flags=[flag_msg],
        )


class SellerRatingRatioRule(BaseRule):
    """SELLER-002: Evaluate seller positive review percentage and volume."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="SELLER-002-RATING_RATIO",
            name="出品者評価比率・実績検査",
            category=RuleCategory.SELLER,
            severity=RuleSeverity.WARNING,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        seller = detail.seller

        if not seller or seller.total_ratings == 0:
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning="出品者の過去取引評価履歴がありません (新規出品者)。",
                score_impact=0,
            )

        ratio = seller.positive_ratio
        good = seller.good_ratings
        bad = seller.bad_ratings
        total = seller.total_ratings

        if ratio >= 0.90:
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning=f"出品者評価が極めて良好です (良い評価 {good}/{total}件, 良好率 {ratio*100:.1f}%)。",
                score_impact=5,
                flags=[f"高評価出品者 (SELLER-002: 良い評価率 {ratio*100:.1f}%)"],
            )

        if ratio >= 0.80:
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning=f"出品者評価は概ね普通です (良い評価 {good}/{total}件, 良好率 {ratio*100:.1f}%)。",
                score_impact=0,
            )

        flag_msg = f"出品者低評価率高 (SELLER-002: 良い評価率 {ratio*100:.1f}%, 悪い評価 {bad}件)"
        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            category=self.category,
            severity=RuleSeverity.WARNING,
            passed=False,
            reasoning=f"出品者の悪い評価率が高めです (良い評価 {good}件, 悪い評価 {bad}件, 良好率 {ratio*100:.1f}%)。",
            score_impact=-15,
            flags=[flag_msg],
        )


class SellerUnverifiedSuspiciousRule(BaseRule):
    """SELLER-003: Detect suspicious accounts combining unverified status with bad ratings."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="SELLER-003-UNVERIFIED_SUSPICIOUS",
            name="未認証・低評価アカウント総合警戒",
            category=RuleCategory.SELLER,
            severity=RuleSeverity.WARNING,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        seller = detail.seller

        if not seller:
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning="出品者情報がありません。",
                score_impact=0,
            )

        is_suspicious = (
            not seller.identified
            and seller.bad_ratings > 0
            and (
                seller.positive_ratio < 0.75
                or seller.bad_ratings >= seller.good_ratings
                or seller.bad_ratings >= 2
            )
        )

        if is_suspicious:
            flag_msg = "出品者未認証・低評価 (SELLER-003: 本人確認未完了かつ悪い評価が複数存在、取引リスク高)"
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.WARNING,
                passed=False,
                reasoning=(
                    f"出品者は本人確認未完了であり、かつ悪い評価が複数存在します (悪い評価 {seller.bad_ratings}件)。"
                    "トラブル防止のため慎重な対応または取引見送りが推奨されます。"
                ),
                score_impact=-20,
                flags=[flag_msg],
            )

        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            category=self.category,
            severity=RuleSeverity.INFO,
            passed=True,
            reasoning="不審な未認証・低評価アカウントのパターンには該当しません。",
            score_impact=0,
        )


# ===========================================================================
# Listing Recency & Activity Rules
# ===========================================================================


class StaleListingRule(BaseRule):
    """ACTIVITY-001: Audit listing recency, updated timestamp, and seller contactability risk."""

    def __init__(self, stale_days_threshold: int = 60, dead_days_threshold: int = 120) -> None:
        super().__init__(
            rule_id="ACTIVITY-001-STALE_LISTING",
            name="投稿更新鮮度・放置リスク検査",
            category=RuleCategory.ACTIVITY,
            severity=RuleSeverity.WARNING,
        )
        self.stale_days_threshold = stale_days_threshold
        self.dead_days_threshold = dead_days_threshold

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        last_dt = detail.updated_at or detail.created_at
        if not last_dt:
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning="投稿日時の明示的記録が確認できませんでした。取引前の在庫・対応可否確認を推奨します。",
                score_impact=0,
            )

        now = datetime.now(timezone.utc)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone(timedelta(hours=9)))

        diff_days = max(0.0, (now - last_dt).total_seconds() / 86400.0)
        date_str = last_dt.strftime("%Y-%m-%d")

        if diff_days >= self.dead_days_threshold:
            flag_msg = f"投稿放置リスク (ACTIVITY-001: 最終更新から約{int(diff_days)}日経過、出品者離脱・他所譲渡済みの可能性大)"
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.WARNING,
                passed=False,
                reasoning=(
                    f"最終更新から約{int(diff_days)}日（{date_str}）が経過しています。"
                    "出品者がジモティーを放置しているか、他所で既に譲渡済みのまま投稿が残っている可能性が極めて高く、"
                    "連絡がつかないリスクがあります。取引前に在庫確認が必須です。"
                ),
                score_impact=-20,
                flags=[flag_msg],
                metadata={"days_since_update": int(diff_days), "last_updated": date_str},
            )
        elif diff_days >= self.stale_days_threshold:
            flag_msg = f"更新滞留 (ACTIVITY-001: 最終更新から約{int(diff_days)}日経過、応答遅延リスクあり)"
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.WARNING,
                passed=False,
                reasoning=(
                    f"最終更新から約{int(diff_days)}日（{date_str}）が経過しています。"
                    "出品者の連絡応答率が低下している可能性があるため、購入決定前に取引可能か在庫確認を推奨します。"
                ),
                score_impact=-10,
                flags=[flag_msg],
                metadata={"days_since_update": int(diff_days), "last_updated": date_str},
            )
        elif diff_days <= 7:
            flag_msg = f"新規・活発更新 (ACTIVITY-001: 最終更新から{int(diff_days)}日以内の新鮮な投稿)"
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning=(
                    f"最終更新から{int(diff_days)}日以内（{date_str}）の非常に新鮮な投稿です。"
                    "出品者のアクティブ度が高く、迅速な連絡・取引対応が期待できます。"
                ),
                score_impact=10,
                flags=[flag_msg],
                metadata={"days_since_update": int(diff_days), "last_updated": date_str},
            )
        else:
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning=f"最終更新から約{int(diff_days)}日（{date_str}）経過しています。通常のアクティブ範囲内です。",
                score_impact=0,
                metadata={"days_since_update": int(diff_days), "last_updated": date_str},
            )


class ContactTimingRule(BaseRule):
    """ACTIVITY-002: Advisory check on seller contact time-of-day and etiquette."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="ACTIVITY-002-TIME_COURTESY",
            name="連絡時間帯・応答マナー配慮",
            category=RuleCategory.ACTIVITY,
            severity=RuleSeverity.INFO,
        )

    def evaluate(self, detail: ListingDetail) -> RuleEvaluation:
        jst = timezone(timedelta(hours=9))
        now_jst = datetime.now(jst)
        hour = now_jst.hour
        is_night = (hour >= 22 or hour < 7)

        if is_night:
            reasoning = (
                f"現在日本時間 {now_jst.strftime('%H:%M')}（深夜早朝帯）です。"
                "ジモティーでは夜間通知をオフにしている出品者が多く、早朝・深夜の連絡は通知迷惑・返信遅延の原因となります。"
                "急ぎでない場合は日中（9:00〜21:00）の連絡、または『夜分遅くに失礼いたします』等の敬語配慮を推奨します。"
            )
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning=reasoning,
                score_impact=0,
                metadata={"current_jst_hour": hour},
            )
        else:
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                category=self.category,
                severity=RuleSeverity.INFO,
                passed=True,
                reasoning=f"現在日本時間 {now_jst.strftime('%H:%M')}（日中・連絡推奨時間帯）です。出品者への連絡がスムーズに行える適切な時間帯です。",
                score_impact=0,
                metadata={"current_jst_hour": hour},
            )


def get_default_rules() -> List[BaseRule]:
    """Return the ordered list of all standard diagnostic rules."""
    return [
        MissingPapersRule(),
        NoKeysRule(),
        ValidPapersRule(),
        EngineSeizedRule(),
        NonRunningRule(),
        RunningConfirmedRule(),
        BatteryIssueRule(),
        Powertrain4StFiRule(),
        Powertrain2StCarbRule(),
        SellerVerifiedIdRule(),
        SellerRatingRatioRule(),
        SellerUnverifiedSuspiciousRule(),
        StaleListingRule(),
        ContactTimingRule(),
    ]
