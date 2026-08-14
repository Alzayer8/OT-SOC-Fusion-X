from __future__ import annotations

from app.evidence.adapter import telemetry_to_evidence_request
from app.evidence.schemas import EvidenceIngestRequest
from app.simulation import OilGasTransferSimulator, SimulationConfig


def sample_evidence_request(*, source_event_id: str | None = None) -> EvidenceIngestRequest:
    config = SimulationConfig(duration_seconds=2)
    sample = OilGasTransferSimulator(config).step().telemetry
    request = telemetry_to_evidence_request(sample, seed=config.seed)
    if source_event_id is None:
        return request
    return request.model_copy(update={"source_event_id": source_event_id})
