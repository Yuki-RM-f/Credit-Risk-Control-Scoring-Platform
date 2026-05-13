from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .domain import ApplicantProfile, ScoringResult


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


class CreditRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists application (
                    application_id text primary key,
                    customer_id text not null,
                    customer_name text not null,
                    status text not null,
                    created_at text not null,
                    updated_at text not null,
                    loan_disbursed_at text,
                    observation_due_at text,
                    operator_id text not null default 'demo_operator',
                    role text not null default 'risk_operator'
                );

                create table if not exists application_feature_snapshot (
                    application_id text primary key,
                    feature_payload text not null,
                    created_at text not null
                );

                create table if not exists scoring_result (
                    application_id text primary key,
                    model_version text not null,
                    raw_pd real not null,
                    calibrated_pd real not null,
                    score real not null,
                    risk_level text not null,
                    decision_band text not null,
                    reason_codes text not null,
                    positive_factors text not null,
                    negative_factors text not null,
                    shap_payload text not null,
                    strategy_version text not null,
                    scored_at text not null
                );

                create table if not exists review_task (
                    application_id text primary key,
                    review_status text not null,
                    review_decision text,
                    review_comment text,
                    created_at text not null,
                    completed_at text
                );

                create table if not exists strategy_version (
                    strategy_version text primary key,
                    t1 real not null,
                    t2 real not null,
                    fn_cost real not null,
                    fp_cost real not null,
                    review_cost real not null,
                    status text not null,
                    published_by text not null,
                    published_at text not null
                );

                create table if not exists label_feedback (
                    application_id text primary key,
                    actual_default_label integer not null,
                    label_returned_at text not null
                );

                create table if not exists audit_log (
                    log_id integer primary key autoincrement,
                    operator_id text not null,
                    module text not null,
                    action text not null,
                    target_id text not null,
                    before_payload text,
                    after_payload text,
                    created_at text not null
                );

                create table if not exists alert_event (
                    alert_id integer primary key autoincrement,
                    alert_type text not null,
                    alert_level text not null,
                    alert_message text not null,
                    status text not null,
                    created_at text not null
                );
                """
            )
            count = conn.execute("select count(*) from strategy_version where status = 'active'").fetchone()[0]
            if count == 0:
                conn.execute(
                    """
                    insert into strategy_version
                    (strategy_version, t1, t2, fn_cost, fp_cost, review_cost, status, published_by, published_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("S20260511_01", 0.14, 0.42, 5.0, 1.0, 0.4, "active", "system", _now()),
                )
            conn.commit()

    def create_application(self, profile: ApplicantProfile, result: ScoringResult) -> str:
        application_id = self._next_application_id()
        created_at = _now()
        loan_disbursed_at = created_at if result.status == "approved" else None
        observation_due_at = (
            (datetime.now() + timedelta(days=90)).isoformat(timespec="seconds")
            if result.status == "approved"
            else None
        )
        with self.connect() as conn:
            conn.execute(
                """
                insert into application
                (application_id, customer_id, customer_name, status, created_at, updated_at,
                 loan_disbursed_at, observation_due_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    profile.customer_id,
                    profile.customer_name,
                    result.status,
                    created_at,
                    created_at,
                    loan_disbursed_at,
                    observation_due_at,
                ),
            )
            conn.execute(
                """
                insert into application_feature_snapshot (application_id, feature_payload, created_at)
                values (?, ?, ?)
                """,
                (application_id, _json(asdict(profile)), created_at),
            )
            conn.execute(
                """
                insert into scoring_result
                (application_id, model_version, raw_pd, calibrated_pd, score, risk_level, decision_band,
                 reason_codes, positive_factors, negative_factors, shap_payload, strategy_version, scored_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    result.model_version,
                    result.raw_pd,
                    result.calibrated_pd,
                    result.score,
                    result.risk_level,
                    result.decision_band,
                    _json(result.reason_codes),
                    _json(result.positive_factors),
                    _json(result.negative_factors),
                    _json(result.waterfall),
                    result.strategy_version,
                    created_at,
                ),
            )
            if result.status == "pending_review":
                conn.execute(
                    """
                    insert into review_task (application_id, review_status, created_at)
                    values (?, ?, ?)
                    """,
                    (application_id, "pending", created_at),
                )
            self._insert_audit(conn, "application", "application_scored", application_id, None, {"status": result.status})
            conn.commit()
        return application_id

    def get_application(self, application_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("select * from application where application_id = ?", (application_id,)).fetchone()
        result = _row_to_dict(row)
        if result is None:
            raise KeyError(application_id)
        return result

    def get_review_task(self, application_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("select * from review_task where application_id = ?", (application_id,)).fetchone()
        result = _row_to_dict(row)
        if result is None:
            raise KeyError(application_id)
        return result

    def list_applications(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select a.*, s.raw_pd, s.calibrated_pd, s.score, s.risk_level, s.decision_band,
                       s.reason_codes, s.strategy_version, lf.actual_default_label
                from application a
                join scoring_result s on s.application_id = a.application_id
                left join label_feedback lf on lf.application_id = a.application_id
                order by a.created_at desc
                """
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def list_pending_reviews(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select a.application_id, a.customer_id, a.customer_name, a.created_at,
                       s.score, s.calibrated_pd, s.reason_codes, s.negative_factors,
                       rt.review_status
                from review_task rt
                join application a on a.application_id = rt.application_id
                join scoring_result s on s.application_id = rt.application_id
                where rt.review_status = 'pending'
                order by a.created_at asc
                """
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def list_scoring_results(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select a.application_id, a.status, a.created_at, a.customer_name,
                       s.raw_pd, s.calibrated_pd, s.score, s.risk_level, s.decision_band,
                       s.reason_codes, s.positive_factors, s.negative_factors, s.shap_payload,
                       lf.actual_default_label
                from scoring_result s
                join application a on a.application_id = s.application_id
                left join label_feedback lf on lf.application_id = a.application_id
                order by a.created_at desc
                """
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def submit_review(self, application_id: str, review_decision: str, review_comment: str) -> None:
        if review_decision not in {"approved", "rejected"}:
            raise ValueError("review_decision must be approved or rejected")
        completed_at = _now()
        with self.connect() as conn:
            before = conn.execute("select * from review_task where application_id = ?", (application_id,)).fetchone()
            if before is None:
                raise KeyError(application_id)
            if before["review_status"] == "completed":
                return
            new_status = "review_approved" if review_decision == "approved" else "review_rejected"
            conn.execute(
                """
                update review_task
                set review_status = 'completed', review_decision = ?, review_comment = ?, completed_at = ?
                where application_id = ?
                """,
                (review_decision, review_comment, completed_at, application_id),
            )
            conn.execute(
                "update application set status = ?, updated_at = ? where application_id = ?",
                (new_status, completed_at, application_id),
            )
            self._insert_audit(
                conn,
                "manual_review",
                "review_decision_submitted",
                application_id,
                _row_to_dict(before),
                {"review_decision": review_decision, "status": new_status},
            )
            conn.commit()

    def publish_strategy(
        self,
        *,
        t1: float,
        t2: float,
        fn_cost: float,
        fp_cost: float,
        review_cost: float,
        published_by: str = "strategy_operator",
    ) -> str:
        version = f"S{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with self.connect() as conn:
            before = self.get_active_strategy()
            conn.execute("update strategy_version set status = 'inactive' where status = 'active'")
            conn.execute(
                """
                insert into strategy_version
                (strategy_version, t1, t2, fn_cost, fp_cost, review_cost, status, published_by, published_at)
                values (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (version, t1, t2, fn_cost, fp_cost, review_cost, published_by, _now()),
            )
            self._insert_audit(conn, "strategy", "strategy_published", version, before, {"t1": t1, "t2": t2})
            conn.commit()
        return version

    def get_active_strategy(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("select * from strategy_version where status = 'active' order by published_at desc limit 1").fetchone()
        result = _row_to_dict(row)
        if result is None:
            raise RuntimeError("No active strategy exists.")
        return result

    def list_strategy_versions(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("select * from strategy_version order by published_at desc").fetchall()
        return [_row_to_dict(row) for row in rows]

    def add_label_feedback(self, application_id: str, actual_default_label: int) -> None:
        if actual_default_label not in {0, 1}:
            raise ValueError("actual_default_label must be 0 or 1")
        with self.connect() as conn:
            conn.execute(
                """
                insert into label_feedback (application_id, actual_default_label, label_returned_at)
                values (?, ?, ?)
                on conflict(application_id) do update set
                    actual_default_label = excluded.actual_default_label,
                    label_returned_at = excluded.label_returned_at
                """,
                (application_id, actual_default_label, _now()),
            )
            self._insert_audit(
                conn,
                "label_feedback",
                "label_feedback_returned",
                application_id,
                None,
                {"actual_default_label": actual_default_label},
            )
            conn.commit()

    def list_label_feedback(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("select * from label_feedback order by label_returned_at desc").fetchall()
        return [_row_to_dict(row) for row in rows]

    def list_audit_logs(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("select * from audit_log order by created_at desc, log_id desc").fetchall()
        return [_row_to_dict(row) for row in rows]

    def is_empty(self) -> bool:
        with self.connect() as conn:
            count = conn.execute("select count(*) from application").fetchone()[0]
        return count == 0

    def _next_application_id(self) -> str:
        with self.connect() as conn:
            count = conn.execute("select count(*) from application").fetchone()[0]
        return f"A{datetime.now().strftime('%Y%m%d')}{count + 1:04d}"

    @staticmethod
    def _insert_audit(
        conn: sqlite3.Connection,
        module: str,
        action: str,
        target_id: str,
        before_payload: Any,
        after_payload: Any,
        operator_id: str = "demo_operator",
    ) -> None:
        conn.execute(
            """
            insert into audit_log
            (operator_id, module, action, target_id, before_payload, after_payload, created_at)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (operator_id, module, action, target_id, _json(before_payload), _json(after_payload), _now()),
        )
