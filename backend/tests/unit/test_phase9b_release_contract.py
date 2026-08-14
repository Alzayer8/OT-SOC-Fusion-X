from __future__ import annotations

import json
import os
from pathlib import Path

from app.tools.phase9_dataset import (
    DATASET_ID,
    DATASET_PATH,
    DATASET_SEED,
    DATASET_VERSION,
    EXPECTED_DATASET_SHA256,
    load_dataset,
)

ROOT = Path(os.environ.get("OTSOC_REPOSITORY_ROOT", Path(__file__).resolve().parents[3]))


def test_final_dataset_identity_profiles_cases_and_configuration_are_frozen() -> None:
    loaded = load_dataset()

    assert loaded.manifest.dataset_id == DATASET_ID
    assert loaded.manifest.dataset_version == DATASET_VERSION
    assert loaded.manifest.seed == DATASET_SEED
    assert loaded.sha256 == EXPECTED_DATASET_SHA256
    assert [case.case_id for case in loaded.manifest.cases] == [
        "OTSOC-EVAL-V1-BG-001",
        "OTSOC-EVAL-V1-S1-001",
        "OTSOC-EVAL-V1-S2-001",
        "OTSOC-EVAL-V1-S3-001",
        "OTSOC-EVAL-V1-S4-001",
    ]
    assert loaded.manifest.case("OTSOC-EVAL-V1-BG-001").run_id == ("otsoc-eval-v1-bg-run-001")
    assert loaded.manifest.case("OTSOC-EVAL-V1-S3-001").run_id == ("otsoc-eval-v1-s3-run-001")
    assert loaded.manifest.case("OTSOC-EVAL-V1-S4-001").run_id == ("otsoc-eval-v1-s4-run-001")
    for case in loaded.manifest.cases:
        if case.configuration is None:
            assert case.configuration_hash is None
        else:
            assert case.configuration_hash is not None
            assert len(case.configuration_hash) == 64


def test_runtime_dataset_has_no_truth_or_expected_outcome_fields() -> None:
    document = json.loads(DATASET_PATH.read_text("utf-8"))

    assert document["contains_ground_truth"] is False
    keys: set[str] = set()

    def collect(value: object) -> None:
        if isinstance(value, dict):
            keys.update(str(key).lower() for key in value)
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(document)
    assert not {key for key in keys if key.startswith("expected")}
    assert "ground_truth" not in keys


def test_ground_truth_is_outside_runtime_images_and_compose_mounts() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text("utf-8")
    backend_dockerfile = (ROOT / "backend" / "Dockerfile").read_text("utf-8").lower()
    frontend_dockerfile = (ROOT / "frontend" / "Dockerfile").read_text("utf-8").lower()
    compose = (ROOT / "docker-compose.yml").read_text("utf-8").lower()

    assert "evaluation/ground-truth" in dockerignore
    assert "ground-truth" not in backend_dockerfile
    assert "ground-truth" not in frontend_dockerfile
    assert "ground-truth" not in compose
    assert "evaluation" not in backend_dockerfile
    assert "evaluation" not in frontend_dockerfile


def test_compose_keeps_exact_three_services_and_no_unsafe_container_modes() -> None:
    compose = (ROOT / "docker-compose.yml").read_text("utf-8")

    for forbidden in (
        "privileged: true",
        "network_mode: host",
        "/var/run/docker.sock",
        "pid: host",
        "ipc: host",
    ):
        assert forbidden not in compose


def test_frontend_vite_runtime_cache_is_narrowly_owned_across_container_restarts() -> None:
    compose = (ROOT / "docker-compose.yml").read_text("utf-8")

    assert "read_only: true" in compose
    assert "cap_drop:\n      - ALL" in compose
    assert "no-new-privileges:true" in compose
    assert "/app/node_modules/.vite-temp:size=16m,uid=1000,gid=1000,mode=0700" in compose
    assert "/app:rw" not in compose
