from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

from sqlalchemy import func, select

from app.core.config import Settings
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.incidents.lifecycle import IncidentLifecycleError, transition_incident_status
from app.incidents.models import (
    Incident,
    IncidentEvidenceMembership,
    IncidentQualificationRequest,
    IncidentSeverityHistory,
    IncidentStatus,
)
from app.incidents.notes import add_analyst_note
from app.incidents.repository import get_incident_detail
from app.incidents.service import qualify_stored_evidence
from app.tools.incident_support import persist_correlation_chain, persist_policy_chain


@dataclass(frozen=True, slots=True)
class IncidentRuntimeCheckResult:
    s1_low: bool
    s2_medium: bool
    s3_approved_not_correlated_evidence_only: bool
    s3_denied_not_correlated_medium: bool
    s3_approved_correlated_medium: bool
    s3_denied_correlated_high: bool
    s4_correlated_high: bool
    retry_same_incident: bool
    concurrent_duplicate_safe: bool
    late_s3_enriched: bool
    primary_evidence_unchanged: bool
    severity_only_raised: bool
    run_isolated: bool
    configuration_isolated: bool
    lifecycle_valid: bool
    invalid_status_rejected: bool
    note_added: bool
    note_did_not_change_evidence: bool
    timeline_deterministic: bool
    ground_truth_absent: bool
    incident_count: int


def _settings() -> Settings:
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url is None or "otsoc_test" not in test_url:
        raise SystemExit("TEST_DATABASE_URL must target the isolated otsoc_test database")
    return Settings(
        app_name="OT-SOC Fusion X",
        app_version="1.0.0",
        app_env="development",
        api_version="v1",
        log_level="WARNING",
        cors_origins=["http://localhost:5173"],
        database_url=test_url,
        database_connect_timeout_seconds=2,
    )


def _qualify(settings: Settings, request: IncidentQualificationRequest):  # type: ignore[no-untyped-def]
    with session_scope(settings) as session:
        return qualify_stored_evidence(session, request)


