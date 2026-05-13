from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture()
def sample_artifact_dir(tmp_path: Path) -> Path:
    base = tmp_path / "home-credit-gpu-full"
    reports = base / "reports"
    predictions = base / "predictions"
    features = base / "features"
    reports.mkdir(parents=True)
    predictions.mkdir()
    features.mkdir()

    (reports / "metrics.json").write_text(
        json.dumps(
            {
                "roc_auc": 0.7876,
                "ks": 0.4345,
                "logloss": 0.2364,
                "brier_score": 0.0656,
                "final_strategy": "xgboost_only",
                "feature_count": 438,
                "calibration_method": "isotonic",
            }
        ),
        encoding="utf-8",
    )
    (reports / "thresholds.json").write_text(
        json.dumps(
            {
                "dual_threshold": {
                    "t1": 0.14,
                    "t2": 0.42,
                    "pass_rate": 0.50,
                    "review_rate": 0.25,
                    "reject_rate": 0.25,
                    "total_cost": 12.5,
                    "bad_capture_rate": 0.60,
                    "review_count": 1,
                }
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        {
            "decile": [1, 10],
            "bad_rate": [0.02, 0.30],
            "lift": [0.3, 3.8],
        }
    ).to_csv(reports / "lift_table.csv", index=False)
    pd.DataFrame(
        {
            "feature": [
                "EXT_SOURCE_2",
                "bureau_debt_credit_ratio_max",
                "inst_overdue_count",
            ],
            "mean_abs_shap": [0.32, 0.12, 0.09],
        }
    ).to_csv(reports / "shap_top20.csv", index=False)

    pd.DataFrame(
        {
            "SK_ID_CURR": [100001, 100002, 100003],
            "TARGET": [0, 0, 1],
            "raw_pd": [0.20, 0.55, 0.82],
            "calibrated_pd": [0.05, 0.22, 0.55],
            "score": [820, 680, 520],
            "decision_band": ["approve", "review", "reject"],
        }
    ).to_csv(predictions / "holdout_predictions.csv", index=False)
    pd.DataFrame(
        {
            "SK_ID_CURR": [100001, 100002, 100003],
            "TARGET": [0, 0, 1],
            "CODE_GENDER": ["F", "M", "M"],
            "NAME_FAMILY_STATUS": ["Married", "Single / not married", "Married"],
            "NAME_EDUCATION_TYPE": ["Higher education", "Secondary / secondary special", "Secondary / secondary special"],
            "OCCUPATION_TYPE": ["Core staff", "Laborers", "Drivers"],
            "CNT_FAM_MEMBERS": [3, 2, 4],
            "CNT_CHILDREN": [1, 0, 2],
            "AMT_INCOME_TOTAL": [240000, 180000, 120000],
            "AMT_CREDIT": [300000, 420000, 650000],
            "AMT_GOODS_PRICE": [280000, 390000, 600000],
            "AMT_ANNUITY": [18000, 26000, 39000],
            "DAYS_BIRTH": [-12000, -15000, -11000],
            "DAYS_EMPLOYED": [-2800, -900, -280],
            "EXT_SOURCE_2": [0.72, 0.35, 0.12],
            "bureau_debt_credit_ratio_max": [0.20, 0.62, 0.88],
            "inst_overdue_count": [0, 1, 5],
            "cc_utilization_ratio_mean": [0.25, 0.48, 0.91],
        }
    ).to_parquet(features / "feature_matrix.parquet", index=False)
    return base
