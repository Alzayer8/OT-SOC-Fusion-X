# OT-SOC Fusion X v1.1.1 Portfolio Release Notes

This portfolio/publication copy presents the accepted OT-SOC Fusion X v1.1.1 application with a fresh Git history and curated public-safe documentation. It is not a new software release and does not change application behavior or scenario semantics.

## Highlights

- Protocol-to-process investigation from stored synthetic Modbus evidence through semantic, asset, policy, process, incident, and analyst context
- Fictional Oil & Gas transfer path: `TK-101 → P-101 → PL-101 → CV-101 → TK-102`
- Allowlisted Baseline and S1-S4 Scenario Lab workflows
- Featured S3 mapping from FC06 holding-register offset `1`, raw `250`, to the stored `CV-101` command at `25.0%`
- S4 pump/flow process inconsistency with no fabricated cyber cause
- Read-only Digital Twin and deterministic stored-evidence Replay
- Authenticated SOC workflow with assignment, disposition, notes, reports, audit history, and lifecycle
- Exactly three Docker services: PostgreSQL `db`, FastAPI `backend`, and React `frontend`

## Accepted local validation evidence

- 321 backend tests passed with 86.79% coverage
- 43 frontend tests passed
- 8 existing real-stack Playwright tests passed
- 1 screenshot-validation test passed
- Frozen v1.1 acceptance: 96/96
- v1.1.1 validation: 53/53
- Visual evidence: 32/32
- Docker services: 3/3 healthy
- Baseline: 0 current incidents

These values are accepted synthetic/local release evidence, not production benchmarks or certification claims.

## Safety boundary

The project remains synthetic, offline, academic, and advisory-only. It does not connect to real PLCs or facilities, transmit Modbus, scan networks, capture or inject packets, control equipment or processes, execute containment, or establish attacker intent. Correlation is not causation; `DENIED` is not maliciousness; and `TRUE_POSITIVE` confirms only the defined synthetic condition.

## Provenance

The protected accepted source release was verified at `0dfa3776a6acea97e25039a66d9f301c1d55a5ba` with tag `otsoc-fusion-x-v1.1.1`. This portfolio repository has independent Git history and therefore a different commit identity.
