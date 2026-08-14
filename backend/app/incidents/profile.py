from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.incidents.canonical import canonical_profile_bytes, sha256_hex
from app.incidents.models import (
    EvidenceRole,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    SemVer,
    TimelineEntryType,
)

MAX_PROFILE_BYTES = 65_536
PROFILE_ROOT = Path(__file__).resolve().parent / "profiles"
PROFILE_FILENAME = "oil_gas_incident_v1.json"
EXPECTED_INCIDENT_PROFILE_SHA256 = (
    "609de2ee030102c7f36c22109748e7b53b019fedd51125b3bc3af23c8fd53411"
)


class IncidentProfileError(ValueError):
    pass


class StrictProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False, frozen=True)


class EvidenceSchemaContract(StrictProfileModel):
    evidence_type: Literal[
        "protocol_semantic_event",
        "asset_context_event",
        "communication_policy_finding",
        "correlation_finding",
    ]
    schema_id: Literal[
        "otsoc.protocol.semantic_event",
        "otsoc.asset.context_event",
        "otsoc.communication_policy.finding",
        "otsoc.cyber_physical.correlation_finding",
    ]
    schema_version: Literal["1.0.0"]


class GroupingContract(StrictProfileModel):
    window_seconds: Literal[300]
    window_kind: Literal["FIXED_NON_OVERLAPPING_UTC"]
    timestamp_authority: Literal["OBSERVED_AT"]
    s1_s2_run_scope: Literal["NO_SIMULATION_SCOPE"]
    denied_s3_run_scope: Literal["UNBOUND_PROCESS_SCOPE"]


class IncidentRule(StrictProfileModel):
    rule_id: str = Field(min_length=1, max_length=80)
    rule_version: SemVer
    branch: Literal["S1", "S2", "S3", "S4"]
    category: IncidentCategory
    initial_severity: IncidentSeverity
    required_evidence_types: tuple[str, ...]
    title_template_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=600)


class IncidentProfile(StrictProfileModel):
    profile_id: Literal["otsoc.incident.oil_gas_transfer"]
    profile_version: Literal["1.0.0"]
    incident_schema: Literal["otsoc.incident.record"]
    incident_schema_version: Literal["1.0.0"]
    domain: Literal["oil_gas_transfer"]
    educational_only: Literal[True]
    disclaimer: Literal[
        "Fictional academic incident qualification; advisory investigation context only."
    ]
    categories: tuple[IncidentCategory, ...]
    severities: tuple[IncidentSeverity, ...]
    statuses: tuple[IncidentStatus, ...]
    initial_status: Literal[IncidentStatus.OPEN]
    evidence_roles: tuple[EvidenceRole, ...]
    timeline_entry_types: tuple[TimelineEntryType, ...]
    evidence_schemas: tuple[EvidenceSchemaContract, ...]
    grouping: GroupingContract
    rules: tuple[IncidentRule, ...] = Field(min_length=4, max_length=4)
    ground_truth_used: Literal[False]
    malicious_intent_inferred: Literal[False]
    causality_inferred: Literal[False]

    @model_validator(mode="after")
    def validate_frozen_contract(self) -> IncidentProfile:
        _require_exact_catalog(self.categories, IncidentCategory, "incident category")
        _require_exact_catalog(self.severities, IncidentSeverity, "incident severity")
        _require_exact_catalog(self.statuses, IncidentStatus, "incident status")
        _require_exact_catalog(self.evidence_roles, EvidenceRole, "evidence role")
        _require_exact_catalog(self.timeline_entry_types, TimelineEntryType, "timeline entry type")
        schema_pairs = {
            (item.evidence_type, item.schema_id, item.schema_version)
            for item in self.evidence_schemas
        }
        expected_schemas = {
            ("protocol_semantic_event", "otsoc.protocol.semantic_event", "1.0.0"),
            ("asset_context_event", "otsoc.asset.context_event", "1.0.0"),
            (
                "communication_policy_finding",
                "otsoc.communication_policy.finding",
                "1.0.0",
            ),
            (
                "correlation_finding",
                "otsoc.cyber_physical.correlation_finding",
                "1.0.0",
            ),
        }
        if schema_pairs != expected_schemas or len(self.evidence_schemas) != 4:
            raise ValueError("evidence schema catalog differs from the frozen contract")
        expected_rules = {
            "IQR-S1-UNKNOWN-SOURCE-001": (
                "S1",
                IncidentCategory.ASSET_IDENTITY_ANOMALY,
                IncidentSeverity.LOW,
                "INCIDENT_S1_UNKNOWN_SOURCE",
                "Unknown synthetic source identity",
            ),
            "IQR-S2-IT-PLC-POLICY-001": (
                "S2",
                IncidentCategory.COMMUNICATION_POLICY_VIOLATION,
                IncidentSeverity.MEDIUM,
                "INCIDENT_S2_POLICY_VIOLATION",
                "Unapproved synthetic IT-to-controller communication",
            ),
            "IQR-S3-CV-COMMAND-001": (
                "S3",
                IncidentCategory.CONTROL_COMMAND_INVESTIGATION,
                IncidentSeverity.MEDIUM,
                "INCIDENT_S3_CONTROL_COMMAND",
                "CV-101 control-command investigation",
            ),
            "IQR-S4-PUMP-FLOW-001": (
                "S4",
                IncidentCategory.PROCESS_INCONSISTENCY,
                IncidentSeverity.HIGH,
                "INCIDENT_S4_PROCESS_INCONSISTENCY",
                "P-101/PL-101 process inconsistency",
            ),
        }
        rules = {rule.rule_id: rule for rule in self.rules}
        if set(rules) != set(expected_rules) or len(rules) != 4:
            raise ValueError("exactly the four approved qualification rules are required")
        for rule_id, expected in expected_rules.items():
            rule = rules[rule_id]
            if (
                rule.rule_version,
                rule.branch,
                rule.category,
                rule.initial_severity,
                rule.title_template_id,
                rule.title,
            ) != ("1.0.0", *expected):
                raise ValueError("incident rule identity or mapping differs from the contract")
            normalized = f"{rule.title} {rule.summary}".lower()
            if any(
                phrase in normalized
                for phrase in (
                    "confirmed attack",
                    "confirmed cyberattack",
                    "attacker",
                    "compromised",
                    "sabotage caused",
                    "definitely caused",
                )
            ):
                raise ValueError("incident templates contain a prohibited intent or causal claim")
        required = {
            "IQR-S1-UNKNOWN-SOURCE-001": ("communication_policy_finding",),
            "IQR-S2-IT-PLC-POLICY-001": ("communication_policy_finding",),
            "IQR-S3-CV-COMMAND-001": (
                "communication_policy_finding",
                "correlation_finding",
            ),
            "IQR-S4-PUMP-FLOW-001": ("correlation_finding",),
        }
        if any(
            tuple(sorted(rules[key].required_evidence_types)) != value
            for key, value in required.items()
        ):
            raise ValueError("incident evidence requirements differ from the contract")
        return self


