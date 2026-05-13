from __future__ import annotations

from pathlib import Path

from credit_platform.artifact_loader import load_artifacts
from credit_platform.database import CreditRepository
from credit_platform.reporting_service import build_dashboard_summary, build_label_feedback_metrics
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
