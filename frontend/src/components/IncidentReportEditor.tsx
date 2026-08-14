import { useMemo, useState } from "react";

import {
  ApiError,
  getIncidentReport,
  saveIncidentReport,
  type IncidentReport,
  type IncidentReportFields,
  type WorkflowIncidentDetail,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useApiResource } from "../hooks/useApiResource";
import { formatTimestamp } from "../utils/presentation";
import { ExactStatusBadge, LoadingSkeleton, ProductError } from "./ProductComponents";

const FIELD_DEFINITIONS: { key: keyof IncidentReportFields; label: string }[] = [
  { key: "investigation_summary", label: "Investigation Summary" },
  { key: "analyst_assessment", label: "Analyst Assessment" },
  { key: "evidence_assessment", label: "Evidence Assessment" },
  { key: "process_impact_assessment", label: "Process Impact Assessment" },
  { key: "disposition_rationale", label: "Disposition Rationale" },
  { key: "recommended_follow_up", label: "Recommended Follow-up" },
  { key: "final_conclusion", label: "Final Conclusion" },
];

const EMPTY_FIELDS: IncidentReportFields = {
  investigation_summary: "",
  analyst_assessment: "",
  evidence_assessment: "",
  process_impact_assessment: "",
  disposition_rationale: "",
  recommended_follow_up: "",
  final_conclusion: "",
};

export function IncidentReportEditor({ detail }: { detail: WorkflowIncidentDetail }) {
  const state = useApiResource(`incident-report:${detail.incident.incident_id}`, async (signal) => {
    try {
      return await getIncidentReport(detail.incident.incident_id, signal);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        return {
          ...EMPTY_FIELDS,
          incident_id: detail.incident.incident_id,
          created_by_user_id: null,
          created_at: null,
          updated_by_user_id: null,
          updated_at: null,
          version: 0,
          fields_filled: 0,
          fields_total: 7,
        } satisfies IncidentReport;
      }
      throw error;
    }
  });

  if (state.status === "loading") return <LoadingSkeleton label="Loading analyst report" />;
  if (state.status === "error") return <ProductError {...state} />;
  return <ReportWorkspace detail={detail} initial={state.data} />;
}

function ReportWorkspace({
  detail,
  initial,
}: {
  detail: WorkflowIncidentDetail;
  initial: IncidentReport;
}) {
  const auth = useAuth();
  const canEdit = auth.hasRole("ADMIN", "SOC_ANALYST");
  const [report, setReport] = useState(initial);
  const [fields, setFields] = useState<IncidentReportFields>(() => fieldsFrom(initial));
  const [preview, setPreview] = useState(!canEdit);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const completed = useMemo(
    () => FIELD_DEFINITIONS.filter(({ key }) => fields[key].trim()).length,
    [fields],
  );

  const save = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const saved = await saveIncidentReport(detail.incident.incident_id, fields, report.version);
      setReport(saved);
      setFields(fieldsFrom(saved));
      setMessage("Analyst report draft saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Report save failed.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="report-workspace">
      <section className="report-context panel">
        <div className="panel__header">
          <div>
            <span className="section-kicker">Read-only sourced context</span>
            <h2>Incident report context</h2>
          </div>
          <ExactStatusBadge value={`${completed} OF 7 FIELDS`} />
        </div>
        <div className="panel__content">
          <dl className="detail-grid">
            <div>
              <dt>Incident ID</dt>
              <dd className="mono">{detail.incident.incident_id}</dd>
            </div>
            <div>
              <dt>Category</dt>
              <dd>{detail.incident.category}</dd>
            </div>
            <div>
              <dt>Severity</dt>
              <dd>{detail.incident.severity}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{detail.incident.status}</dd>
            </div>
            <div>
              <dt>Disposition</dt>
              <dd>{detail.incident.disposition ?? "UNREVIEWED"}</dd>
            </div>
            <div>
              <dt>Assignee</dt>
              <dd>{detail.incident.assignee_display_name ?? "Unassigned"}</dd>
            </div>
            <div>
              <dt>First observed</dt>
              <dd>{formatTimestamp(detail.incident.first_observed_at)}</dd>
            </div>
            <div>
              <dt>Last observed</dt>
              <dd>{formatTimestamp(detail.incident.last_observed_at)}</dd>
            </div>
            <div>
              <dt>Evidence membership</dt>
              <dd>{detail.evidence_memberships.length}</dd>
            </div>
            <div>
              <dt>Policy / correlation</dt>
              <dd>
                {detail.incident.policy_context} / {detail.incident.correlation_context}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <div className="report-toolbar print-hide">
        {canEdit ? (
          <button className="button" type="button" onClick={() => setPreview(false)}>
            Edit Report
          </button>
        ) : null}
        {canEdit ? (
          <button className="button" disabled={saving} type="button" onClick={() => void save()}>
            {saving ? "Saving…" : "Save Draft"}
          </button>
        ) : null}
        <button className="button" type="button" onClick={() => setPreview(true)}>
          Preview
        </button>
        <button className="button" type="button" onClick={() => window.print()}>
          Print
        </button>
      </div>
      {!canEdit ? (
        <p className="partial-banner">
          Your authenticated role may review this report but cannot edit it.
        </p>
      ) : null}
      {message ? <p role="status">{message}</p> : null}

      {preview ? (
        <article className="analyst-report-preview panel">
          <div className="panel__header">
            <div>
              <p className="page-header__eyebrow">Synthetic / Offline · Analyst Report</p>
              <h2>{detail.incident.title}</h2>
            </div>
          </div>
          <div className="panel__content">
            {FIELD_DEFINITIONS.map(({ key, label }) => (
              <section key={key}>
                <h3>{label}</h3>
                <p>{fields[key].trim() || "Not completed."}</p>
              </section>
            ))}
            <p className="report-disclaimer">
              Academic synthetic evidence. Analyst interpretation does not rewrite evidence, prove
              malicious intent, or establish causation.
            </p>
          </div>
        </article>
      ) : (
        <section className="panel">
          <div className="panel__header">
            <h2>Analyst report draft</h2>
          </div>
          <div className="panel__content report-field-grid">
            {FIELD_DEFINITIONS.map(({ key, label }) => (
              <label key={key}>
                {label}
                <textarea
                  disabled={!canEdit}
                  maxLength={4000}
                  value={fields[key]}
                  onChange={(event) =>
                    setFields((current) => ({ ...current, [key]: event.target.value }))
                  }
                />
                <small>{fields[key].length} / 4000</small>
              </label>
            ))}
          </div>
        </section>
      )}
      <p className="report-metadata">
        Created {report.created_at ? formatTimestamp(report.created_at) : "when first saved"} by{" "}
        {report.created_by_user_id ?? "—"} · Updated{" "}
        {report.updated_at ? formatTimestamp(report.updated_at) : "not yet"} by{" "}
        {report.updated_by_user_id ?? "—"}
      </p>
    </div>
  );
}

function fieldsFrom(report: IncidentReport): IncidentReportFields {
  return Object.fromEntries(
    FIELD_DEFINITIONS.map(({ key }) => [key, report[key] ?? ""]),
  ) as unknown as IncidentReportFields;
}
