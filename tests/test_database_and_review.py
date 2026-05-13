from __future__ import annotations

from pathlib import Path

from credit_platform.database import CreditRepository
from credit_platform.scoring_service import ScoringService
from credit_platform.artifact_loader import load_artifacts


def test_application_state_flow_creates_review_task_and_audit_log(
    tmp_path: Path, sample_artifact_dir: Path
) -> None:
    repo = CreditRepository(tmp_path / "platform.db")
    repo.initialize()
    service = ScoringService(load_artifacts(sample_artifact_dir))

    result = service.score_sample("medium")
    app_id = repo.create_application(result.profile, result)

    pending = repo.list_pending_reviews()
    assert app_id in [row["application_id"] for row in pending]
    assert repo.get_application(app_id)["status"] == "pending_review"

    repo.submit_review(app_id, "approved", "资料完整，可人工通过")
    repo.submit_review(app_id, "rejected", "重复提交应被忽略")

    application = repo.get_application(app_id)
    review = repo.get_review_task(app_id)
    assert application["status"] == "review_approved"
    assert review["review_decision"] == "approved"
    assert review["review_comment"] == "资料完整，可人工通过"
    assert len(repo.list_audit_logs()) >= 2


def test_auto_approve_and_reject_skip_review_queue(tmp_path: Path, sample_artifact_dir: Path) -> None:
    repo = CreditRepository(tmp_path / "platform.db")
    repo.initialize()
    service = ScoringService(load_artifacts(sample_artifact_dir))

    low_id = repo.create_application(service.score_sample("low").profile, service.score_sample("low"))
    high_id = repo.create_application(service.score_sample("high").profile, service.score_sample("high"))

    assert repo.get_application(low_id)["status"] == "approved"
    assert repo.get_application(high_id)["status"] == "rejected"
    assert repo.list_pending_reviews() == []
