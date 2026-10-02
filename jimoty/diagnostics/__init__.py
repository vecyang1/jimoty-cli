"""Diagnostic-First Evaluation & Triage Engine for Jimoty listings (Milestone 2).

Provides deterministic auditing for:
- Legal registration paperwork & stolen vehicle heuristics (DOC-001, DOC-002, DOC-003)
- Mechanical condition & running engine triage (MECH-001, MECH-002, MECH-003, MECH-004)
- Powertrain classification (ENGINE-ENG-001, ENGINE-ENG-002)
- Seller reputation & fraud heuristics (SELLER-001, SELLER-002, SELLER-003)
"""

from __future__ import annotations

from jimoty.diagnostics.engine import DiagnosticEngine
from jimoty.diagnostics.models import (
    DiagnosticReport,
    RuleCategory,
    RuleEvaluation,
    RuleSeverity,
    Verdict,
)
from jimoty.diagnostics.rules import (
    BaseRule,
    BatteryIssueRule,
    EngineSeizedRule,
    MissingPapersRule,
    NoKeysRule,
    NonRunningRule,
    Powertrain2StCarbRule,
    Powertrain4StFiRule,
    RunningConfirmedRule,
    SellerRatingRatioRule,
    SellerUnverifiedSuspiciousRule,
    SellerVerifiedIdRule,
    ValidPapersRule,
    get_default_rules,
)

__all__ = [
    # Engine
    "DiagnosticEngine",
    # Models
    "DiagnosticReport",
    "RuleEvaluation",
    "Verdict",
    "RuleSeverity",
    "RuleCategory",
    # Base and rules
    "BaseRule",
    "get_default_rules",
    "MissingPapersRule",
    "NoKeysRule",
    "ValidPapersRule",
    "EngineSeizedRule",
    "NonRunningRule",
    "RunningConfirmedRule",
    "BatteryIssueRule",
    "Powertrain4StFiRule",
    "Powertrain2StCarbRule",
    "SellerVerifiedIdRule",
    "SellerRatingRatioRule",
    "SellerUnverifiedSuspiciousRule",
]
