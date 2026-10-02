"""Data models for Jimoty diagnostic-first evaluation and triage engine (Milestone 2).

Defines:
- RuleSeverity (FATAL, WARNING, INFO)
- RuleCategory (LEGAL, MECHANICAL, POWERTRAIN, SELLER)
- Verdict (RECOMMENDED, CAUTION, FATAL_REJECT)
- RuleEvaluation: single rule evaluation outcome
- DiagnosticReport: comprehensive evaluation result with .to_dict() and .format_terminal()
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RuleSeverity(str, Enum):
    """Severity classification for diagnostic evaluation rules."""

    FATAL = "FATAL"
    WARNING = "WARNING"
    INFO = "INFO"

    def __str__(self) -> str:
        return self.value


class RuleCategory(str, Enum):
    """Categorization of diagnostic evaluation scope."""

    LEGAL = "LEGAL"
    MECHANICAL = "MECHANICAL"
    POWERTRAIN = "POWERTRAIN"
    SELLER = "SELLER"
    ACTIVITY = "ACTIVITY"

    def __str__(self) -> str:
        return self.value


class Verdict(str, Enum):
    """Deterministic final recommendation verdict."""

    RECOMMENDED = "RECOMMENDED"
    CAUTION = "CAUTION"
    FATAL_REJECT = "FATAL_REJECT"

    def __str__(self) -> str:
        return self.value


@dataclass
class RuleEvaluation:
    """Outcome and rationale of evaluating a single diagnostic rule."""

    rule_id: str
    name: str
    category: RuleCategory
    severity: RuleSeverity
    passed: bool
    reasoning: str
    score_impact: int = 0
    flags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert rule evaluation to a clean JSON-serializable dictionary."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "category": str(self.category),
            "severity": str(self.severity),
            "passed": self.passed,
            "reasoning": self.reasoning,
            "score_impact": self.score_impact,
            "flags": list(self.flags),
            "metadata": dict(self.metadata),
        }

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{self.rule_id}] {self.name} ({status}): {self.reasoning}"


@dataclass
class DiagnosticReport:
    """Comprehensive diagnostic and triage report for a Jimoty listing."""

    item_id: str
    title: str
    price: Optional[int] = None
    url: Optional[str] = None
    verdict: Verdict = Verdict.CAUTION
    score: int = 0
    rules_evaluated: List[RuleEvaluation] = field(default_factory=list)
    fatal_flags: List[str] = field(default_factory=list)
    warning_flags: List[str] = field(default_factory=list)
    info_flags: List[str] = field(default_factory=list)
    summary: str = ""
    posted_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Produce clean, JSON-serializable schema output for --json reporting."""
        return {
            "item_id": self.item_id,
            "title": self.title,
            "price": self.price,
            "url": self.url,
            "verdict": str(self.verdict),
            "score": self.score,
            "summary": self.summary,
            "posted_at": self.posted_at,
            "updated_at": self.updated_at,
            "fatal_flags": list(self.fatal_flags),
            "warning_flags": list(self.warning_flags),
            "info_flags": list(self.info_flags),
            "rules_evaluated": [r.to_dict() for r in self.rules_evaluated],
            "created_at": self.created_at,
        }

    def format_terminal(self) -> str:
        """Render a formatted, human-readable terminal table summary."""
        verdict_icon = {
            Verdict.RECOMMENDED: "🟢 [RECOMMENDED / 購入推奨]",
            Verdict.CAUTION: "🟡 [CAUTION / 要注意・要確認]",
            Verdict.FATAL_REJECT: "🔴 [FATAL_REJECT / 購入不可・重大欠陥]",
        }.get(self.verdict, str(self.verdict))

        # Progress bar for score (0 to 100, 20 blocks)
        bar_len = 20
        filled_len = max(0, min(bar_len, int(self.score / 5)))
        score_bar = "█" * filled_len + "░" * (bar_len - filled_len)

        price_str = f"{self.price:,}円" if self.price is not None else "価格要確認"

        lines = [
            "═" * 78,
            f"  JIMOTY LISTING DIAGNOSTIC REPORT: {verdict_icon}",
            "═" * 78,
            f"  Item ID:   {self.item_id}",
            f"  Title:     {self.title}",
            f"  Price:     {price_str}",
        ]
        if self.posted_at or self.updated_at:
            post_str = self.posted_at[:16].replace("T", " ") if self.posted_at else "不明"
            up_str = self.updated_at[:16].replace("T", " ") if self.updated_at else "なし"
            lines.append(f"  Timeline:  投稿: {post_str} | 最終更新: {up_str}")
        if self.url:
            lines.append(f"  URL:       {self.url}")

        lines.extend([
            f"  Verdict:   {self.verdict.value}",
            f"  Score:     [{score_bar}] {self.score} / 100",
            f"  Summary:   {self.summary}",
            "─" * 78,
        ])

        # Fatal Flags
        if self.fatal_flags:
            lines.append(f"  🚨 FATAL RED FLAGS ({len(self.fatal_flags)}):")
            for flag in self.fatal_flags:
                lines.append(f"    • [FATAL] {flag}")
            lines.append("─" * 78)
        else:
            lines.append("  🚨 FATAL RED FLAGS: 0 (No dealbreaker conditions found)")
            lines.append("─" * 78)

        # Warning Flags
        if self.warning_flags:
            lines.append(f"  ⚠️  WARNINGS & INQUIRY ITEMS ({len(self.warning_flags)}):")
            for flag in self.warning_flags:
                lines.append(f"    • [WARNING] {flag}")
            lines.append("─" * 78)
        else:
            lines.append("  ⚠️  WARNINGS & INQUIRY ITEMS: 0")
            lines.append("─" * 78)

        # Evaluated Rules Table
        lines.append(f"  📋 EVALUATED RULES ({len(self.rules_evaluated)}):")
        for r in self.rules_evaluated:
            if r.passed:
                mark = "✅ PASS"
            elif r.severity == RuleSeverity.FATAL:
                mark = "⛔ FAIL"
            elif r.severity == RuleSeverity.WARNING:
                mark = "⚠️ WARN"
            else:
                mark = "ℹ️ INFO"
            lines.append(f"    {mark:<8} {r.rule_id:<28} {r.reasoning}")

        lines.append("═" * 78)
        return "\n".join(lines)
