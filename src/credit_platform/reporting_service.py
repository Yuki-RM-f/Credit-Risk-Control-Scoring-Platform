from __future__ import annotations

import json
from datetime import date, datetime, timedelta

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


def build_dashboard_alerts(repo: CreditRepository, artifacts: PlatformArtifacts) -> list[dict[str, str]]:
    summary = build_dashboard_summary(repo, artifacts)
    active = repo.get_active_strategy()
    simulation = simulate_strategy(
        artifacts.predictions,
        t1=float(active["t1"]),
        t2=float(active["t2"]),
        fn_cost=float(active["fn_cost"]),
        fp_cost=float(active["fp_cost"]),
        review_cost=float(active["review_cost"]),
    )
    psi = float(artifacts.metrics.get("psi", 0.0) or 0.0)
    csi = float(artifacts.metrics.get("csi", 0.0) or 0.0)
    drift_value = max(psi, csi)

    backlog_level = "warn" if summary.pending_review_count >= 3 else "info"
    strategy_level = "warn" if simulation.review_rate >= 0.35 else "info"
    stability_level = "warn" if drift_value >= 0.1 else "info"

    return [
        {
            "type": "review_backlog",
            "level": backlog_level,
            "title": "待复核积压",
            "message": f"待复核积压 {summary.pending_review_count} 笔",
        },
        {
            "type": "strategy_mix",
            "level": strategy_level,
            "title": "策略分流",
            "message": f"当前样本复核率 {simulation.review_rate:.1%}，拒绝率 {simulation.reject_rate:.1%}",
        },
        {
            "type": "model_stability",
            "level": stability_level,
            "title": "模型稳定性",
            "message": f"PSI {psi:.3f}，CSI {csi:.3f}",
        },
    ]


def build_lift_summary(artifacts: PlatformArtifacts) -> dict[str, float]:
    lift = artifacts.lift_table.copy()
    lift_col = "lift" if "lift" in lift.columns else lift.columns[-1]
    bad_rate_col = "bad_rate" if "bad_rate" in lift.columns else None
    max_lift = float(lift[lift_col].max()) if not lift.empty else 0.0
    max_bad_rate = float(lift[bad_rate_col].max()) if bad_rate_col and not lift.empty else 0.0
    return {
        "max_lift": max_lift,
        "max_bad_rate": max_bad_rate,
        "bucket_count": float(len(lift)),
    }


def build_operations_trend(repo: CreditRepository, granularity: str = "day") -> pd.DataFrame:
    if granularity not in {"day", "week", "month"}:
        raise ValueError("granularity must be day, week, or month")
    apps = repo.list_applications()
    if granularity != "day":
        return _build_period_trend(apps, granularity)

    today = datetime.now().date()
    rows = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        day_apps = [app for app in apps if datetime.fromisoformat(app["created_at"]).date() == day]
        total = len(day_apps)
        rows.append(
            {
                "date": day.isoformat(),
                "period": day.isoformat(),
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


def _build_period_trend(apps: list[dict], granularity: str) -> pd.DataFrame:
    buckets: dict[str, list[dict]] = {}
    if not apps:
        today = date.today()
        buckets[_period_label(today, granularity)] = []
    for app in apps:
        created = datetime.fromisoformat(app["created_at"]).date()
        buckets.setdefault(_period_label(created, granularity), []).append(app)

    rows = []
    for period, period_apps in sorted(buckets.items()):
        rows.append(
            {
                "date": period,
                "period": period,
                "申请量": len(period_apps),
                "自动通过率": _rate(period_apps, "approved"),
                "人工复核率": _rate(period_apps, "pending_review"),
                "自动拒绝率": _rate(period_apps, "rejected"),
                "平均风险分": _avg(period_apps, "score"),
                "平均校准PD": _avg(period_apps, "calibrated_pd"),
            }
        )
    return pd.DataFrame(rows)


def _period_label(value: date, granularity: str) -> str:
    if granularity == "week":
        year, week, _ = value.isocalendar()
        return f"{year}-W{week:02d}"
    if granularity == "month":
        return value.strftime("%Y-%m")
    return value.isoformat()


def _rate(apps: list[dict], status: str) -> float:
    return sum(1 for app in apps if app["status"] == status) / len(apps) if apps else 0.0


def _avg(apps: list[dict], key: str) -> float:
    values = [float(app[key]) for app in apps if app.get(key) is not None]
    return sum(values) / len(values) if values else 0.0
