"""Align active simulator source metadata with the Oil & Gas v2 contract.

Revision ID: 0003_phase_3_6_oil_gas
Revises: 0002_phase_3_evidence
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_phase_3_6_oil_gas"
down_revision: str | None = "0002_phase_3_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE evidence_sources
        SET display_name = 'Primary Synthetic Oil and Gas Transfer Simulator',
            schema_version = '2.0.0',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = '143c438b-ca4d-5094-ae31-7794ca91d8f9'
          AND source_key = 'simulator-primary'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE evidence_sources
        SET display_name = 'Primary Synthetic Cooling Simulator',
            schema_version = '1.0.0',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = '143c438b-ca4d-5094-ae31-7794ca91d8f9'
          AND source_key = 'simulator-primary'
        """
    )
