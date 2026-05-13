from __future__ import annotations

import json
from datetime import datetime, timedelta

import pandas as pd

from .artifact_loader import PlatformArtifacts
from .database import CreditRepository
from .domain import DashboardSummary, LabelFeedbackMetrics
from .strategy_service import simulate_strategy


def build_dashboard_summary(repo: CreditRepository, artifacts: PlatformArtifacts) -> DashboardSummary:
    apps = repo.list_applications()
    active = repo.get_active_strategy()
    total = len(apps)
    approved = sum(1 for app in apps if app["status"] == "approved")
    pending = sum(1 for app in apps if app["status"] == "pending_review")
    rejected = sum(1 for app in apps if app["status"] == "rejected")
    high_risk = sum(1 for app in apps if float(app["calibrated_pd"]) >= float(active["t2"]))
    avg_score = sum(float(app["score"]) for app in apps) / total if total else float(artifacts.predictions["score"].mean()) if "score" in artifacts.predictions else 0.0
    avg_pd = sum(float(app["calibrated_pd"]) for app in apps) / total if total else float(artifacts.predictions["calibrated_pd"].mean())
    simulation = simulate_strategy(
        artifacts.predictions,
        t1=float(active["t1"]),
        t2=float(active["t2"]),
        fn_cost=float(active["fn_cost"]),
        fp_cost=float(active["fp_cost"]),
        review_cost=float(active["review_cost"]),
    )

    return DashboardSummary(
        today_count=total,
        auto_approve_rate=approved / total if total else simulation.approve_rate,
        review_rate=pending / total if total else simulation.review_rate,
        auto_reject_rate=rejected / total if total else simulation.reject_rate,
        avg_score=avg_score,
        avg_calibrated_pd=avg_pd,
        pending_review_count=pending,
        high_risk_count=high_risk,
        current_strategy_version=str(active["strategy_version"]),
        total_cost=simulation.total_cost,
    )


def build_label_feedback_metrics(repo: CreditRepository, artifacts: PlatformArtifacts) -> LabelFeedbackMetrics:
    feedback = repo.list_label_feedback()
    returned = len(feedback)
    bad_count = sum(1 for row in feedback if int(row["actual_default_label"]) == 1)
    metrics = artifacts.metrics
    return LabelFeedbackMetrics(
        returned_count=returned,
        bad_count=bad_count,
        bad_rate=bad_count / returned if returned else 0.0,
        model_auc=float(metrics.get("roc_auc", 0.0)),
        model_ks=float(metrics.get("ks", 0.0)),
        model_brier=float(metrics.get("brier_score", 0.0)),
    )


def build_operations_trend(repo: CreditRepository) -> pd.DataFrame:
    apps = repo.list_applications()
    today = datetime.now().date()
    rows = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        day_apps = [app for app in apps if datetime.fromisoformat(app["created_at"]).date() == day]
        total = len(day_apps)
        rows.append(
            {
                "date": day.isoformat(),
                "申请量": total,
                "自动通过率": _rate(day_apps, "approved"),
                "人工复核率": _rate(day_apps, "pending_review"),
                "自动拒绝率": _rate(day_apps, "rejected"),
                "平均风险分": _avg(day_apps, "score"),
                "平均校准PD": _avg(day_apps, "calibrated_pd"),
            }
        )
    return pd.DataFrame(rows)


def build_risk_distribution(repo: CreditRepository, artifacts: PlatformArtifacts) -> pd.DataFrame:
    rows = repo.list_scoring_results()
    if rows:
        data = pd.DataFrame(rows)
        data["calibrated_pd"] = data["calibrated_pd"].astype(float)
        data["score"] = data["score"].astype(float)
    else:
        data = artifacts.predictions.copy()
        if "score" not in data:
            data["score"] = 0
    data["风险分层"] = pd.cut(
        data["calibrated_pd"],
        bins=[-0.001, 0.14, 0.42, 1.0],
        labels=["低风险", "中风险", "高风险"],
    )
    return data


def parse_json_field(value: str | None) -> object:
    if not value:
        return []
    return json.loads(value)


def _rate(apps: list[dict], status: str) -> float:
    return sum(1 for app in apps if app["status"] == status) / len(apps) if apps else 0.0


def _avg(apps: list[dict], key: str) -> float:
    values = [float(app[key]) for app in apps if app.get(key) is not None]
    return sum(values) / len(values) if values else 0.0