def main() -> int:
    settings = _settings()
    with engine_for(settings).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)

    s1_request = IncidentQualificationRequest(
        policy_finding=persist_policy_chain(settings, "s1_unknown_source_asset.json")
    )
    s1 = _qualify(settings, s1_request)
    retry = _qualify(settings, s1_request)
    s2 = _qualify(
        settings,
        IncidentQualificationRequest(
            policy_finding=persist_policy_chain(settings, "s2_it_to_controller.json")
        ),
    )
    s3a = _qualify(
        settings,
        persist_correlation_chain(
            settings,
            "p6b-f002.json",
            context_fixture="s3_hmi_approved_valve_command.json",
        ),
    )
    denied_policy = IncidentQualificationRequest(
        policy_finding=persist_policy_chain(settings, "s3_engineering_denied_valve_command.json")
    )
    s3b = _qualify(settings, denied_policy)
    s3_not_correlated = _qualify(
        settings,
        persist_correlation_chain(
            settings,
            "p6b-f002.json",
            context_fixture="s3_engineering_denied_valve_command.json",
        ),
    )
    s3c = _qualify(
        settings,
        persist_correlation_chain(
            settings,
            "p6b-f005.json",
            context_fixture="s3_hmi_approved_valve_command.json",
        ),
    )
    before_primary = s3b.incident.primary_evidence_id if s3b.incident else None
    s3d = _qualify(
        settings,
        persist_correlation_chain(
            settings,
            "p6b-f005.json",
            context_fixture="s3_engineering_denied_valve_command.json",
        ),
    )
    s4 = _qualify(settings, persist_correlation_chain(settings, "p6b-f008.json"))
    s4_other_run = _qualify(
        settings,
        persist_correlation_chain(
            settings,
            "p6b-f008.json",
            simulation_id="sim-phase7b-runtime-second",
        ),
    )
    s4_other_config = _qualify(
        settings,
        persist_correlation_chain(settings, "p6b-f008.json", configuration_hash="d" * 64),
    )

    def retry_s1() -> str:
        return str(_qualify(settings, s1_request).outcome)

    with ThreadPoolExecutor(max_workers=8) as executor:
        concurrent_outcomes = list(executor.map(lambda _: retry_s1(), range(8)))

    if s1.incident_id is None or s1.incident is None or s1_request.policy_finding is None:
        raise RuntimeError("S1 runtime proof did not create an incident")
    with session_scope(settings) as session:
        evidence = session.get(EvidenceRecord, s1_request.policy_finding.evidence_id)
        if evidence is None:
            raise RuntimeError("S1 evidence could not be reloaded")
        evidence_before = (dict(evidence.payload), evidence.integrity_sha256)
        investigating = transition_incident_status(
            session,
            s1.incident_id,
            new_status=IncidentStatus.INVESTIGATING,
            expected_version=s1.incident.version,
            actor_context="runtime-analyst",
            reason="Runtime review started.",
            request_id="runtime-status",
        )
    invalid_rejected = False
    with session_scope(settings) as session:
        try:
            transition_incident_status(
                session,
                s1.incident_id,
                new_status=IncidentStatus.OPEN,
                expected_version=investigating.version,
                actor_context="runtime-analyst",
                reason=None,
                request_id="runtime-invalid",
            )
        except IncidentLifecycleError:
            invalid_rejected = True
    with session_scope(settings) as session:
        noted = add_analyst_note(
            session,
            s1.incident_id,
            content="Runtime analyst context; it does not change stored evidence.",
            expected_version=investigating.version,
            actor_context="runtime-analyst",
            request_id="runtime-note",
        )
    with session_scope(settings) as session:
        evidence_after = session.get(EvidenceRecord, s1_request.policy_finding.evidence_id)
        detail = get_incident_detail(session, s1.incident_id)
        incident_count = session.scalar(select(func.count()).select_from(Incident)) or 0
        membership_count = (
            session.scalar(
                select(func.count())
                .select_from(IncidentEvidenceMembership)
                .where(IncidentEvidenceMembership.incident_id == s1.incident_id)
            )
            or 0
        )
        severity_rows = session.scalars(
            select(IncidentSeverityHistory).where(
                IncidentSeverityHistory.incident_id == s3d.incident_id
            )
        ).all()
    result = IncidentRuntimeCheckResult(
        s1_low=bool(s1.incident and s1.incident.severity.value == "LOW"),
        s2_medium=bool(s2.incident and s2.incident.severity.value == "MEDIUM"),
        s3_approved_not_correlated_evidence_only=s3a.outcome == "evidence_only",
        s3_denied_not_correlated_medium=bool(
            s3_not_correlated.incident and s3_not_correlated.incident.severity.value == "MEDIUM"
        ),
        s3_approved_correlated_medium=bool(
            s3c.incident and s3c.incident.severity.value == "MEDIUM"
        ),
        s3_denied_correlated_high=bool(s3d.incident and s3d.incident.severity.value == "HIGH"),
        s4_correlated_high=bool(s4.incident and s4.incident.severity.value == "HIGH"),
        retry_same_incident=retry.incident_id == s1.incident_id,
        concurrent_duplicate_safe=concurrent_outcomes == ["existing"] * 8 and membership_count == 1,
        late_s3_enriched=s3b.incident_id == s3d.incident_id and s3d.outcome == "enriched",
        primary_evidence_unchanged=bool(
            s3d.incident and s3d.incident.primary_evidence_id == before_primary
        ),
        severity_only_raised=[row.new_severity for row in severity_rows] == ["MEDIUM", "HIGH"],
        run_isolated=s4.incident_id != s4_other_run.incident_id,
        configuration_isolated=s4.incident_id != s4_other_config.incident_id,
        lifecycle_valid=investigating.status == "INVESTIGATING",
        invalid_status_rejected=invalid_rejected,
        note_added=noted.version == investigating.version + 1,
        note_did_not_change_evidence=bool(
            evidence_after
            and (dict(evidence_after.payload), evidence_after.integrity_sha256) == evidence_before
        ),
        timeline_deterministic=bool(
            detail
            and [item.observed_at for item in detail.timeline]
            == sorted(item.observed_at for item in detail.timeline)
        ),
        ground_truth_absent=bool(
            s1.incident
            and s2.incident
            and s3d.incident
            and s4.incident
            and not any(
                item.ground_truth_used
                for item in (s1.incident, s2.incident, s3d.incident, s4.incident)
            )
        ),
        incident_count=incident_count,
    )
    output = asdict(result)
    checks = [value for key, value in output.items() if key != "incident_count"]
    output["passed"] = all(checks)
    print(json.dumps(output, sort_keys=True))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
