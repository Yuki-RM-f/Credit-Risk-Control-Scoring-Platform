from __future__ import annotations

from pathlib import Path

import pytest

from credit_platform.artifact_loader import load_artifacts
from credit_platform.scoring_service import ScoringService
from credit_platform.strategy_service import simulate_strategy


def test_sample_scoring_uses_true_prediction_bands(sample_artifact_dir: Path) -> None:
    service = ScoringService(load_artifacts(sample_artifact_dir))

    assert service.score_sample("low").decision_band == "approve"
    assert service.score_sample("medium").decision_band == "review"
    assert service.score_sample("high").decision_band == "reject"
    assert service.score_sample("high").reason_codes
    assert service.score_sample("high").waterfall


def test_strategy_simulation_rates_sum_to_one(sample_artifact_dir: Path) -> None:
    artifacts = load_artifacts(sample_artifact_dir)
    result = simulate_strategy(artifacts.predictions, t1=0.14, t2=0.42, fn_cost=5, fp_cost=1, review_cost=0.4)

    assert result.approve_rate + result.review_rate + result.reject_rate == pytest.approx(1.0)
    assert result.total_count == 3
    assert result.total_cost > 0


def test_strategy_simulation_rejects_invalid_thresholds(sample_artifact_dir: Path) -> None:
    artifacts = load_artifacts(sample_artifact_dir)

    with pytest.raises(ValueError, match="t1 must be lower than t2"):
        simulate_strategy(artifacts.predictions, t1=0.42, t2=0.14, fn_cost=5, fp_cost=1, review_cost=0.4)
