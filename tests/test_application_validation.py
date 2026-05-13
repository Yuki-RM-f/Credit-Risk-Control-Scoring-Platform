from __future__ import annotations

from dataclasses import asdict

from credit_platform.application_service import build_profile_from_payload, validate_profile_payload
from credit_platform.artifact_loader import load_artifacts
from credit_platform.scoring_service import ScoringService


def test_profile_payload_validation_rejects_missing_and_invalid_values(sample_artifact_dir) -> None:
    service = ScoringService(load_artifacts(sample_artifact_dir))
    profile = service.score_sample("low").profile
    payload = asdict(profile) | {
        "customer_name": "",
        "age": 17,
        "annual_income": 0,
        "credit_amount": -1,
        "cc_utilization_ratio_mean": 1.4,
    }

    errors = validate_profile_payload(payload)

    assert "客户姓名不能为空" in errors
    assert "年龄必须不低于 18 岁" in errors
    assert "年收入必须大于 0" in errors
    assert "贷款金额必须大于 0" in errors
    assert "信用卡利用率必须在 0 到 1 之间" in errors


def test_build_profile_from_payload_keeps_sample_binding_and_applies_business_edits(sample_artifact_dir) -> None:
    service = ScoringService(load_artifacts(sample_artifact_dir))
    profile = service.score_sample("low").profile
    payload = asdict(profile) | {
        "customer_name": "王测试",
        "annual_income": 360000,
        "credit_amount": 500000,
    }

    edited = build_profile_from_payload(profile, payload)

    assert edited.sample_key == profile.sample_key
    assert edited.source_sk_id_curr == profile.source_sk_id_curr
    assert edited.customer_name == "王测试"
    assert edited.annual_income == 360000
    assert edited.credit_amount == 500000
