"""Allow offline cyber-physical correlation derivative evidence.

Revision ID: 0006_phase_6b_correlation
Revises: 0005_phase_5b_asset_policy
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_phase_6b_correlation"
down_revision: str | None = "0005_phase_5b_asset_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_evidence_sources_supported_type",
        "evidence_sources",
        type_="check",
    )
    op.create_check_constraint(
        "ck_evidence_sources_supported_type",
        "evidence_sources",
        "source_type IN ('simulator_telemetry', 'synthetic_protocol_event', "
        "'protocol_semantic_event', 'asset_context_event', "
        "'communication_policy_finding', 'correlation_finding')",
    )
    op.execute(
        """
        INSERT INTO evidence_sources
            (id, source_key, source_type, display_name, schema_version, enabled)
        VALUES
            ('21f51f40-c7bb-57a6-993a-416b244185b8',
             'cyber-physical-correlation-evaluator',
             'correlation_finding',
             'Offline Synthetic Cyber-Physical Correlation Evaluator',
             '1.0.0',
             true)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM evidence_records
                WHERE source_id = '21f51f40-c7bb-57a6-993a-416b244185b8'
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade Phase 6B while correlation evidence remains; '
                    'records are append-only'
                    USING ERRCODE = '55000';
            END IF;
        END
        $$
        """
    )
    op.execute(
        """
        DELETE FROM evidence_sources
        WHERE id = '21f51f40-c7bb-57a6-993a-416b244185b8'
        """
    )
    op.drop_constraint(
        "ck_evidence_sources_supported_type",
        "evidence_sources",
        type_="check",
    )
    op.create_check_constraint(
        "ck_evidence_sources_supported_type",
        "evidence_sources",
        "source_type IN ('simulator_telemetry', 'synthetic_protocol_event', "
        "'protocol_semantic_event', 'asset_context_event', "
        "'communication_policy_finding')",
    )
