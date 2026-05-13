from __future__ import annotations

from dataclasses import fields, replace
from typing import Any, Mapping

from .domain import ApplicantProfile


def validate_profile_payload(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(payload.get("customer_id", "")).strip():
        errors.append("客户编号不能为空")
    if not str(payload.get("customer_name", "")).strip():
        errors.append("客户姓名不能为空")
    if _number(payload, "age") < 18:
        errors.append("年龄必须不低于 18 岁")
    if _number(payload, "annual_income") <= 0:
        errors.append("年收入必须大于 0")
    if _number(payload, "credit_amount") <= 0:
        errors.append("贷款金额必须大于 0")
    if _number(payload, "goods_price") <= 0:
        errors.append("商品价格必须大于 0")
    if _number(payload, "annuity_amount") <= 0:
        errors.append("年金必须大于 0")
    utilization = _number(payload, "cc_utilization_ratio_mean")
    if utilization < 0 or utilization > 1:
        errors.append("信用卡利用率必须在 0 到 1 之间")
    if _number(payload, "bureau_debt_sum_total") < 0:
        errors.append("外部债务金额不能小于 0")
    if _number(payload, "bureau_credit_sum_total") < 0:
        errors.append("外部授信金额不能小于 0")
    return errors


def build_profile_from_payload(base: ApplicantProfile, payload: Mapping[str, Any]) -> ApplicantProfile:
    allowed = {field.name for field in fields(ApplicantProfile)}
    values = {key: payload[key] for key in payload.keys() & allowed}
    values["customer_id"] = str(values.get("customer_id", base.customer_id)).strip()
    values["customer_name"] = str(values.get("customer_name", base.customer_name)).strip()
    values["age"] = int(_number(values, "age"))
    values["family_members"] = int(_number(values, "family_members"))
    values["children_count"] = int(_number(values, "children_count"))
    values["days_employed"] = int(_number(values, "days_employed"))
    values["prev_record_count"] = int(_number(values, "prev_record_count"))
    values["inst_overdue_count"] = int(_number(values, "inst_overdue_count"))
    for key in [
        "annual_income",
        "credit_amount",
        "goods_price",
        "annuity_amount",
        "bureau_credit_sum_total",
        "bureau_debt_sum_total",
        "cc_utilization_ratio_mean",
    ]:
        values[key] = float(_number(values, key))
    return replace(base, **values)


def _number(payload: Mapping[str, Any], key: str) -> float:
    value = payload.get(key, 0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
