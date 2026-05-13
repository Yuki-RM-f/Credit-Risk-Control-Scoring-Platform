from __future__ import annotations

from pathlib import Path

import pytest

from credit_platform.artifact_loader import ArtifactLoadError, load_artifacts


def test_load_artifacts_reads_required_reports_and_predictions(sample_artifact_dir: Path) -> None:
    artifacts = load_artifacts(sample_artifact_dir)

    assert artifacts.metrics["roc_auc"] == 0.7876
    assert artifacts.thresholds["dual_threshold"]["t1"] == 0.14
    assert set(artifacts.predictions["decision_band"]) == {"approve", "review", "reject"}
    assert "EXT_SOURCE_2" in artifacts.features.columns


def test_load_artifacts_fails_with_clear_message_for_missing_file(sample_artifact_dir: Path) -> None:
    (sample_artifact_dir / "reports" / "metrics.json").unlink()

    with pytest.raises(ArtifactLoadError, match="metrics.json"):
        load_artifacts(sample_artifact_dir)
