from __future__ import annotations

from app.evidence.schemas import EvidenceIngestRequest, EvidenceProvenance
from app.simulation.models import TelemetrySample


def telemetry_to_evidence_request(
    sample: TelemetrySample,
    *,
    source_key: str = "simulator-primary",
    seed: int,
) -> EvidenceIngestRequest:
    """Convert public telemetry only; GroundTruthEvent is intentionally unsupported."""

    payload = sample.canonical_dict()
    return EvidenceIngestRequest(
        source_key=source_key,
        source_event_id=f"{sample.simulation_id}:{sample.sequence_number}",
        evidence_type="simulator_telemetry",
        observed_at=sample.timestamp,
        sequence_number=sample.sequence_number,
        payload_schema="otsoc.simulator.telemetry",
        payload_schema_version="2.0.0",
        payload=payload,
        provenance=EvidenceProvenance(
            producer="otsoc_simulator",
            producer_version=sample.simulator_version,
            domain=sample.domain,
            simulation_id=sample.simulation_id,
            configuration_hash=sample.configuration_hash,
            seed=seed,
        ),
    )
