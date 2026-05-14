from __future__ import annotations

import ast
import re
from pathlib import Path


APP_SOURCE = Path(__file__).resolve().parents[1] / "app.py"


def _navigation_labels() -> list[str]:
    tree = ast.parse(APP_SOURCE.read_text(encoding="utf-8"))

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "NAV_ITEMS" for target in node.targets):
            continue
        labels = []
        for item in node.value.elts:
            labels.append(item.elts[1].value)
        return labels

    raise AssertionError("NAV_ITEMS is not defined")


def test_page_navigation_uses_streamlit_native_top_navigation() -> None:
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "st.sidebar.radio" not in source
    assert "def render_top_navigation" not in source
    assert "st.navigation" in source
    assert 'position="top"' in source
    assert "st.Page" in source
    assert "NAV_ITEMS" in source


def test_navigation_keeps_business_pages_in_expected_order() -> None:
    expected = ["风控总览", "申请审批", "人工复核", "策略中心", "模型中心", "报表中心", "平台教程"]

    assert _navigation_labels() == expected


def test_tutorial_page_is_routed_and_contains_case_examples() -> None:
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "def tutorial_page" in source
    assert 'title="平台教程"' in source
    assert "低风险客户案例" in source
    assert "中风险客户案例" in source
    assert "高风险客户案例" in source


def test_topbar_has_enough_spacing_below_streamlit_toolbar() -> None:
    source = APP_SOURCE.read_text(encoding="utf-8")
    match = re.search(r"\.block-container\s*\{\s*padding-top:\s*([0-9.]+)rem;", source)

    assert match is not None
    assert float(match.group(1)) >= 4.0


def test_topbar_exposes_local_and_remote_access_addresses() -> None:
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "本地调试地址" in source
    assert "远程访问地址" in source
    assert "CREDIT_PLATFORM_PUBLIC_HOST" in source
    assert "http://<ECS公网IP>:8503" in source
