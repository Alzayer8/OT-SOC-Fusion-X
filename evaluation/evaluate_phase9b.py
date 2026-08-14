from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
TRUTH_PATH = ROOT / "ground-truth" / "otsoc-final-eval-v1.json"


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def evaluate(receipt: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("dataset_id") != truth.get("dataset_id"):
        raise ValueError("dataset identity mismatch")
    if receipt.get("dataset_version") != truth.get("dataset_version"):
        raise ValueError("dataset version mismatch")
    if receipt.get("dataset_sha256") != truth.get("dataset_sha256"):
        raise ValueError("dataset digest mismatch")
    observed_cases = receipt.get("cases")
    expected_cases = truth.get("cases")
    if not isinstance(observed_cases, dict) or not isinstance(expected_cases, dict):
        raise ValueError("case maps are required")

    scenario_correct = 0
    correlation_correct = 0
    correlation_denominator = 0
    incident_correct = 0
    false_positives = 0
    false_negatives = 0
    lineage_required = 0
    lineage_resolved = 0
    replay_correct = 0
    replay_denominator = 0
    case_results: dict[str, Any] = {}

    for case_id, expected in expected_cases.items():
        observed = observed_cases.get(case_id)
        if not isinstance(observed, dict) or not isinstance(expected, dict):
            raise ValueError(f"case {case_id} is missing")
        expected_incident = expected.get("incident")
        observed_incident = observed.get("incident")
        incident_match = observed_incident == expected_incident
        policy_match = (
            "policy_statuses" not in expected
            or observed.get("policy_statuses") == expected.get("policy_statuses")
        ) and (
            "policy_reasons" not in expected
            or observed.get("policy_reasons") == expected.get("policy_reasons")
        )
        incident_correct += int(incident_match)
        is_background = case_id.endswith("BG-001")
        expected_correlation = expected.get("correlation_status")
        correlation_match = (
            observed.get("correlation_status") == expected_correlation
            and observed.get("correlation_reason") == expected.get("correlation_reason")
        )
        cyber_parent_match = True
        if "cyber_parent_count" in expected:
            correlation_evidence = observed.get("correlation_evidence")
            cyber_parent_match = isinstance(correlation_evidence, dict) and (
                correlation_evidence.get("cyber_parent_count") == expected["cyber_parent_count"]
            )
        scenario_match = (
            policy_match and incident_match and cyber_parent_match
            and (expected_correlation is None or correlation_match)
        )

        if is_background:
            false_positives += int(observed_incident is not None)
        else:
            false_negatives += int(expected_incident is not None and observed_incident is None)
            scenario_correct += int(scenario_match)

        if expected_correlation is not None:
            correlation_denominator += 1
            correlation_correct += int(correlation_match)

        required_types = set(expected.get("required_lineage_types", []))
        observed_types = set(observed.get("lineage_evidence_types", []))
        lineage_required += len(required_types)
        lineage_resolved += len(required_types & observed_types)
        if expected_incident is not None:
            replay_denominator += 1
            replay_correct += int(
                observed.get("replay_completeness") == "COMPLETE"
                and observed.get("replay_ordering_correct") is True
            )
        case_results[case_id] = {
            "scenario_match": scenario_match,
            "policy_match": policy_match,
            "correlation_match": correlation_match,
            "incident_match": incident_match,
            "cyber_parent_match": cyber_parent_match,
            "lineage_match": required_types <= observed_types,
            "replay_match": (
                True
                if expected_incident is None
                else observed.get("replay_completeness") == "COMPLETE"
                and observed.get("replay_ordering_correct") is True
            ),
        }

    metrics = {
        "scenario_qualification": {"passed": scenario_correct, "total": 4},
        "correlation_classification": {
            "passed": correlation_correct,
            "total": correlation_denominator,
        },
        "incident_outcomes": {"passed": incident_correct, "total": 5},
        "normal_false_positives": false_positives,
        "scenario_false_negatives": false_negatives,
        "lineage": {"resolved": lineage_resolved, "required": lineage_required},
        "replay": {"passed": replay_correct, "total": replay_denominator},
    }
    passed = (
        scenario_correct == 4
        and correlation_correct == correlation_denominator == 3
        and incident_correct == 5
        and false_positives == 0
        and false_negatives == 0
        and lineage_resolved == lineage_required
        and replay_correct == replay_denominator == 4
    )
    return {"passed": passed, "metrics": metrics, "cases": case_results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Score completed Phase 9B runtime output.")
    parser.add_argument(
        "--receipt",
        required=True,
        help="completed runtime receipt path, or '-' to read JSON from standard input",
    )
    parser.add_argument("--truth", type=Path, default=TRUTH_PATH)
    arguments = parser.parse_args()
    receipt = json.load(sys.stdin) if arguments.receipt == "-" else _load(Path(arguments.receipt))
    if not isinstance(receipt, dict):
        raise ValueError("the completed runtime receipt must contain one JSON object")
    result = evaluate(receipt, _load(arguments.truth))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
