from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


class ArtifactLoadError(RuntimeError):
    """Raised when the model artifact bundle is missing required files."""


@dataclass(frozen=True)
class PlatformArtifacts:
    artifact_dir: Path
    metrics: dict
    thresholds: dict
    lift_table: pd.DataFrame
    shap_top20: pd.DataFrame
    predictions: pd.DataFrame
    features: pd.DataFrame


def _require(path: Path) -> Path:
    if not path.exists():
        raise ArtifactLoadError(f"Required model artifact is missing: {path.name} ({path})")
    return path


def _read_json(path: Path) -> dict:
    with _require(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_artifacts(artifact_dir: str | Path) -> PlatformArtifacts:
    base = Path(artifact_dir)
    reports = base / "reports"
    predictions_dir = base / "predictions"
    features_dir = base / "features"

    metrics = _read_json(reports / "metrics.json")
    thresholds = _read_json(reports / "thresholds.json")
    lift_table = pd.read_csv(_require(reports / "lift_table.csv"))
    shap_top20 = pd.read_csv(_require(reports / "shap_top20.csv"))
    predictions = pd.read_csv(_require(predictions_dir / "holdout_predictions.csv"))
    features = pd.read_parquet(_require(features_dir / "feature_matrix.parquet"))

    if "SK_ID_CURR" not in predictions.columns or "SK_ID_CURR" not in features.columns:
        raise ArtifactLoadError("Predictions and features must both include SK_ID_CURR.")
    if "calibrated_pd" not in predictions.columns or "decision_band" not in predictions.columns:
        raise ArtifactLoadError("Predictions must include calibrated_pd and decision_band.")

    return PlatformArtifacts(
        artifact_dir=base,
        metrics=metrics,
        thresholds=thresholds,
        lift_table=lift_table,
        shap_top20=shap_top20,
        predictions=predictions,
        features=features,
    )
