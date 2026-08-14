"""Allow offline asset-context and communication-policy derivative evidence.

Revision ID: 0005_phase_5b_asset_policy
Revises: 0004_phase_4b_protocol_semantics
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_phase_5b_asset_policy"
down_revision: str | None = "0004_phase_4b_protocol_semantics"
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
        "'communication_policy_finding')",
    )
    op.execute(
        """
        INSERT INTO evidence_sources
            (id, source_key, source_type, display_name, schema_version, enabled)
        VALUES
            ('2f41bc75-eebd-535e-8473-2eef00a7b457',
             'asset-context-resolver',
             'asset_context_event',
             'Offline Synthetic Asset Context Resolver',
             '1.0.0',
             true),
            ('a054a5bc-960a-5ae0-ad10-61a3897425bf',
             'communication-policy-evaluator',
             'communication_policy_finding',
             'Offline Synthetic Communication Policy Evaluator',
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
                    '2f41bc75-eebd-535e-8473-2eef00a7b457',
                    'a054a5bc-960a-5ae0-ad10-61a3897425bf'
                )
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade Phase 5B while asset/policy evidence remains; '
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
            '2f41bc75-eebd-535e-8473-2eef00a7b457',
            'a054a5bc-960a-5ae0-ad10-61a3897425bf'
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
        "source_type IN ('simulator_telemetry', 'synthetic_protocol_event', "
        "'protocol_semantic_event')",
    )
