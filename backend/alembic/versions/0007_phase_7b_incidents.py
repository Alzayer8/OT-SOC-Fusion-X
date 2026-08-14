"""Create deterministic Phase 7B incident workflow persistence.

Revision ID: 0007_phase_7b_incidents
Revises: 0006_phase_6b_correlation
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_phase_7b_incidents"
down_revision: str | None = "0006_phase_6b_correlation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("incident_schema", sa.String(length=80), nullable=False),
        sa.Column("incident_schema_version", sa.String(length=16), nullable=False),
        sa.Column("incident_profile_id", sa.String(length=80), nullable=False),
        sa.Column("incident_profile_version", sa.String(length=16), nullable=False),
        sa.Column("incident_profile_sha256", sa.String(length=64), nullable=False),
        sa.Column("qualification_rule_id", sa.String(length=80), nullable=False),
        sa.Column("qualification_rule_version", sa.String(length=16), nullable=False),
        sa.Column("grouping_key_sha256", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("primary_evidence_id", sa.Uuid(), nullable=False),
        sa.Column("primary_evidence_type", sa.String(length=48), nullable=False),
        sa.Column("primary_evidence_schema", sa.String(length=80), nullable=False),
        sa.Column("primary_evidence_schema_version", sa.String(length=16), nullable=False),
        sa.Column("primary_evidence_integrity_sha256", sa.String(length=64), nullable=False),
        sa.Column("identity_asset_scope", postgresql.ARRAY(sa.String(length=160)), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=True),
        sa.Column("destination_asset_id", sa.Uuid(), nullable=True),
        sa.Column("controller_asset_id", sa.Uuid(), nullable=True),
        sa.Column("process_asset_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("process_asset_keys", postgresql.ARRAY(sa.String(length=80)), nullable=False),
        sa.Column("target_point_ids", postgresql.ARRAY(sa.String(length=80)), nullable=False),
        sa.Column("correlation_rule_id", sa.String(length=80), nullable=True),
        sa.Column("correlation_rule_version", sa.String(length=16), nullable=True),
        sa.Column("run_scope", sa.String(length=160), nullable=False),
        sa.Column("configuration_scope", sa.String(length=160), nullable=False),
        sa.Column("bound_simulation_id", sa.String(length=80), nullable=True),
        sa.Column("bound_configuration_hash", sa.String(length=64), nullable=True),
        sa.Column("s3_semantic_evidence_id", sa.Uuid(), nullable=True),
        sa.Column("grouping_epoch_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_context", sa.String(length=32), nullable=False),
        sa.Column("correlation_context", sa.String(length=32), nullable=False),
        sa.Column("evidence_completeness", sa.String(length=48), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("ground_truth_used", sa.Boolean(), nullable=False),
        sa.Column("malicious_intent_inferred", sa.Boolean(), nullable=False),
        sa.Column("causality_inferred", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('ASSET_IDENTITY_ANOMALY', 'COMMUNICATION_POLICY_VIOLATION', "
            "'CONTROL_COMMAND_INVESTIGATION', 'PROCESS_INCONSISTENCY')",
            name="ck_incidents_category",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'INVESTIGATING', 'RESOLVED')",
            name="ck_incidents_status",
        ),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_incidents_severity",
        ),
        sa.CheckConstraint("version >= 1", name="ck_incidents_version"),
        sa.CheckConstraint("evidence_count >= 1", name="ck_incidents_evidence_count"),
        sa.CheckConstraint("ground_truth_used = false", name="ck_incidents_no_ground_truth"),
        sa.CheckConstraint(
            "malicious_intent_inferred = false",
            name="ck_incidents_no_malicious_intent",
        ),
        sa.CheckConstraint("causality_inferred = false", name="ck_incidents_no_causality"),
        sa.ForeignKeyConstraint(
            ["primary_evidence_id"],
            ["evidence_records.evidence_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("incident_id"),
        sa.UniqueConstraint("grouping_key_sha256", name="uq_incidents_grouping_key"),
    )
    op.create_index(
        "ix_incidents_list_order",
        "incidents",
        [sa.text("last_observed_at DESC"), "incident_id"],
    )
    op.create_index(
        "ix_incidents_status_order",
        "incidents",
        ["status", sa.text("last_observed_at DESC"), "incident_id"],
    )
    op.create_index(
        "ix_incidents_category_order",
        "incidents",
        ["category", sa.text("last_observed_at DESC"), "incident_id"],
    )
    op.create_index(
        "ix_incidents_severity_order",
        "incidents",
        ["severity", sa.text("last_observed_at DESC"), "incident_id"],
    )
    op.create_index(
        "ix_incidents_process_asset_ids",
        "incidents",
        ["process_asset_ids"],
        postgresql_using="gin",
    )

    op.create_table(
        "incident_evidence_memberships",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_type", sa.String(length=48), nullable=False),
        sa.Column("evidence_schema", sa.String(length=80), nullable=False),
        sa.Column("evidence_schema_version", sa.String(length=16), nullable=False),
        sa.Column("integrity_sha256", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('PRIMARY', 'SUPPORTING', 'CONTRADICTING', 'CONTEXT')",
            name="ck_incident_membership_role",
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["evidence_id"], ["evidence_records.evidence_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("membership_id"),
        sa.UniqueConstraint(
            "incident_id", "evidence_id", name="uq_incident_evidence_membership"
        ),
    )
    op.create_index(
        "uq_incident_one_primary",
        "incident_evidence_memberships",
        ["incident_id"],
        unique=True,
        postgresql_where=sa.text("role = 'PRIMARY'"),
    )

    op.create_table(
        "incident_timeline_entries",
        sa.Column("timeline_entry_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("timeline_schema", sa.String(length=80), nullable=False),
        sa.Column("timeline_schema_version", sa.String(length=16), nullable=False),
        sa.Column("producer", sa.String(length=80), nullable=False),
        sa.Column("producer_version", sa.String(length=16), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("reference_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_type", sa.String(length=48), nullable=True),
        sa.Column("evidence_schema", sa.String(length=80), nullable=True),
        sa.Column("evidence_schema_version", sa.String(length=16), nullable=True),
        sa.Column("evidence_integrity_sha256", sa.String(length=64), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("asset_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("process_asset_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("actor_context", sa.String(length=80), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "entry_type IN ('INCIDENT_CREATED', 'EVIDENCE_ADDED', 'STATUS_CHANGED', "
            "'SEVERITY_CHANGED', 'ANALYST_NOTE_ADDED')",
            name="ck_incident_timeline_type",
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("timeline_entry_id"),
        sa.UniqueConstraint(
            "incident_id", "entry_type", "reference_id", name="uq_incident_timeline_reference"
        ),
    )
    op.create_index(
        "ix_incident_timeline_semantic_order",
        "incident_timeline_entries",
        ["incident_id", "observed_at", "timeline_entry_id"],
    )

    op.create_table(
        "incident_status_history",
        sa.Column("status_history_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("previous_status", sa.String(length=24), nullable=True),
        sa.Column("new_status", sa.String(length=24), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_context", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("version_before", sa.Integer(), nullable=False),
        sa.Column("version_after", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "new_status IN ('OPEN', 'INVESTIGATING', 'RESOLVED')",
            name="ck_incident_status_history_new",
        ),
        sa.CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('OPEN', 'INVESTIGATING', 'RESOLVED')",
            name="ck_incident_status_history_previous",
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("status_history_id"),
    )

    op.create_table(
        "incident_severity_history",
        sa.Column("severity_history_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("previous_severity", sa.String(length=16), nullable=True),
        sa.Column("new_severity", sa.String(length=16), nullable=False),
        sa.Column("triggering_evidence_id", sa.Uuid(), nullable=False),
        sa.Column("triggering_integrity_sha256", sa.String(length=64), nullable=False),
        sa.Column("profile_version", sa.String(length=16), nullable=False),
        sa.Column("rule_version", sa.String(length=16), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "new_severity IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_incident_severity_history_new",
        ),
        sa.CheckConstraint(
            "previous_severity IS NULL OR previous_severity IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_incident_severity_history_previous",
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["triggering_evidence_id"],
            ["evidence_records.evidence_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("severity_history_id"),
    )

    op.create_table(
        "incident_notes",
        sa.Column("note_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("actor_context", sa.String(length=80), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "char_length(content) BETWEEN 1 AND 2000",
            name="ck_incident_note_length",
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("note_id"),
    )

    op.create_table(
        "incident_audit_events",
        sa.Column("audit_event_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_context", sa.String(length=80), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("safe_reason", sa.String(length=300), nullable=True),
        sa.Column("version_before", sa.Integer(), nullable=False),
        sa.Column("version_after", sa.Integer(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("audit_event_id"),
    )

    op.execute(
        """
        CREATE FUNCTION reject_incident_append_only_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'incident history rows are append-only' USING ERRCODE = '55000';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in (
        "incident_evidence_memberships",
        "incident_timeline_entries",
        "incident_status_history",
        "incident_severity_history",
        "incident_notes",
        "incident_audit_events",
    ):
        op.execute(
            f"""
            CREATE TRIGGER {table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_incident_append_only_mutation()
            """
        )
    op.execute(
        """
        CREATE FUNCTION reject_incident_delete()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'incidents cannot be deleted' USING ERRCODE = '55000';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER incidents_no_delete
        BEFORE DELETE ON incidents
        FOR EACH ROW EXECUTE FUNCTION reject_incident_delete()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER incidents_no_delete ON incidents")
    op.execute("DROP FUNCTION reject_incident_delete()")
    for table in (
        "incident_evidence_memberships",
        "incident_timeline_entries",
        "incident_status_history",
        "incident_severity_history",
        "incident_notes",
        "incident_audit_events",
    ):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.execute("DROP FUNCTION reject_incident_append_only_mutation()")
    op.drop_table("incident_audit_events")
    op.drop_table("incident_notes")
    op.drop_table("incident_severity_history")
    op.drop_table("incident_status_history")
    op.drop_table("incident_timeline_entries")
    op.drop_table("incident_evidence_memberships")
    op.drop_table("incidents")
