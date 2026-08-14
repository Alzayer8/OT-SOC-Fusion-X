from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class EvidenceBase(DeclarativeBase):
    pass


class EvidenceSource(EvidenceBase):
    __tablename__ = "evidence_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('simulator_telemetry', 'synthetic_protocol_event', "
            "'protocol_semantic_event', 'asset_context_event', "
            "'communication_policy_finding', 'correlation_finding')",
            name="ck_evidence_sources_supported_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    records: Mapped[list[EvidenceRecord]] = relationship(back_populates="source")


class EvidenceRecord(EvidenceBase):
    __tablename__ = "evidence_records"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "source_event_id",
            "evidence_type",
            "payload_schema_version",
            name="uq_evidence_source_event_identity",
        ),
        CheckConstraint("evidence_version = 1", name="ck_evidence_records_version"),
        CheckConstraint(
            "sequence_number IS NULL OR sequence_number >= 0", name="ck_evidence_sequence"
        ),
        CheckConstraint("canonical_byte_length > 0", name="ck_evidence_canonical_length"),
        Index("ix_evidence_records_source_observed", "source_id", "observed_at", "evidence_id"),
        Index("ix_evidence_records_type_observed", "evidence_type", "observed_at", "evidence_id"),
    )

    evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    evidence_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evidence_sources.id", ondelete="RESTRICT"), nullable=False
    )
    source_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(48), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_schema: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    integrity_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_byte_length: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[EvidenceSource] = relationship(back_populates="records")
