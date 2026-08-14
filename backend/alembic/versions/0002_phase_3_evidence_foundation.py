"""Phase 3 evidence source and immutable record foundation.

Revision ID: 0002_phase_3_evidence
Revises: 0001_phase_1_baseline
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase_3_evidence"
down_revision: str | None = "0001_phase_1_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type = 'simulator_telemetry'",
            name="ck_evidence_sources_supported_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key"),
    )
    op.create_table(
        "evidence_records",
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_version", sa.SmallInteger(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_event_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_type", sa.String(length=48), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        sa.Column("payload_schema", sa.String(length=80), nullable=False),
        sa.Column("payload_schema_version", sa.String(length=16), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("integrity_sha256", sa.String(length=64), nullable=False),
        sa.Column("canonical_byte_length", sa.Integer(), nullable=False),
        sa.CheckConstraint("evidence_version = 1", name="ck_evidence_records_version"),
        sa.CheckConstraint(
            "sequence_number IS NULL OR sequence_number >= 0",
            name="ck_evidence_sequence",
        ),
        sa.CheckConstraint(
            "canonical_byte_length > 0",
            name="ck_evidence_canonical_length",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["evidence_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("evidence_id"),
        sa.UniqueConstraint(
            "source_id",
            "source_event_id",
            "evidence_type",
            "payload_schema_version",
            name="uq_evidence_source_event_identity",
        ),
    )
    op.create_index(
        "ix_evidence_records_source_observed",
        "evidence_records",
        ["source_id", "observed_at", "evidence_id"],
    )
    op.create_index(
        "ix_evidence_records_type_observed",
        "evidence_records",
        ["evidence_type", "observed_at", "evidence_id"],
    )
    op.execute(
        """
        CREATE FUNCTION reject_evidence_record_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'evidence records are append-only' USING ERRCODE = '55000';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER evidence_records_append_only
        BEFORE UPDATE OR DELETE ON evidence_records
        FOR EACH ROW EXECUTE FUNCTION reject_evidence_record_mutation()
        """
    )
    op.execute(
        """
        INSERT INTO evidence_sources
            (id, source_key, source_type, display_name, schema_version, enabled)
        VALUES
            ('143c438b-ca4d-5094-ae31-7794ca91d8f9', 'simulator-primary',
             'simulator_telemetry', 'Primary Synthetic Cooling Simulator', '1.0.0', true)
        """
    )


def downgrade() -> None:
    op.drop_table("evidence_records")
    op.execute("DROP FUNCTION reject_evidence_record_mutation()")
    op.drop_table("evidence_sources")
