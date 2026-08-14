"""Add v1.1 local identity, lab context, and SOC workflow persistence.

Revision ID: 0008_v1_1_soc_workflow
Revises: 0007_phase_7b_incidents
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_v1_1_soc_workflow"
down_revision: str | None = "0007_phase_7b_incidents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_auth_tables()
    _create_lab_tables()
    _extend_incidents()
    _create_report_tables()
    _create_soc_audit_table()
    _install_history_guards()


def downgrade() -> None:
    _remove_history_guards()
    op.drop_table("soc_audit_events")
    op.drop_table("incident_report_revisions")
    op.drop_table("incident_reports")
    op.drop_constraint(
        "fk_incident_notes_actor_user", "incident_notes", type_="foreignkey"
    )
    op.drop_column("incident_notes", "actor_user_id")
    op.drop_constraint(
        "fk_incident_status_actor_user", "incident_status_history", type_="foreignkey"
    )
    op.drop_column("incident_status_history", "actor_user_id")
    op.drop_constraint(
        "fk_incident_audit_actor_user", "incident_audit_events", type_="foreignkey"
    )
    op.drop_column("incident_audit_events", "actor_user_id")
    op.drop_index("ix_incidents_disposition", table_name="incidents")
    op.drop_index("ix_incidents_assignee", table_name="incidents")
    op.drop_constraint("fk_incidents_disposition_user", "incidents", type_="foreignkey")
    op.drop_constraint("fk_incidents_assignee_user", "incidents", type_="foreignkey")
    op.drop_constraint("ck_incidents_disposition_reason", "incidents", type_="check")
    op.drop_constraint("ck_incidents_disposition", "incidents", type_="check")
    for column in (
        "disposition_set_at",
        "disposition_set_by_user_id",
        "disposition_reason",
        "disposition",
        "assigned_at",
        "assignee_user_id",
    ):
        op.drop_column("incidents", column)
    op.drop_table("lab_active_context")
    op.drop_table("lab_run_incidents")
    op.drop_table("lab_run_evidence")
    op.drop_table("lab_runs")
    op.drop_table("auth_sessions")
    op.drop_table("local_users")


def _create_auth_tables() -> None:
    op.create_table(
        "local_users",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'SOC_ANALYST', 'OT_ENGINEER', 'READ_ONLY')",
            name="ck_local_users_role",
        ),
        sa.CheckConstraint("version >= 1", name="ck_local_users_version"),
        sa.CheckConstraint(
            "username = lower(username) AND username ~ "
            "'^[a-z0-9][a-z0-9._-]{2,63}$'",
            name="ck_local_users_username",
        ),
        sa.CheckConstraint(
            "char_length(display_name) BETWEEN 1 AND 120",
            name="ck_local_users_display_name",
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("username", name="uq_local_users_username"),
    )
    op.create_index(
        "ix_local_users_active_role", "local_users", ["active", "role", "username"]
    )
    op.create_table(
        "auth_sessions",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("csrf_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > created_at", name="ck_auth_sessions_expiry"),
        sa.CheckConstraint(
            "char_length(token_digest) = 64 AND char_length(csrf_digest) = 64",
            name="ck_auth_sessions_digest_length",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["local_users.user_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("token_digest", name="uq_auth_sessions_token_digest"),
    )
    op.create_index(
        "ix_auth_sessions_user_expiry", "auth_sessions", ["user_id", "expires_at"]
    )
    op.create_index(
        "ix_auth_sessions_active_lookup",
        "auth_sessions",
        ["token_digest", "revoked_at", "expires_at"],
    )


def _create_lab_tables() -> None:
    op.create_table(
        "lab_runs",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.String(length=12), nullable=False),
        sa.Column("definition_version", sa.String(length=16), nullable=False),
        sa.Column("dataset_id", sa.String(length=100), nullable=False),
        sa.Column("dataset_version", sa.String(length=16), nullable=False),
        sa.Column("dataset_sha256", sa.String(length=64), nullable=False),
        sa.Column("dataset_case_id", sa.String(length=40), nullable=False),
        sa.Column("evidence_simulation_id", sa.String(length=80), nullable=True),
        sa.Column("configuration_id", sa.String(length=100), nullable=True),
        sa.Column("configuration_hash", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("started_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("started_by_actor", sa.String(length=80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_observed_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_observed_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scenario_id IN ('BASELINE', 'S1', 'S2', 'S3', 'S4')",
            name="ck_lab_runs_scenario",
        ),
        sa.CheckConstraint(
            "state IN ('RUNNING', 'COMPLETED', 'FAILED')", name="ck_lab_runs_state"
        ),
        sa.CheckConstraint(
            "(state = 'RUNNING' AND completed_at IS NULL) OR "
            "(state IN ('COMPLETED', 'FAILED') AND completed_at IS NOT NULL)",
            name="ck_lab_runs_completion",
        ),
        sa.CheckConstraint(
            "(state = 'FAILED' AND failure_code IS NOT NULL) OR "
            "(state != 'FAILED' AND failure_code IS NULL)",
            name="ck_lab_runs_failure",
        ),
        sa.CheckConstraint(
            "evidence_observed_from IS NULL OR evidence_observed_to IS NULL OR "
            "evidence_observed_from <= evidence_observed_to",
            name="ck_lab_runs_evidence_window",
        ),
        sa.ForeignKeyConstraint(
            ["started_by_user_id"], ["local_users.user_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "uq_lab_runs_one_baseline",
        "lab_runs",
        ["scenario_id"],
        unique=True,
        postgresql_where=sa.text("scenario_id = 'BASELINE'"),
    )
    op.create_index(
        "uq_lab_runs_one_running",
        "lab_runs",
        ["state"],
        unique=True,
        postgresql_where=sa.text("state = 'RUNNING'"),
    )
    op.create_index(
        "ix_lab_runs_history", "lab_runs", [sa.text("started_at DESC"), "run_id"]
    )
    op.create_index(
        "ix_lab_runs_scenario_history",
        "lab_runs",
        ["scenario_id", sa.text("started_at DESC")],
    )
    op.create_table(
        "lab_run_evidence",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('ROOT', 'LINEAGE')", name="ck_lab_run_evidence_role"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["lab_runs.run_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["evidence_id"], ["evidence_records.evidence_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("run_id", "evidence_id"),
    )
    op.create_index(
        "ix_lab_run_evidence_evidence", "lab_run_evidence", ["evidence_id", "run_id"]
    )
    op.create_table(
        "lab_run_incidents",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["lab_runs.run_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("run_id", "incident_id"),
    )
    op.create_index(
        "ix_lab_run_incidents_incident", "lab_run_incidents", ["incident_id", "run_id"]
    )
    op.create_table(
        "lab_active_context",
        sa.Column("singleton_id", sa.Integer(), nullable=False),
        sa.Column("active_run_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("changed_by_actor", sa.String(length=80), nullable=False),
        sa.Column("activation_reason", sa.String(length=32), nullable=False),
        sa.CheckConstraint("singleton_id = 1", name="ck_lab_active_context_singleton"),
        sa.CheckConstraint("version >= 1", name="ck_lab_active_context_version"),
        sa.CheckConstraint(
            "activation_reason IN ('STARTUP_BASELINE', 'SCENARIO_COMPLETED', "
            "'RETURN_BASELINE', 'RESET')",
            name="ck_lab_active_context_reason",
        ),
        sa.ForeignKeyConstraint(
            ["active_run_id"], ["lab_runs.run_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"], ["local_users.user_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("singleton_id"),
    )


def _extend_incidents() -> None:
    op.add_column(
        "incident_status_history", sa.Column("actor_user_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_incident_status_actor_user",
        "incident_status_history",
        "local_users",
        ["actor_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )
    op.add_column("incident_notes", sa.Column("actor_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_incident_notes_actor_user",
        "incident_notes",
        "local_users",
        ["actor_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )
    op.add_column("incidents", sa.Column("assignee_user_id", sa.Uuid(), nullable=True))
    op.add_column("incidents", sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "incidents",
        sa.Column(
            "disposition",
            sa.String(length=24),
            nullable=False,
            server_default="UNREVIEWED",
        ),
    )
    op.add_column("incidents", sa.Column("disposition_reason", sa.Text(), nullable=True))
    op.add_column(
        "incidents", sa.Column("disposition_set_by_user_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "incidents", sa.Column("disposition_set_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "ck_incidents_disposition",
        "incidents",
        "disposition IN ('UNREVIEWED', 'TRUE_POSITIVE', 'FALSE_POSITIVE')",
    )
    op.create_check_constraint(
        "ck_incidents_disposition_reason",
        "incidents",
        "disposition_reason IS NULL OR char_length(disposition_reason) BETWEEN 1 AND 2000",
    )
    op.create_foreign_key(
        "fk_incidents_assignee_user",
        "incidents",
        "local_users",
        ["assignee_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_incidents_disposition_user",
        "incidents",
        "local_users",
        ["disposition_set_by_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_incidents_assignee", "incidents", ["assignee_user_id"])
    op.create_index("ix_incidents_disposition", "incidents", ["disposition"])
    op.add_column(
        "incident_audit_events", sa.Column("actor_user_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_incident_audit_actor_user",
        "incident_audit_events",
        "local_users",
        ["actor_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )


def _create_report_tables() -> None:
    field_columns = [
        sa.Column(name, sa.Text(), nullable=False)
        for name in (
            "investigation_summary",
            "analyst_assessment",
            "evidence_assessment",
            "process_impact_assessment",
            "disposition_rationale",
            "recommended_follow_up",
            "final_conclusion",
        )
    ]
    op.create_table(
        "incident_reports",
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        *field_columns,
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_incident_reports_version"),
        *_report_field_checks("incident_reports"),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["local_users.user_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["local_users.user_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("incident_id"),
    )
    revision_columns = [
        sa.Column(name, sa.Text(), nullable=False)
        for name in (
            "investigation_summary",
            "analyst_assessment",
            "evidence_assessment",
            "process_impact_assessment",
            "disposition_rationale",
            "recommended_follow_up",
            "final_conclusion",
        )
    ]
    op.create_table(
        "incident_report_revisions",
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        *revision_columns,
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("saved_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_incident_report_revision_version"),
        *_report_field_checks("incident_report_revisions"),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["saved_by_user_id"], ["local_users.user_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("revision_id"),
        sa.UniqueConstraint("incident_id", "version", name="uq_incident_report_revision"),
    )


def _report_field_checks(prefix: str) -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            f"char_length({name}) <= 4000", name=f"ck_{prefix}_{name}_length"
        )
        for name in (
            "investigation_summary",
            "analyst_assessment",
            "evidence_assessment",
            "process_impact_assessment",
            "disposition_rationale",
            "recommended_follow_up",
            "final_conclusion",
        )
    ]


def _create_soc_audit_table() -> None:
    op.create_table(
        "soc_audit_events",
        sa.Column("audit_event_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("subject_user_id", sa.Uuid(), nullable=True),
        sa.Column("subject_label", sa.String(length=80), nullable=True),
        sa.Column("incident_id", sa.Uuid(), nullable=True),
        sa.Column("scenario_run_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("safe_reason", sa.String(length=300), nullable=True),
        sa.Column(
            "details", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.CheckConstraint(
            "result IN ('ACCEPTED', 'DENIED', 'FAILED')",
            name="ck_soc_audit_events_result",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["local_users.user_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["subject_user_id"], ["local_users.user_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["scenario_run_id"], ["lab_runs.run_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("audit_event_id"),
    )
    op.create_index(
        "ix_soc_audit_events_time", "soc_audit_events", ["occurred_at", "audit_event_id"]
    )
    op.create_index(
        "ix_soc_audit_events_actor_time",
        "soc_audit_events",
        ["actor_user_id", "occurred_at"],
    )
    op.create_index(
        "ix_soc_audit_events_incident_time",
        "soc_audit_events",
        ["incident_id", "occurred_at"],
    )
    op.create_index(
        "ix_soc_audit_events_run_time",
        "soc_audit_events",
        ["scenario_run_id", "occurred_at"],
    )


def _install_history_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION reject_v11_append_only_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'v1.1 history rows are append-only' USING ERRCODE = '55000';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in (
        "soc_audit_events",
        "incident_report_revisions",
        "lab_run_evidence",
        "lab_run_incidents",
    ):
        op.execute(
            f"""
            CREATE TRIGGER {table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_v11_append_only_mutation()
            """
        )
    op.execute(
        """
        CREATE FUNCTION reject_v11_identity_history_delete()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'v1.1 identity and run records cannot be deleted' USING ERRCODE = '55000';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in ("local_users", "auth_sessions", "lab_runs"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_no_delete
            BEFORE DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_v11_identity_history_delete()
            """
        )


def _remove_history_guards() -> None:
    for table in ("local_users", "auth_sessions", "lab_runs"):
        op.execute(f"DROP TRIGGER {table}_no_delete ON {table}")
    op.execute("DROP FUNCTION reject_v11_identity_history_delete()")
    for table in (
        "soc_audit_events",
        "incident_report_revisions",
        "lab_run_evidence",
        "lab_run_incidents",
    ):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.execute("DROP FUNCTION reject_v11_append_only_mutation()")
