"""Deterministic diagnostic runner and scoring engine (Milestone 2).

Evaluates Jimoty vehicle/item listings against rules:
- Legal & Paperwork (DOC-001, DOC-002, DOC-003)
- Mechanical Condition (MECH-001, MECH-002, MECH-003, MECH-004)
- Powertrain Classification (ENGINE-ENG-001, ENGINE-ENG-002)
- Seller Integrity (SELLER-001, SELLER-002, SELLER-003)

Calculates deterministic score (0-100) and assigns Verdict:
- FATAL_REJECT: any FATAL rule failure
- RECOMMENDED: score >= 70 with running engine and valid paperwork
- CAUTION: all other cases
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from jimoty.diagnostics.models import (
    DiagnosticReport,
    RuleCategory,
    RuleEvaluation,
    RuleSeverity,
    Verdict,
)
from jimoty.diagnostics.rules import BaseRule, get_default_rules
from jimoty.models import ListingDetail


class DiagnosticEngine:
    """Deterministic evaluation and triage engine for Jimoty vehicle and goods listings."""

    def __init__(self, rules: Optional[List[BaseRule]] = None) -> None:
        self.rules = rules if rules is not None else get_default_rules()

    def diagnose(self, detail: ListingDetail) -> DiagnosticReport:
        """Run complete deterministic diagnostic triage on a listing detail.

        Args:
            detail: Structured ListingDetail instance.

        Returns:
            DiagnosticReport containing evaluated rules, score, flags, and verdict.
        """
        rules_evaluated: List[RuleEvaluation] = []
        fatal_flags: List[str] = []
        warning_flags: List[str] = []
        info_flags: List[str] = []

        raw_score = 50  # Baseline neutral score

        for rule in self.rules:
            res = rule.evaluate(detail)
            rules_evaluated.append(res)
            raw_score += res.score_impact

            # Collect flags based on severity and outcome
            if not res.passed:
                if res.severity == RuleSeverity.FATAL:
                    for flag in res.flags:
                        if flag not in fatal_flags:
                            fatal_flags.append(flag)
                elif res.severity == RuleSeverity.WARNING:
                    for flag in res.flags:
                        if flag not in warning_flags:
                            warning_flags.append(flag)
            else:
                for flag in res.flags:
                    if flag not in info_flags:
                        info_flags.append(flag)

        # Determine condition flags
        has_fatal = len(fatal_flags) > 0
        has_valid_papers = any(
            r.rule_id == "DOC-003-VALID_PAPERS" and r.passed for r in rules_evaluated
        )
        has_running_engine = any(
            r.rule_id == "MECH-003-RUNNING_CONFIRMED" and r.passed for r in rules_evaluated
        )
        is_stale = any(
            r.rule_id == "ACTIVITY-001-STALE_LISTING" and not r.passed for r in rules_evaluated
        )

        # Score normalization
        if has_fatal:
            # Fatal listings are capped strictly below 40 (typically 5 to 25)
            final_score = max(5, min(raw_score, 25))
            verdict = Verdict.FATAL_REJECT
        elif raw_score >= 70 and has_valid_papers and has_running_engine and not is_stale:
            final_score = min(100, max(70, raw_score))
            verdict = Verdict.RECOMMENDED
        else:
            final_score = max(30, min(69, raw_score))
            verdict = Verdict.CAUTION

        # Generate summary
        if verdict == Verdict.FATAL_REJECT:
            primary_reasons = ", ".join(fatal_flags[:2])
            summary = (
                f"【購入不可】重大欠陥または法的リスクが検出されました（{primary_reasons}）。"
                "公道登録不可・高額修理リスクのため取引見送りを強く推奨します。"
            )
        elif verdict == Verdict.RECOMMENDED:
            summary = (
                "【購入推奨】実動確認済みかつ正規登録書類（廃車申告受付書・譲渡証明書）が揃っており、"
                "出品者信頼性・出品鮮度も良好な優良候補車両です。"
            )
        else:
            if warning_flags:
                primary_warns = ", ".join(warning_flags[:2])
                summary = (
                    f"【要確認・注意】取引前に出品者への事前確認事項があります（{primary_warns}）。"
                    "現車確認での状態チェックと書類確認を推奨します。"
                )
            else:
                summary = "【要確認】現車確認にてエンジンの始動・灯火類および登録書類の現物確認を推奨します。"

        now_iso = datetime.now(timezone.utc).isoformat()

        return DiagnosticReport(
            item_id=detail.id,
            title=detail.title,
            price=detail.price,
            url=detail.url,
            verdict=verdict,
            score=final_score,
            rules_evaluated=rules_evaluated,
            fatal_flags=fatal_flags,
            warning_flags=warning_flags,
            info_flags=info_flags,
            summary=summary,
            posted_at=detail.created_at.isoformat() if detail.created_at else None,
            updated_at=detail.updated_at.isoformat() if detail.updated_at else None,
            created_at=now_iso,
        )
