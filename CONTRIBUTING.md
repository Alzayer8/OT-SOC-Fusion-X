# Contributing

Contributions are welcome when they preserve the project's synthetic, offline, advisory-only scope.

## Contribution boundaries

- Use only fictional assets, deterministic synthetic evidence, and the allowlisted Oil & Gas process model.
- Do not add real PLC connectivity, protocol transmission, packet capture/injection, network scanning, arbitrary industrial targeting, device control, process control, or automated containment.
- Preserve evidence traceability from raw records through semantics, context, correlation, incidents, and analyst decisions.
- Preserve claim boundaries: correlation is not causation, `DENIED` is not maliciousness, and `TRUE_POSITIVE` is not proof of a real attacker.
- Keep Digital Twin and Replay read-only and keep playbooks advisory-only.
- Do not commit `.env`, credentials, tokens, cookies, database data, logs, traces, or private facility information.

## Before proposing a change

1. Keep the change focused and explain which synthetic requirement it supports.
2. Add or update tests for behavior changes.
3. Run the relevant backend and frontend quality checks documented in `README.md`.
4. Verify `docker compose config --services` still lists exactly `db`, `backend`, and `frontend`.
5. Run a secret scan and inspect any screenshots or fixtures for sensitive or real-world data.
6. Document limitations and avoid claims that exceed measured synthetic/local evidence.

This portfolio release is based on accepted v1.1.1 behavior. Feature proposals should be discussed before implementation so they do not blur the project's safety boundary or accepted scenario semantics.
