from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

import pandas as pd

from .artifact_loader import PlatformArtifacts
from .domain import ApplicantProfile, ScoringResult


SAMPLE_LABELS = {
    "low": "低风险自动通过客户",
    "medium": "中风险人工复核客户",
    "high": "高风险自动拒绝客户",
    "thin_file": "征信薄文件客户",
    "high_debt": "高收入高负债客户",
    "overdue": "历史逾期客户",
}

DECISION_STATUS = {
    "approve": "approved",
    "review": "pending_review",
    "reject": "rejected",
}

FEATURE_REASON_MAP = {
    "EXT_SOURCE_2": {
        "negative": "外部信用评分偏低",
        "positive": "外部信用评分表现较好",
    },
    "bureau_debt_credit_ratio_max": {
        "negative": "外部债务授信比偏高",
        "positive": "外部债务授信比健康",
    },
    "inst_overdue_count": {
        "negative": "历史分期存在多次逾期",
        "positive": "历史分期还款表现稳定",
    },
    "cc_utilization_ratio_mean": {
        "negative": "信用卡额度使用率偏高",
        "positive": "信用卡额度使用率较低",
    },
    "DAYS_EMPLOYED": {
        "negative": "当前在职稳定性偏弱",
        "positive": "职业稳定性较好",
    },
    "AMT_CREDIT": {
        "negative": "本次贷款金额相对收入偏高",
        "positive": "本次贷款金额处于可承受区间",
    },
}


