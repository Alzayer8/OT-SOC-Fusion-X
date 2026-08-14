"""Allow offline raw protocol and derived semantic evidence sources.

Revision ID: 0004_phase_4b_protocol_semantics
Revises: 0003_phase_3_6_oil_gas
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_phase_4b_protocol_semantics"
down_revision: str | None = "0003_phase_3_6_oil_gas"
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
        "'protocol_semantic_event')",
    )
    op.execute(
        """
        INSERT INTO evidence_sources
            (id, source_key, source_type, display_name, schema_version, enabled)
        VALUES
            ('4eecb667-d128-5c1f-bd61-28444df4ed8c',
             'synthetic-modbus-fixture-primary',
             'synthetic_protocol_event',
             'Offline Synthetic Modbus Fixture Source',
             '1.0.0',
             true),
            ('8db5c3ac-ca9e-59e6-8176-95cffeed43d6',
             'protocol-semantics-decoder',
             'protocol_semantic_event',
             'Offline Protocol Semantics Decoder',
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
                WHERE source_id IN (
                    '4eecb667-d128-5c1f-bd61-28444df4ed8c',
                    '8db5c3ac-ca9e-59e6-8176-95cffeed43d6'
                )
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade Phase 4B while protocol evidence remains; '
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
        WHERE id IN (
            '4eecb667-d128-5c1f-bd61-28444df4ed8c',
            '8db5c3ac-ca9e-59e6-8176-95cffeed43d6'
        )
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
        "source_type = 'simulator_telemetry'",
    )
