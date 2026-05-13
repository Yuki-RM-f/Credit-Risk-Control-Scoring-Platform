from __future__ import annotations

import pandas as pd

from .domain import StrategySimulation


def simulate_strategy(
    predictions: pd.DataFrame,
    *,
    t1: float,
    t2: float,
    fn_cost: float,
    fp_cost: float,
    review_cost: float,
) -> StrategySimulation:
    if not 0 <= t1 < t2 <= 1:
        raise ValueError("t1 must be lower than t2 and both thresholds must be within [0, 1].")

    scored = predictions.copy()
    scored["simulated_decision"] = "review"
    scored.loc[scored["calibrated_pd"] < t1, "simulated_decision"] = "approve"
    scored.loc[scored["calibrated_pd"] >= t2, "simulated_decision"] = "reject"

    total = len(scored)
    if total == 0:
        return StrategySimulation(0, 0, 0, 0, 0, 0, 0, 0, 0)

    target = scored["TARGET"] if "TARGET" in scored.columns else pd.Series(0, index=scored.index)
    false_negative_count = int(((scored["simulated_decision"] == "approve") & (target == 1)).sum())
    false_positive_count = int(((scored["simulated_decision"] == "reject") & (target == 0)).sum())
    review_count = int((scored["simulated_decision"] == "review").sum())
    bad_total = int((target == 1).sum())
    rejected_bad = int(((scored["simulated_decision"] == "reject") & (target == 1)).sum())

    total_cost = false_negative_count * fn_cost + false_positive_count * fp_cost + review_count * review_cost

    return StrategySimulation(
        approve_rate=float((scored["simulated_decision"] == "approve").mean()),
        review_rate=float((scored["simulated_decision"] == "review").mean()),
        reject_rate=float((scored["simulated_decision"] == "reject").mean()),
        bad_capture_rate=float(rejected_bad / bad_total) if bad_total else 0.0,
        false_negative_count=false_negative_count,
        false_positive_count=false_positive_count,
        review_count=review_count,
        total_cost=float(total_cost),
        total_count=total,
    )
