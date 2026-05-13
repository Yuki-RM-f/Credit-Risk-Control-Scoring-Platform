from __future__ import annotations

from pathlib import Path

from credit_platform.artifact_loader import load_artifacts
from credit_platform.database import CreditRepository
from credit_platform.reporting_service import (
    build_dashboard_alerts,
    build_dashboard_summary,
    build_label_feedback_metrics,
    build_lift_summary,
    build_operations_trend,
)
from credit_platform.scoring_service import ScoringService


def test_dashboard_summary_reflects_persisted_applications(tmp_path: Path, sample_artifact_dir: Path) -> None:
    repo = CreditRepository(tmp_path / "platform.db")
    repo.initialize()
    service = ScoringService(load_artifacts(sample_artifact_dir))

    for key in ["low", "medium", "high"]:
        result = service.score_sample(key)
        repo.create_application(result.profile, result)

    summary = build_dashboard_summary(repo, load_artifacts(sample_artifact_dir))
    assert summary.today_count == 3
    assert summary.auto_approve_rate > 0
    assert summary.pending_review_count == 1
    assert summary.high_risk_count == 1


def test_label_feedback_metrics_refresh_after_feedback(tmp_path: Path, sample_artifact_dir: Path) -> None:
    repo = CreditRepository(tmp_path / "platform.db")
    repo.initialize()
    service = ScoringService(load_artifacts(sample_artifact_dir))
    app_id = repo.create_application(service.score_sample("high").profile, service.score_sample("high"))

    before = build_label_feedback_metrics(repo, load_artifacts(sample_artifact_dir))
    repo.add_label_feedback(app_id, 1)
    after = build_label_feedback_metrics(repo, load_artifacts(sample_artifact_dir))

    assert before.returned_count == 0
    assert after.returned_count == 1
    assert after.bad_rate == 1.0


def test_dashboard_alerts_cover_backlog_strategy_and_stability(
    tmp_path: Path, sample_artifact_dir: Path
) -> None:
    repo = CreditRepository(tmp_path / "platform.db")
    repo.initialize()
    artifacts = load_artifacts(sample_artifact_dir)
    service = ScoringService(artifacts)
    repo.create_application(service.score_sample("medium").profile, service.score_sample("medium"))

    alerts = build_dashboard_alerts(repo, artifacts)

    assert [alert["type"] for alert in alerts] == ["review_backlog", "strategy_mix", "model_stability"]
    assert "待复核积压 1 笔" in alerts[0]["message"]


def test_report_helpers_build_lift_summary_and_period_trends(
    tmp_path: Path, sample_artifact_dir: Path
) -> None:
    repo = CreditRepository(tmp_path / "platform.db")
    repo.initialize()
    artifacts = load_artifacts(sample_artifact_dir)
    service = ScoringService(artifacts)
    repo.create_application(service.score_sample("low").profile, service.score_sample("low"))

    weekly = build_operations_trend(repo, granularity="week")
    monthly = build_operations_trend(repo, granularity="month")
    lift = build_lift_summary(artifacts)

    assert "period" in weekly.columns
    assert "period" in monthly.columns
    assert lift["max_lift"] == 3.8
    assert lift["max_bad_rate"] == 0.30