class ScoringService:
    def __init__(self, artifacts: PlatformArtifacts, strategy_version: str = "S20260511_01") -> None:
        self.artifacts = artifacts
        self.strategy_version = strategy_version
        self._sample_rows = self._build_sample_rows()

    def list_samples(self) -> dict[str, str]:
        return {key: SAMPLE_LABELS[key] for key in SAMPLE_LABELS if key in self._sample_rows}

    def score_sample(self, sample_key: str) -> ScoringResult:
        if sample_key not in self._sample_rows:
            raise KeyError(f"Unknown sample customer: {sample_key}")

        row = self._sample_rows[sample_key]
        profile = self._profile_from_row(sample_key, row)
        calibrated_pd = float(row["calibrated_pd"])
        raw_pd = float(row.get("raw_pd", calibrated_pd))
        score = float(row.get("score", _pd_to_score(calibrated_pd)))
        decision_band = str(row["decision_band"])
        risk_level = _risk_level(calibrated_pd)
        negative, positive = self._factor_lists(row, risk_level)

        if decision_band == "reject":
            reason_codes = [item["reason"] for item in negative[:3]] or ["校准 PD 已超过自动拒绝阈值"]
        elif decision_band == "review":
            reason_codes = [item["reason"] for item in negative[:3]] or ["风险水平处于人工复核区间"]
        else:
            reason_codes = [item["reason"] for item in positive[:2]] or ["风险水平低于自动通过阈值"]

        return ScoringResult(
            profile=profile,
            raw_pd=raw_pd,
            calibrated_pd=calibrated_pd,
            score=score,
            risk_level=risk_level,
            decision_band=decision_band,
            status=DECISION_STATUS.get(decision_band, "pending_review"),
            strategy_version=self.strategy_version,
            reason_codes=reason_codes,
            positive_factors=positive,
            negative_factors=negative,
            waterfall=self._waterfall(calibrated_pd, negative, positive),
        )

    def _build_sample_rows(self) -> dict[str, pd.Series]:
        merged = self.artifacts.predictions.merge(
            self.artifacts.features,
            on="SK_ID_CURR",
            how="left",
            suffixes=("", "_feature"),
        )
        samples: dict[str, pd.Series] = {}
        samples["low"] = _pick_band(merged, "approve", "lowest")
        samples["medium"] = _pick_band(merged, "review", "median")
        samples["high"] = _pick_band(merged, "reject", "highest")
        samples["thin_file"] = _pick_thin_file(merged)
        samples["high_debt"] = _pick_high_debt(merged)
        samples["overdue"] = _pick_overdue(merged)
        return samples

    def _profile_from_row(self, sample_key: str, row: pd.Series) -> ApplicantProfile:
        sk_id = int(row["SK_ID_CURR"])
        income = _float(row, "AMT_INCOME_TOTAL", 180000)
        credit = _float(row, "AMT_CREDIT", 250000)
        debt_ratio = _float(row, "bureau_debt_credit_ratio_max", credit / max(income, 1))
        bureau_credit = _float(row, "bureau_credit_sum_total", max(credit * 0.7, 1))
        bureau_debt = _float(row, "bureau_debt_sum_total", bureau_credit * min(max(debt_ratio, 0), 1.5))

        return ApplicantProfile(
            sample_key=sample_key,
            sample_label=SAMPLE_LABELS[sample_key],
            customer_id=f"C{sk_id}",
            customer_name=_customer_name(sample_key),
            age=max(18, int(abs(_float(row, "DAYS_BIRTH", -12000)) // 365)),
            gender=_gender(row.get("CODE_GENDER", "F")),
            marital_status=str(row.get("NAME_FAMILY_STATUS", "Married")),
            education_type=str(row.get("NAME_EDUCATION_TYPE", "Secondary / secondary special")),
            occupation_type=str(row.get("OCCUPATION_TYPE", "Staff")),
            family_members=int(_float(row, "CNT_FAM_MEMBERS", 2)),
            children_count=int(_float(row, "CNT_CHILDREN", 0)),
            annual_income=income,
            days_employed=int(abs(_float(row, "DAYS_EMPLOYED", -1000))),
            credit_amount=credit,
            goods_price=_float(row, "AMT_GOODS_PRICE", credit * 0.92),
            annuity_amount=_float(row, "AMT_ANNUITY", credit * 0.08),
            bureau_credit_sum_total=bureau_credit,
            bureau_debt_sum_total=bureau_debt,
            prev_record_count=int(_float(row, "prev_record_count", 2)),
            inst_overdue_count=int(_float(row, "inst_overdue_count", 0)),
            cc_utilization_ratio_mean=_float(row, "cc_utilization_ratio_mean", 0.35),
            target_label=int(_float(row, "TARGET", 0)) if "TARGET" in row else None,
            source_sk_id_curr=sk_id,
        )

    def _factor_lists(self, row: pd.Series, risk_level: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        negative: list[dict[str, Any]] = []
        positive: list[dict[str, Any]] = []
        shap_weights = dict(
            zip(
                self.artifacts.shap_top20["feature"].astype(str),
                self.artifacts.shap_top20["mean_abs_shap"].astype(float),
                strict=False,
            )
        )

        def add(feature: str, direction: str, value: float, threshold: str) -> None:
            reason = FEATURE_REASON_MAP[feature][direction]
            item = {
                "feature": feature,
                "reason": reason,
                "value": value,
                "threshold": threshold,
                "impact": float(shap_weights.get(feature, 0.04)),
            }
            if direction == "negative":
                negative.append(item)
            else:
                positive.append(item)

        ext2 = _float(row, "EXT_SOURCE_2", math.nan)
        if not math.isnan(ext2):
            if ext2 < 0.30:
                add("EXT_SOURCE_2", "negative", ext2, "< 0.30")
            elif ext2 > 0.60:
                add("EXT_SOURCE_2", "positive", ext2, "> 0.60")

        debt_ratio = _float(row, "bureau_debt_credit_ratio_max", math.nan)
        if not math.isnan(debt_ratio):
            if debt_ratio > 0.60:
                add("bureau_debt_credit_ratio_max", "negative", debt_ratio, "> 0.60")
            elif debt_ratio < 0.35:
                add("bureau_debt_credit_ratio_max", "positive", debt_ratio, "< 0.35")

        overdue = _float(row, "inst_overdue_count", 0)
        if overdue > 0:
            add("inst_overdue_count", "negative", overdue, "> 0")
        else:
            add("inst_overdue_count", "positive", overdue, "= 0")

        utilization = _float(row, "cc_utilization_ratio_mean", math.nan)
        if not math.isnan(utilization):
            if utilization > 0.70:
                add("cc_utilization_ratio_mean", "negative", utilization, "> 0.70")
            elif utilization < 0.35:
                add("cc_utilization_ratio_mean", "positive", utilization, "< 0.35")

        income = _float(row, "AMT_INCOME_TOTAL", 1)
        credit = _float(row, "AMT_CREDIT", 0)
        credit_income_ratio = credit / max(income, 1)
        if credit_income_ratio > 3.0:
            add("AMT_CREDIT", "negative", credit_income_ratio, "> 3.0x income")
        elif credit_income_ratio < 1.8:
            add("AMT_CREDIT", "positive", credit_income_ratio, "< 1.8x income")

        negative.sort(key=lambda item: item["impact"], reverse=True)
        positive.sort(key=lambda item: item["impact"], reverse=True)

        if risk_level == "high" and not negative:
            negative.append({"feature": "calibrated_pd", "reason": "校准 PD 偏高", "value": _float(row, "calibrated_pd", 0), "threshold": ">= 0.42", "impact": 0.08})
        return negative, positive

    @staticmethod
    def _waterfall(
        calibrated_pd: float,
        negative: list[dict[str, Any]],
        positive: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        baseline = 0.08
        points: list[dict[str, Any]] = [{"factor": "基准风险", "pd": baseline, "delta": baseline}]
        current = baseline
        for item in positive[:2]:
            delta = -min(item["impact"] / 4, 0.035)
            current = max(current + delta, 0.001)
            points.append({"factor": item["reason"], "pd": current, "delta": delta})
        for item in negative[:3]:
            delta = min(item["impact"] / 3, 0.08)
            current = min(current + delta, 0.95)
            points.append({"factor": item["reason"], "pd": current, "delta": delta})
        points.append({"factor": "最终校准 PD", "pd": calibrated_pd, "delta": calibrated_pd - current})
        return points


def result_to_payload(result: ScoringResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["profile"] = asdict(result.profile)
    return payload


def _pick_band(frame: pd.DataFrame, band: str, mode: str) -> pd.Series:
    subset = frame[frame["decision_band"] == band].sort_values("calibrated_pd")
    if subset.empty:
        subset = frame.sort_values("calibrated_pd")
    if mode == "lowest":
        return subset.iloc[0]
    if mode == "highest":
        return subset.iloc[-1]
    return subset.iloc[len(subset) // 2]


def _pick_thin_file(frame: pd.DataFrame) -> pd.Series:
    ext_cols = [col for col in ["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"] if col in frame.columns]
    if not ext_cols:
        return _pick_band(frame, "review", "median")
    ranked = frame.copy()
    ranked["_thin_score"] = ranked[ext_cols].isna().sum(axis=1) - ranked[ext_cols].fillna(0).sum(axis=1)
    return ranked.sort_values(["_thin_score", "calibrated_pd"], ascending=[False, False]).iloc[0]


def _pick_high_debt(frame: pd.DataFrame) -> pd.Series:
    ranked = frame.copy()
    income = ranked.get("AMT_INCOME_TOTAL", pd.Series(1, index=ranked.index)).replace(0, 1)
    ranked["_debt_pressure"] = ranked.get("AMT_CREDIT", 0) / income
    return ranked.sort_values(["_debt_pressure", "calibrated_pd"], ascending=[False, False]).iloc[0]


def _pick_overdue(frame: pd.DataFrame) -> pd.Series:
    if "inst_overdue_count" not in frame.columns:
        return _pick_band(frame, "reject", "highest")
    return frame.sort_values(["inst_overdue_count", "calibrated_pd"], ascending=[False, False]).iloc[0]


def _float(row: pd.Series, column: str, default: float) -> float:
    value = row.get(column, default)
    if pd.isna(value):
        return float(default)
    return float(value)


def _risk_level(calibrated_pd: float) -> str:
    if calibrated_pd < 0.14:
        return "low"
    if calibrated_pd < 0.42:
        return "medium"
    return "high"


def _pd_to_score(pd_value: float) -> float:
    pd_value = min(max(pd_value, 0.000001), 0.999999)
    b = 50 / math.log(2)
    a = 700 + b * math.log(20)
    return round(min(max(a - b * math.log(pd_value / (1 - pd_value)), 300), 900), 2)


def _gender(value: object) -> str:
    text = str(value)
    if text == "M":
        return "male"
    if text == "F":
        return "female"
    return "unknown"


def _customer_name(sample_key: str) -> str:
    names = {
        "low": "张安然",
        "medium": "李谨慎",
        "high": "王高险",
        "thin_file": "赵薄档",
        "high_debt": "陈高负",
        "overdue": "刘逾期",
    }
    return names.get(sample_key, "样例客户")
