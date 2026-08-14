# Security Policy

## Supported release

The portfolio copy documents and supports the accepted `v1.1.1` synthetic academic release.

## Project boundary

OT-SOC Fusion X is an offline, synthetic, advisory-only investigation platform. It does not connect to real industrial equipment, transmit Modbus commands, capture or inject packets, scan networks, control a process, or execute containment actions.

Do not use this project to target, probe, connect to, or control a real OT/ICS environment. Security research and contributions must remain within the repository's fictional process, deterministic fixtures, local containers, and allowlisted scenarios.

## Reporting a vulnerability

Use the repository's private vulnerability-reporting or Security Advisory feature when available. If no private reporting channel is enabled, open a minimal issue requesting a secure contact channel without including exploit details, credentials, tokens, facility information, or personal data.

Please include, through a private channel:

- the affected version and component;
- reproducible steps using only the synthetic local environment;
- expected and observed behavior;
- impact within the documented academic scope; and
- a proposed mitigation, if known.

Never submit passwords, session cookies, CSRF tokens, database contents, private keys, `.env` files, or information from a real organization or industrial facility.

## Safe handling expectations

- Reproduce only against a local copy you are authorized to test.
- Use generated, disposable local credentials.
- Preserve the distinction between correlation, causation, policy status, and malicious intent.
- Do not add real-target connectivity, packet transmission, scanning, exploitation, device control, or automated response.
- Remove sensitive data from screenshots, logs, traces, and test output before sharing.

This policy is a responsible-reporting guide for an academic prototype; it is not a security certification or a statement of production readiness.