@dataclass(frozen=True)
class LoadedIncidentProfile:
    profile: IncidentProfile
    sha256: str

    @property
    def rules(self) -> dict[str, IncidentRule]:
        return {rule.rule_id: rule for rule in self.profile.rules}


def load_incident_profile(
    profile_id: str = "otsoc.incident.oil_gas_transfer",
    profile_version: str = "1.0.0",
    *,
    expected_sha256: str | None = None,
) -> LoadedIncidentProfile:
    if (profile_id, profile_version) != (
        "otsoc.incident.oil_gas_transfer",
        "1.0.0",
    ):
        raise IncidentProfileError("The requested incident profile ID/version is unavailable.")
    path = PROFILE_ROOT / PROFILE_FILENAME
    if path.is_symlink() or path.resolve().parent != PROFILE_ROOT.resolve():
        raise IncidentProfileError("The approved incident profile path is unsafe.")
    loaded = parse_incident_profile_bytes(path.read_bytes())
    required = expected_sha256 or EXPECTED_INCIDENT_PROFILE_SHA256
    if required == "PENDING" or loaded.sha256 != required:
        raise IncidentProfileError("The incident profile digest is not approved.")
    return loaded


def parse_incident_profile_bytes(content: bytes) -> LoadedIncidentProfile:
    if not content or len(content) > MAX_PROFILE_BYTES:
        raise IncidentProfileError("The incident profile exceeds the approved size bound.")
    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        profile = IncidentProfile.model_validate(document)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise IncidentProfileError("The incident profile is invalid.") from exc
    return LoadedIncidentProfile(
        profile=profile,
        sha256=sha256_hex(canonical_profile_bytes(profile)),
    )


def _require_exact_catalog(values: tuple[Any, ...], enum_type: type[StrEnum], label: str) -> None:
    expected = tuple(enum_type.__members__.values())
    if set(values) != set(expected) or len(values) != len(expected):
        raise ValueError(f"{label} catalog differs from the frozen contract")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IncidentProfileError("The incident profile has a duplicate JSON key.")
        result[key] = value
    return result
