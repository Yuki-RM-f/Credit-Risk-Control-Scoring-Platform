from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ApplicantProfile:
    sample_key: str
    sample_label: str
    customer_id: str
    customer_name: str
    age: int
    gender: str
    marital_status: str
    education_type: str
    occupation_type: str
    family_members: int
    children_count: int
    annual_income: float
    days_employed: int
    credit_amount: float
    goods_price: float
    annuity_amount: float
    bureau_credit_sum_total: float
    bureau_debt_sum_total: float
    prev_record_count: int
    inst_overdue_count: int
    cc_utilization_ratio_mean: float
    target_label: int | None = None
    source_sk_id_curr: int | None = None


@dataclass(frozen=True)
class ScoringResult:
    profile: ApplicantProfile
    raw_pd: float
    calibrated_pd: float
    score: float
    risk_level: str
    decision_band: str
    status: str
    strategy_version: str
    reason_codes: list[str] = field(default_factory=list)
    positive_factors: list[dict[str, Any]] = field(default_factory=list)
    negative_factors: list[dict[str, Any]] = field(default_factory=list)
    waterfall: list[dict[str, Any]] = field(default_factory=list)
    model_version: str = "home-credit-xgboost-only-gpu-full"


@dataclass(frozen=True)
class StrategySimulation:
    approve_rate: float
    review_rate: float
    reject_rate: float
    bad_capture_rate: float
    false_negative_count: int
    false_positive_count: int
    review_count: int
    total_cost: float
    total_count: int


@dataclass(frozen=True)
class DashboardSummary:
    today_count: int
    auto_approve_rate: float
    review_rate: float
    auto_reject_rate: float
    avg_score: float
    avg_calibrated_pd: float
    pending_review_count: int
    high_risk_count: int
    current_strategy_version: str
    total_cost: float


@dataclass(frozen=True)
class LabelFeedbackMetrics:
    returned_count: int
    bad_count: int
    bad_rate: float
    model_auc: float
    model_ks: float
    model_brier: float
