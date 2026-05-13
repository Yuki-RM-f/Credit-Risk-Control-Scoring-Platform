from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from credit_platform.bootstrap import initialize_platform
from credit_platform.database import CreditRepository
from credit_platform.domain import ScoringResult
from credit_platform.reporting_service import (
    build_dashboard_summary,
    build_label_feedback_metrics,
    build_operations_trend,
    build_risk_distribution,
    parse_json_field,
)
from credit_platform.scoring_service import ScoringService
from credit_platform.strategy_service import simulate_strategy


st.set_page_config(
    page_title="信用风控评分平台",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource(show_spinner=False)
def load_runtime():
    return initialize_platform(seed_demo=True)


NAV_ITEMS = [
    ("overview", "风控总览"),
    ("application", "申请审批"),
    ("review", "人工复核"),
    ("strategy", "策略中心"),
    ("model", "模型中心"),
    ("reports", "报表中心"),
    ("tutorial", "平台教程"),
]


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #f6f8fb;
            --panel: #ffffff;
            --text: #172033;
            --muted: #657089;
            --line: #e7ebf2;
            --blue: #2563eb;
            --green: #10a36f;
            --amber: #d97706;
            --red: #dc2626;
        }
        .stApp { background: var(--bg); color: var(--text); }
        section[data-testid="stSidebar"],
        div[data-testid="stSidebarCollapsedControl"] {
            display: none;
        }
        .block-container { padding-top: 4.25rem; padding-bottom: 2rem; }
        h1, h2, h3 { letter-spacing: 0; color: var(--text); }
        .topbar {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 16px 18px;
            box-shadow: 0 12px 30px rgba(23, 32, 51, 0.05);
            margin-bottom: 12px;
        }
        .topbar-title {
            font-size: 22px;
            line-height: 1.2;
            font-weight: 800;
            color: var(--text);
        }
        .topbar-caption {
            color: var(--muted);
            font-size: 13px;
            margin-top: 4px;
        }
        .topbar-meta {
            color: var(--blue);
            font-size: 13px;
            font-weight: 700;
            margin-top: 8px;
        }
        div[data-testid="stMetric"] {
            background: #fff;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 14px 16px;
            box-shadow: 0 8px 24px rgba(23, 32, 51, 0.04);
        }
        .section-title {
            font-size: 18px;
            font-weight: 700;
            margin: 0 0 10px 0;
            color: var(--text);
        }
        .subtle {
            color: var(--muted);
            font-size: 13px;
            margin-top: -6px;
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 700;
            border: 1px solid transparent;
        }
        .pill-approved { color: var(--green); background: #eaf8f1; border-color: #bfe8d4; }
        .pill-review { color: var(--amber); background: #fff7ed; border-color: #fed7aa; }
        .pill-rejected { color: var(--red); background: #fef2f2; border-color: #fecaca; }
        .reason-chip {
            display: inline-block;
            margin: 4px 6px 4px 0;
            padding: 6px 10px;
            border-radius: 8px;
            background: #f1f5f9;
            color: #334155;
            font-size: 12px;
        }
        .alert-line {
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid var(--line);
            background: #fff;
            margin-bottom: 8px;
        }
        .tutorial-card {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 16px;
            min-height: 150px;
            box-shadow: 0 8px 24px rgba(23, 32, 51, 0.04);
        }
        .tutorial-card strong {
            display: block;
            color: var(--text);
            font-size: 15px;
            margin-bottom: 8px;
        }
        .tutorial-card p {
            color: var(--muted);
            font-size: 13px;
            line-height: 1.65;
            margin: 0;
        }
        .tutorial-step {
            background: #ffffff;
            border-left: 4px solid var(--blue);
            border-radius: 8px;
            padding: 12px 14px;
            margin-bottom: 10px;
            border-top: 1px solid var(--line);
            border-right: 1px solid var(--line);
            border-bottom: 1px solid var(--line);
        }
        .tutorial-step b {
            color: var(--text);
        }
        .tutorial-step span {
            color: var(--muted);
            font-size: 13px;
        }
        .stButton > button {
            border-radius: 8px;
            border: 1px solid #d7deea;
            font-weight: 700;
            min-height: 40px;
        }
        .stButton > button[kind="primary"] {
            background: var(--blue);
            border-color: var(--blue);
        }
        .stButton > button[kind="secondary"] {
            background: #ffffff;
            color: #334155;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def fmt_pd(value: float) -> str:
    return f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return f"{value:,.0f}"


def decision_pill(decision: str) -> str:
    mapping = {
        "approve": ("自动通过", "pill-approved"),
        "review": ("人工复核", "pill-review"),
        "reject": ("自动拒绝", "pill-rejected"),
        "approved": ("已通过", "pill-approved"),
        "pending_review": ("待复核", "pill-review"),
        "rejected": ("已拒绝", "pill-rejected"),
        "review_approved": ("复核通过", "pill-approved"),
        "review_rejected": ("复核拒绝", "pill-rejected"),
    }
    label, klass = mapping.get(decision, (decision, "pill-review"))
    return f'<span class="status-pill {klass}">{label}</span>'


def page_header(title: str, caption: str) -> None:
    st.markdown(f"## {title}")
    st.markdown(f"<div class='subtle'>{caption}</div>", unsafe_allow_html=True)


def render_app_header() -> None:
    st.markdown(
        """
        <div class="topbar">
            <div class="topbar-title">信用风控评分平台</div>
            <div class="topbar-caption">Home Credit artifact-backed MVP</div>
            <div class="topbar-meta">业务闭环：申请接入 -> 模型评分 -> 策略决策 -> 人工复核 -> 监控报表</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def plotly_layout(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=26, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#172033"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#edf1f7")
    return fig


def overview_page(repo: CreditRepository, artifacts) -> None:
    page_header("风控总览", "今日经营、风险结构、策略效果和模型稳定性")
    summary = build_dashboard_summary(repo, artifacts)

    cols = st.columns(6)
    cols[0].metric("今日申请量", fmt_num(summary.today_count))
    cols[1].metric("自动通过率", fmt_pct(summary.auto_approve_rate))
    cols[2].metric("人工复核率", fmt_pct(summary.review_rate))
    cols[3].metric("自动拒绝率", fmt_pct(summary.auto_reject_rate))
    cols[4].metric("平均风险分", f"{summary.avg_score:.0f}")
    cols[5].metric("平均校准 PD", fmt_pd(summary.avg_calibrated_pd))

    trend = build_operations_trend(repo)
    risk_df = build_risk_distribution(repo, artifacts)

    left, mid, right = st.columns([1.2, 1.1, 0.9])
    with left:
        st.markdown("<div class='section-title'>近 7 日经营趋势</div>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=trend["date"], y=trend["申请量"], name="申请量", marker_color="#2563eb"))
        fig.add_trace(
            go.Scatter(
                x=trend["date"],
                y=trend["自动通过率"] * 100,
                name="通过率",
                yaxis="y2",
                line=dict(color="#10a36f", width=3),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=trend["date"],
                y=trend["人工复核率"] * 100,
                name="复核率",
                yaxis="y2",
                line=dict(color="#d97706", width=3),
            )
        )
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", ticksuffix="%"))
        st.plotly_chart(plotly_layout(fig), width="stretch")

    with mid:
        st.markdown("<div class='section-title'>风险结构</div>", unsafe_allow_html=True)
        fig = px.histogram(
            risk_df,
            x="calibrated_pd",
            nbins=28,
            color="风险分层",
            color_discrete_map={"低风险": "#10a36f", "中风险": "#d97706", "高风险": "#dc2626"},
        )
        st.plotly_chart(plotly_layout(fig), width="stretch")

    with right:
        st.markdown("<div class='section-title'>工作台</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="alert-line">待复核积压 <b>{summary.pending_review_count}</b> 笔</div>
            <div class="alert-line">今日高风险客户 <b>{summary.high_risk_count}</b> 笔</div>
            <div class="alert-line">策略版本 <b>{summary.current_strategy_version}</b></div>
            <div class="alert-line">当前样本策略成本 <b>{summary.total_cost:,.1f}</b></div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div class='section-title'>当前申请明细</div>", unsafe_allow_html=True)
    app_df = pd.DataFrame(repo.list_applications())
    if not app_df.empty:
        display = app_df[
            [
                "application_id",
                "customer_name",
                "score",
                "calibrated_pd",
                "decision_band",
                "status",
                "strategy_version",
                "created_at",
            ]
        ].copy()
        display["calibrated_pd"] = display["calibrated_pd"].astype(float).map(lambda value: f"{value:.2%}")
        st.dataframe(display, width="stretch", hide_index=True)
    else:
        st.info("暂无申请记录")


def application_page(repo: CreditRepository, service: ScoringService) -> None:
    page_header("申请审批", "单笔录入、样例评分、审批结果与申请列表")
    samples = service.list_samples()
    label_to_key = {label: key for key, label in samples.items()}
    selected_label = st.selectbox("样例客户", list(label_to_key.keys()))
    sample_key = label_to_key[selected_label]
    result = service.score_sample(sample_key)
    profile = result.profile

    tabs = st.tabs(["基本信息", "申请信息", "收入与负债", "历史行为"])
    with tabs[0]:
        c1, c2, c3, c4 = st.columns(4)
        c1.text_input("客户编号", profile.customer_id, disabled=True)
        c2.text_input("客户姓名", profile.customer_name, disabled=True)
        c3.number_input("年龄", value=profile.age, disabled=True)
        c4.text_input("职业类别", profile.occupation_type, disabled=True)
    with tabs[1]:
        c1, c2, c3, c4 = st.columns(4)
        c1.number_input("贷款金额", value=float(profile.credit_amount), disabled=True)
        c2.number_input("商品价格", value=float(profile.goods_price), disabled=True)
        c3.number_input("年金", value=float(profile.annuity_amount), disabled=True)
        c4.text_input("申请渠道", "线上进件", disabled=True)
    with tabs[2]:
        c1, c2, c3, c4 = st.columns(4)
        c1.number_input("年收入", value=float(profile.annual_income), disabled=True)
        c2.number_input("在职天数", value=profile.days_employed, disabled=True)
        c3.number_input("外部授信金额", value=float(profile.bureau_credit_sum_total), disabled=True)
        c4.number_input("外部债务金额", value=float(profile.bureau_debt_sum_total), disabled=True)
    with tabs[3]:
        c1, c2, c3, c4 = st.columns(4)
        c1.number_input("历史申请次数", value=profile.prev_record_count, disabled=True)
        c2.number_input("历史逾期次数", value=profile.inst_overdue_count, disabled=True)
        c3.number_input("信用卡利用率", value=float(profile.cc_utilization_ratio_mean), disabled=True)
        c4.number_input("子女数", value=profile.children_count, disabled=True)

    submitted = st.button("提交评分", type="primary", width="content")
    if submitted:
        app_id = repo.create_application(result.profile, result)
        st.session_state["last_application_id"] = app_id
        st.success(f"评分完成：{app_id}")

    st.markdown("<div class='section-title'>当前评分结果</div>", unsafe_allow_html=True)
    render_scoring_result(result, st.session_state.get("last_application_id", "待提交"))

    st.markdown("<div class='section-title'>申请列表</div>", unsafe_allow_html=True)
    app_df = pd.DataFrame(repo.list_applications())
    if not app_df.empty:
        app_df["calibrated_pd"] = app_df["calibrated_pd"].astype(float).map(lambda value: f"{value:.2%}")
        st.dataframe(
            app_df[
                [
                    "application_id",
                    "customer_id",
                    "customer_name",
                    "score",
                    "calibrated_pd",
                    "decision_band",
                    "status",
                    "created_at",
                ]
            ],
            width="stretch",
            hide_index=True,
        )


def render_scoring_result(result: ScoringResult, application_id: str) -> None:
    cols = st.columns([0.9, 0.9, 0.9, 1.3])
    cols[0].markdown(decision_pill(result.decision_band), unsafe_allow_html=True)
    cols[1].metric("风险分", f"{result.score:.0f}")
    cols[2].metric("校准 PD", fmt_pd(result.calibrated_pd))
    cols[3].metric("申请编号", application_id)

    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("主要原因码")
        chips = "".join(f"<span class='reason-chip'>{reason}</span>" for reason in result.reason_codes)
        st.markdown(chips, unsafe_allow_html=True)
        factors = pd.DataFrame(result.negative_factors + result.positive_factors)
        if not factors.empty:
            st.dataframe(factors[["reason", "value", "threshold", "impact"]], width="stretch", hide_index=True)
    with right:
        waterfall = pd.DataFrame(result.waterfall)
        fig = px.bar(
            waterfall,
            x="factor",
            y="pd",
            color="delta",
            color_continuous_scale=["#10a36f", "#e5e7eb", "#dc2626"],
        )
        st.plotly_chart(plotly_layout(fig, height=280), width="stretch")


def review_page(repo: CreditRepository) -> None:
    page_header("人工复核", "待复核工作台与复核处理")
    pending = repo.list_pending_reviews()
    if not pending:
        st.success("当前没有待复核申请")
        return

    pending_df = pd.DataFrame(pending)
    pending_df["calibrated_pd"] = pending_df["calibrated_pd"].astype(float).map(lambda value: f"{value:.2%}")
    st.dataframe(
        pending_df[["application_id", "customer_name", "score", "calibrated_pd", "reason_codes", "created_at"]],
        width="stretch",
        hide_index=True,
    )

    selected = st.selectbox("复核申请", pending_df["application_id"].tolist())
    row = next(item for item in pending if item["application_id"] == selected)
    st.markdown(decision_pill("pending_review"), unsafe_allow_html=True)
    st.metric("风险分", f"{float(row['score']):.0f}")
    st.metric("校准 PD", fmt_pd(float(row["calibrated_pd"])))

    negative = parse_json_field(row.get("negative_factors"))
    if negative:
        st.markdown("负向影响因素")
        st.dataframe(pd.DataFrame(negative)[["reason", "value", "threshold", "impact"]], width="stretch", hide_index=True)

    comment = st.text_area("复核意见", value="补充资料完整，历史还款表现可接受")
    c1, c2 = st.columns(2)
    if c1.button("复核通过", type="primary", width="stretch"):
        repo.submit_review(selected, "approved", comment)
        st.success("复核结论已提交")
        st.rerun()
    if c2.button("复核拒绝", width="stretch"):
        repo.submit_review(selected, "rejected", comment)
        st.warning("复核结论已提交")
        st.rerun()


def strategy_page(repo: CreditRepository, artifacts) -> None:
    page_header("策略中心", "当前策略、阈值试算、成本矩阵与版本历史")
    active = repo.get_active_strategy()
    cols = st.columns(5)
    cols[0].metric("当前版本", active["strategy_version"])
    cols[1].metric("t1 自动通过", f"{float(active['t1']):.2f}")
    cols[2].metric("t2 自动拒绝", f"{float(active['t2']):.2f}")
    cols[3].metric("漏判成本", f"{float(active['fn_cost']):.1f}")
    cols[4].metric("复核成本", f"{float(active['review_cost']):.1f}")

    left, right = st.columns([0.9, 1.1])
    with left:
        t1 = st.slider("t1 自动通过阈值", 0.01, 0.40, float(active["t1"]), 0.01)
        t2 = st.slider("t2 自动拒绝阈值", 0.15, 0.90, float(active["t2"]), 0.01)
        fn_cost = st.number_input("漏判违约客户成本", min_value=0.0, value=float(active["fn_cost"]), step=0.5)
        fp_cost = st.number_input("误拒好客户成本", min_value=0.0, value=float(active["fp_cost"]), step=0.5)
        review_cost = st.number_input("人工复核成本", min_value=0.0, value=float(active["review_cost"]), step=0.1)
    with right:
        try:
            simulation = simulate_strategy(
                artifacts.predictions,
                t1=t1,
                t2=t2,
                fn_cost=fn_cost,
                fp_cost=fp_cost,
                review_cost=review_cost,
            )
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("通过率", fmt_pct(simulation.approve_rate))
            c2.metric("复核率", fmt_pct(simulation.review_rate))
            c3.metric("拒绝率", fmt_pct(simulation.reject_rate))
            c4.metric("总成本", f"{simulation.total_cost:,.1f}")
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=["通过", "复核", "拒绝"],
                        y=[simulation.approve_rate, simulation.review_rate, simulation.reject_rate],
                        marker_color=["#10a36f", "#d97706", "#dc2626"],
                    )
                ]
            )
            st.plotly_chart(plotly_layout(fig, height=280), width="stretch")
            if st.button("发布为新策略版本", type="primary"):
                repo.publish_strategy(t1=t1, t2=t2, fn_cost=fn_cost, fp_cost=fp_cost, review_cost=review_cost)
                st.success("策略已发布")
                st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    st.markdown("<div class='section-title'>策略版本历史</div>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(repo.list_strategy_versions()), width="stretch", hide_index=True)


def model_page(artifacts) -> None:
    page_header("模型中心", "模型概览、效果、解释与稳定性")
    metrics = artifacts.metrics
    cols = st.columns(5)
    cols[0].metric("ROC-AUC", f"{float(metrics.get('roc_auc', 0)):.4f}")
    cols[1].metric("KS", f"{float(metrics.get('ks', 0)):.4f}")
    cols[2].metric("LogLoss", f"{float(metrics.get('logloss', 0)):.4f}")
    cols[3].metric("Brier", f"{float(metrics.get('brier_score', 0)):.4f}")
    cols[4].metric("特征数", f"{int(metrics.get('feature_count', 0))}")

    left, right = st.columns(2)
    with left:
        st.markdown("<div class='section-title'>Lift 曲线</div>", unsafe_allow_html=True)
        lift = artifacts.lift_table.copy()
        x_col = "decile" if "decile" in lift.columns else lift.columns[0]
        y_col = "lift" if "lift" in lift.columns else lift.columns[-1]
        fig = px.line(lift, x=x_col, y=y_col, markers=True)
        st.plotly_chart(plotly_layout(fig), width="stretch")
    with right:
        st.markdown("<div class='section-title'>全局 SHAP Top 20</div>", unsafe_allow_html=True)
        shap_df = artifacts.shap_top20.head(20).sort_values("mean_abs_shap")
        fig = px.bar(
            shap_df,
            x="mean_abs_shap",
            y="feature",
            orientation="h",
            color="mean_abs_shap",
            color_continuous_scale="Blues",
        )
        st.plotly_chart(plotly_layout(fig), width="stretch")

    calibration = artifacts.artifact_dir / "reports" / "calibration_curve.png"
    if calibration.exists():
        st.markdown("<div class='section-title'>Calibration Curve</div>", unsafe_allow_html=True)
        st.image(str(calibration), width="stretch")


def reports_page(repo: CreditRepository, artifacts) -> None:
    page_header("报表中心", "经营趋势、风险分布、标签回流和审计记录")
    trend = build_operations_trend(repo)
    feedback = build_label_feedback_metrics(repo, artifacts)

    cols = st.columns(4)
    cols[0].metric("回流样本数", feedback.returned_count)
    cols[1].metric("回流坏样本数", feedback.bad_count)
    cols[2].metric("回流坏账率", fmt_pct(feedback.bad_rate))
    cols[3].metric("当前 AUC", f"{feedback.model_auc:.4f}")

    left, right = st.columns(2)
    with left:
        fig = px.line(trend, x="date", y=["申请量", "平均风险分"], markers=True)
        st.plotly_chart(plotly_layout(fig), width="stretch")
    with right:
        risk_df = build_risk_distribution(repo, artifacts)
        fig = px.box(
            risk_df,
            x="风险分层",
            y="calibrated_pd",
            color="风险分层",
            color_discrete_map={"低风险": "#10a36f", "中风险": "#d97706", "高风险": "#dc2626"},
        )
        st.plotly_chart(plotly_layout(fig), width="stretch")

    apps = repo.list_applications()
    candidates = [app for app in apps if app.get("actual_default_label") is None]
    if candidates:
        st.markdown("<div class='section-title'>标签回流模拟</div>", unsafe_allow_html=True)
        selected = st.selectbox("申请编号", [app["application_id"] for app in candidates])
        c1, c2 = st.columns(2)
        if c1.button("回流为未违约", width="stretch"):
            repo.add_label_feedback(selected, 0)
            st.rerun()
        if c2.button("回流为违约", type="primary", width="stretch"):
            repo.add_label_feedback(selected, 1)
            st.rerun()

    st.markdown("<div class='section-title'>审计日志</div>", unsafe_allow_html=True)
    logs = pd.DataFrame(repo.list_audit_logs())
    if not logs.empty:
        st.dataframe(logs[["created_at", "operator_id", "module", "action", "target_id"]], width="stretch", hide_index=True)


def tutorial_page() -> None:
    page_header("平台教程", "用 5 分钟看懂整个平台，并按案例完成一次风控演示")

    st.markdown("<div class='section-title'>一、先理解平台在做什么</div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="tutorial-step"><b>1. 申请接入</b><br><span>在“申请审批”选择一个样例客户，平台会读取客户资料和历史行为。</span></div>
        <div class="tutorial-step"><b>2. 模型评分</b><br><span>点击“提交评分”后，模型给出风险分、校准 PD 和主要风险原因。</span></div>
        <div class="tutorial-step"><b>3. 策略决策</b><br><span>平台按当前阈值自动分流为自动通过、人工复核或自动拒绝。</span></div>
        <div class="tutorial-step"><b>4. 人工复核</b><br><span>中风险申请进入“人工复核”，业务人员可以做通过或拒绝处理。</span></div>
        <div class="tutorial-step"><b>5. 报表监控</b><br><span>处理完成后，在“风控总览”和“报表中心”查看通过率、复核率、拒绝率和回流表现。</span></div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-title'>二、推荐演示路径</div>", unsafe_allow_html=True)
    st.dataframe(
        pd.DataFrame(
            [
                {"顺序": "1", "进入页面": "风控总览", "要看什么": "今日申请量、通过率、复核率、拒绝率"},
                {"顺序": "2", "进入页面": "申请审批", "要看什么": "选择样例客户并提交评分"},
                {"顺序": "3", "进入页面": "人工复核", "要看什么": "处理中风险申请，提交人工结论"},
                {"顺序": "4", "进入页面": "策略中心", "要看什么": "调整阈值，观察通过/复核/拒绝比例变化"},
                {"顺序": "5", "进入页面": "模型中心", "要看什么": "查看 AUC、KS、Lift 和主要风险因子"},
                {"顺序": "6", "进入页面": "报表中心", "要看什么": "模拟标签回流，查看审计日志"},
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    st.markdown("<div class='section-title'>三、案例说明</div>", unsafe_allow_html=True)
    case_cols = st.columns(3)
    cases = [
        (
            "低风险客户案例",
            "在“申请审批”选择低风险样例并提交评分。若风险分和 PD 低于策略阈值，结果会显示为自动通过，适合演示快速放行流程。",
        ),
        (
            "中风险客户案例",
            "选择中风险样例并提交评分。申请会进入人工复核区间，然后切到“人工复核”页面，选择该申请并提交复核通过或拒绝。",
        ),
        (
            "高风险客户案例",
            "选择高风险样例并提交评分。若 PD 高于拒绝阈值，平台会自动拒绝，并展示主要风险原因，适合说明策略拦截能力。",
        ),
    ]
    for col, (title, body) in zip(case_cols, cases):
        col.markdown(f"<div class='tutorial-card'><strong>{title}</strong><p>{body}</p></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>四、每个页面的用途</div>", unsafe_allow_html=True)
    st.dataframe(
        pd.DataFrame(
            [
                {"页面": "风控总览", "用途": "看经营和风险总体情况", "适合回答": "今天申请多不多，复核压力大不大"},
                {"页面": "申请审批", "用途": "完成样例客户评分", "适合回答": "单个客户为什么通过、复核或拒绝"},
                {"页面": "人工复核", "用途": "处理待复核申请", "适合回答": "业务人员如何介入中风险申请"},
                {"页面": "策略中心", "用途": "试算阈值和成本", "适合回答": "阈值调高或调低会带来什么影响"},
                {"页面": "模型中心", "用途": "查看模型效果和解释", "适合回答": "模型准不准，哪些因素影响风险"},
                {"页面": "报表中心", "用途": "看趋势、回流和审计", "适合回答": "处理结果能否沉淀为后续监控"},
            ]
        ),
        width="stretch",
        hide_index=True,
    )


def main() -> None:
    inject_styles()
    artifacts, repo, service = load_runtime()

    pages = [
        st.Page(lambda: overview_page(repo, artifacts), title="风控总览", url_path="overview", default=True),
        st.Page(lambda: application_page(repo, service), title="申请审批", url_path="application"),
        st.Page(lambda: review_page(repo), title="人工复核", url_path="review"),
        st.Page(lambda: strategy_page(repo, artifacts), title="策略中心", url_path="strategy"),
        st.Page(lambda: model_page(artifacts), title="模型中心", url_path="model"),
        st.Page(lambda: reports_page(repo, artifacts), title="报表中心", url_path="reports"),
        st.Page(tutorial_page, title="平台教程", url_path="tutorial"),
    ]
    page = st.navigation(pages, position="top")
    render_app_header()
    page.run()


if __name__ == "__main__":
    main()
