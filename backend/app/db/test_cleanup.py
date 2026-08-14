from __future__ import annotations

from sqlalchemy import TextClause, text

# Dedicated local-test cleanup only. All tables participate in one PostgreSQL TRUNCATE so the
# restrictive incident-to-evidence foreign keys remain active in normal application operations.
TEST_DATA_TRUNCATE: TextClause = text(
    "TRUNCATE TABLE soc_audit_events, incident_report_revisions, incident_reports, "
    "lab_active_context, lab_run_incidents, lab_run_evidence, auth_sessions, "
    "incident_audit_events, incident_notes, incident_severity_history, "
    "incident_status_history, incident_timeline_entries, incident_evidence_memberships, "
    "incidents, lab_runs, local_users, evidence_records"
)
