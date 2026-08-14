import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  addIncidentNote,
  ApiError,
  assignIncident,
  getIncidentAssignees,
  getIncidentAudit,
  patchIncidentStatus,
  setIncidentDisposition,
  type IncidentDisposition,
  type WorkflowIncidentDetail,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useApiResource } from "../hooks/useApiResource";
import { formatTimestamp, shortId } from "../utils/presentation";
import { Icon } from "./Icons";
import { IncidentReportEditor } from "./IncidentReportEditor";
import {
  DataTable,
  ExactStatusBadge,
  LoadingSkeleton,
  ProductError,
  SeverityBadge,
} from "./ProductComponents";
import { MiniStat } from "./Visualizations";

const TABS = ["OVERVIEW", "EVIDENCE", "TIMELINE", "INVESTIGATION", "REPORT"] as const;
type WorkspaceTab = (typeof TABS)[number];

export function IncidentWorkspaceTabs({
  detail,
  onChanged,
}: {
  detail: WorkflowIncidentDetail;
  onChanged: () => void;
}) {
  const [params, setParams] = useSearchParams();
  const requested = params.get("tab")?.toUpperCase();
  const tab: WorkspaceTab = TABS.includes(requested as WorkspaceTab)
    ? (requested as WorkspaceTab)
    : "OVERVIEW";
  const incident = detail.incident;
  const selectTab = (next: WorkspaceTab) => {
    const updated = new URLSearchParams(params);
    if (next === "OVERVIEW") updated.delete("tab");
    else updated.set("tab", next.toLowerCase());
    setParams(updated, { replace: true });
  };

  return (
    <>
      <section className="incident-hero panel">
        <div className="incident-hero__identity">
          <span className="incident-hero__icon" aria-hidden="true">
            <Icon name="incidents" />
          </span>
          <span className="mono">{incident.incident_id}</span>
          <h2>{incident.title}</h2>
          <p>{incident.summary}</p>
        </div>
        <div className="incident-hero__status">
          <SeverityBadge severity={incident.severity} />
          <ExactStatusBadge value={incident.status} />
          <ExactStatusBadge value={incident.disposition ?? "UNREVIEWED"} />
          <span>{incident.assignee_display_name ?? "Unassigned"}</span>
          <span>Version {incident.version}</span>
        </div>
      </section>
      <section className="incident-context-strip" aria-label="Incident context summary">
        <MiniStat
          label="Severity"
          value={incident.severity}
          note="LOW / MEDIUM / HIGH"
          tone={
            incident.severity === "HIGH"
              ? "red"
              : incident.severity === "MEDIUM"
                ? "amber"
                : "green"
          }
        />
        <MiniStat
          label="Lifecycle"
          value={incident.status}
          note={`Aggregate version ${incident.version}`}
          tone="blue"
        />
        <MiniStat
          label="Disposition"
          value={incident.disposition ?? "UNREVIEWED"}
          note="Separate analyst decision"
          tone="purple"
        />
        <MiniStat
          label="Assignee"
          value={incident.assignee_display_name ?? "Unassigned"}
          note={
            incident.assigned_at ? formatTimestamp(incident.assigned_at) : "No assignment recorded"
          }
          tone="cyan"
        />
      </section>
      <div
        className="mode-tabs incident-workspace-tabs"
        role="tablist"
        aria-label="Incident workspace"
      >
        {TABS.map((item) => (
          <button
            aria-selected={tab === item}
            key={item}
            role="tab"
            type="button"
            onClick={() => selectTab(item)}
          >
            {item[0]}
            {item.slice(1).toLowerCase()}
          </button>
        ))}
      </div>
      {tab === "OVERVIEW" ? <OverviewTab detail={detail} /> : null}
      {tab === "EVIDENCE" ? <EvidenceTab detail={detail} /> : null}
      {tab === "TIMELINE" ? <TimelineTab detail={detail} /> : null}
      {tab === "INVESTIGATION" ? <InvestigationTab detail={detail} onChanged={onChanged} /> : null}
      {tab === "REPORT" ? <IncidentReportEditor detail={detail} /> : null}
    </>
  );
}

function OverviewTab({ detail }: { detail: WorkflowIncidentDetail }) {
  const incident = detail.incident;
  const correlation = detail.evidence_memberships.find(
    (item) => item.evidence_type === "correlation_finding",
  );
  const scenario = incident.scenario_id ?? scenarioFromRule(incident.qualification_rule_id);
  return (
    <div className="workspace-grid">
      <section className="panel">
        <div className="panel__header">
          <h2>Investigation summary</h2>
        </div>
        <div className="panel__content">
          <dl className="detail-grid">
            <div>
              <dt>Category</dt>
              <dd>{incident.category}</dd>
            </div>
            <div>
              <dt>First observed</dt>
              <dd>{formatTimestamp(incident.first_observed_at)}</dd>
            </div>
            <div>
              <dt>Last observed</dt>
              <dd>{formatTimestamp(incident.last_observed_at)}</dd>
            </div>
            <div>
              <dt>Evidence count</dt>
              <dd>{incident.evidence_count}</dd>
            </div>
            <div>
              <dt>Policy context</dt>
              <dd>
                <ExactStatusBadge value={incident.policy_context} />
              </dd>
            </div>
            <div>
              <dt>Correlation context</dt>
              <dd>
                <ExactStatusBadge value={incident.correlation_context} />
              </dd>
            </div>
            <div>
              <dt>Run ID</dt>
              <dd className="mono">{incident.run_id ?? "Historical run identity unavailable"}</dd>
            </div>
            <div>
              <dt>Scenario</dt>
              <dd>{scenario}</dd>
            </div>
          </dl>
          <h3>Affected assets and points</h3>
          <p>{incident.process_asset_keys.join(" → ") || "Process asset context unavailable"}</p>
          <p>{incident.target_point_ids.join(", ") || "Target point context unavailable"}</p>
          {detail.context.unavailable.length ? (
            <div className="partial-banner">
              Unavailable context: {detail.context.unavailable.join(", ")}. Missing context does not
              imply safety.
            </div>
          ) : null}
          <div className="action-links">
            {incident.s3_semantic_evidence_id ? (
              <Link to={`/protocol-analysis?evidence=${incident.s3_semantic_evidence_id}`}>
                Open protocol semantic evidence
              </Link>
            ) : null}
            <Link to={`/digital-twin?incident=${incident.incident_id}`}>
              Open read-only Digital Twin
            </Link>
            <Link to={`/replay?incident=${incident.incident_id}`}>Open stored-evidence Replay</Link>
            <Link to={`/playbooks?type=${scenario}&incident=${incident.incident_id}`}>
              Open Recommended Playbook
            </Link>
            {correlation ? (
              <Link to={`/protocol-analysis?evidence=${correlation.evidence_id}`}>
                Inspect correlation evidence
              </Link>
            ) : null}
          </div>
        </div>
      </section>
      <section className="panel">
        <div className="panel__header">
          <h2>Current triage state</h2>
        </div>
        <div className="panel__content">
          <dl className="detail-grid">
            <div>
              <dt>Status</dt>
              <dd>{incident.status}</dd>
            </div>
            <div>
              <dt>Disposition</dt>
              <dd>{incident.disposition ?? "UNREVIEWED"}</dd>
            </div>
            <div>
              <dt>Assignee</dt>
              <dd>{incident.assignee_display_name ?? "Unassigned"}</dd>
            </div>
            <div>
              <dt>Evidence preserved</dt>
              <dd>Yes · append-only source evidence</dd>
            </div>
          </dl>
          <p className="safety-copy">
            TRUE_POSITIVE confirms only that the defined synthetic condition was identified; it does
            not prove an attacker, compromise, maliciousness, or cause.
          </p>
        </div>
      </section>
    </div>
  );
}

function EvidenceTab({ detail }: { detail: WorkflowIncidentDetail }) {
  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Evidence membership and lineage</h2>
      </div>
      <div className="panel__content">
        <DataTable label="Incident evidence memberships">
          <thead>
            <tr>
              <th>Role</th>
              <th>Type</th>
              <th>Evidence ID</th>
              <th>Observed</th>
              <th>Integrity</th>
            </tr>
          </thead>
          <tbody>
            {detail.evidence_memberships.map((item) => (
              <tr key={item.membership_id}>
                <td>{item.role}</td>
                <td>{item.evidence_type}</td>
                <td>
                  <Link className="mono" to={`/protocol-analysis?evidence=${item.evidence_id}`}>
                    {shortId(item.evidence_id)}
                  </Link>
                </td>
                <td>{formatTimestamp(item.observed_at)}</td>
                <td className="mono" title={item.integrity_sha256}>
                  {shortId(item.integrity_sha256)}
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
        <div className="lineage-flow" aria-label="Verified evidence lineage">
          {detail.lineage_references.map((item, index) => (
            <div key={item.evidence_id} className="lineage-node">
              <span>{index + 1}</span>
              <strong>{item.evidence_type.replaceAll("_", " ")}</strong>
              <small>{item.relationship}</small>
              <code title={item.evidence_id}>{shortId(item.evidence_id)}</code>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function TimelineTab({ detail }: { detail: WorkflowIncidentDetail }) {
  return (
    <div className="page-stack">
      <section className="panel">
        <div className="panel__header">
          <h2>Deterministic incident timeline</h2>
        </div>
        <div className="panel__content">
          <ol className="timeline-list">
            {detail.timeline.map((item) => (
              <li key={item.timeline_entry_id}>
                <time>{formatTimestamp(item.observed_at)}</time>
                <div>
                  <strong>{item.entry_type.replaceAll("_", " ")}</strong>
                  <p>{item.summary}</p>
                  <small>
                    Recorded {formatTimestamp(item.recorded_at)} · aggregate v
                    {item.aggregate_version}
                  </small>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>
      <div className="workspace-grid">
        <History
          title="Status history"
          items={detail.status_history.map((item) => ({
            id: item.status_history_id,
            title: `${item.previous_status ?? "INITIAL"} → ${item.new_status}`,
            time: item.changed_at,
            note: item.reason ?? "No reason supplied",
          }))}
        />
        <History
          title="Severity history"
          items={detail.severity_history.map((item) => ({
            id: item.severity_history_id,
            title: `${item.previous_severity ?? "INITIAL"} → ${item.new_severity}`,
            time: item.calculated_at,
            note: `Rule ${item.rule_version}`,
          }))}
        />
      </div>
    </div>
  );
}

function InvestigationTab({
  detail,
  onChanged,
}: {
  detail: WorkflowIncidentDetail;
  onChanged: () => void;
}) {
  const auth = useAuth();
  const canAnalystMutate = auth.hasRole("ADMIN", "SOC_ANALYST");
  const canNote = auth.hasRole("ADMIN", "SOC_ANALYST", "OT_ENGINEER");
  const audit = useApiResource(
    `incident-audit:${detail.incident.incident_id}:${detail.incident.version}`,
    (signal) => getIncidentAudit(detail.incident.incident_id, signal),
  );
  const assignees = useApiResource(`incident-assignees:${canAnalystMutate}`, (signal) =>
    canAnalystMutate ? getIncidentAssignees(signal) : Promise.resolve({ items: [] }),
  );
  return (
    <div className="page-stack">
      {!canAnalystMutate && !canNote ? (
        <p className="partial-banner">
          Your authenticated role has read-only incident access. Mutation APIs remain
          server-authorized.
        </p>
      ) : null}
      <div className="workspace-grid">
        {canAnalystMutate ? (
          assignees.status === "success" ? (
            <AssignmentPanel detail={detail} users={assignees.data.items} onChanged={onChanged} />
          ) : assignees.status === "loading" ? (
            <LoadingSkeleton label="Loading authorized assignees" />
          ) : (
            <ProductError {...assignees} />
          )
        ) : null}
        {canAnalystMutate ? <DispositionPanel detail={detail} onChanged={onChanged} /> : null}
        {canAnalystMutate ? <LifecyclePanel detail={detail} onChanged={onChanged} /> : null}
      </div>
      <section className="panel">
        <div className="panel__header">
          <h2>Analyst notes</h2>
        </div>
        <div className="panel__content">
          {detail.notes.length ? (
            <ul className="note-list">
              {detail.notes.map((item) => (
                <li key={item.note_id}>
                  <p>{item.content}</p>
                  <small>
                    {item.actor_context} · {formatTimestamp(item.created_at)} · aggregate v
                    {item.aggregate_version}
                  </small>
                </li>
              ))}
            </ul>
          ) : (
            <p>No analyst notes are stored.</p>
          )}
          {canNote ? <NoteForm detail={detail} onChanged={onChanged} /> : null}
        </div>
      </section>
      <section className="panel">
        <div className="panel__header">
          <h2>Authenticated incident audit trail</h2>
        </div>
        <div className="panel__content">
          {audit.status === "loading" ? <LoadingSkeleton label="Loading incident audit" /> : null}
          {audit.status === "error" ? <ProductError {...audit} /> : null}
          {audit.status === "success" && audit.data.items.length ? (
            <ol className="history-list">
              {audit.data.items.map((item) => (
                <li key={item.audit_id}>
                  <strong>{item.action.replaceAll("_", " ")}</strong>
                  <span>
                    {item.actor_display_name} · {formatTimestamp(item.occurred_at)}
                  </span>
                  <small>{item.summary}</small>
                </li>
              ))}
            </ol>
          ) : null}
          {audit.status === "success" && !audit.data.items.length ? (
            <p>No workflow audit entries are stored.</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function AssignmentPanel({
  detail,
  users,
  onChanged,
}: {
  detail: WorkflowIncidentDetail;
  users: { user_id: string; display_name: string; role: string }[];
  onChanged: () => void;
}) {
  const auth = useAuth();
  const [selected, setSelected] = useState(detail.incident.assignee_user_id ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const submit = async (userId: string | null) => {
    try {
      await assignIncident(detail.incident.incident_id, userId, detail.incident.version);
      setMessage("Incident assignment updated.");
      onChanged();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Assignment failed.");
    }
  };
  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Incident assignment</h2>
      </div>
      <div className="panel__content">
        <label>
          Authorized local analyst
          <select value={selected} onChange={(event) => setSelected(event.target.value)}>
            <option value="">Unassigned</option>
            {users
              .filter((user) => user.role === "ADMIN" || user.role === "SOC_ANALYST")
              .map((user) => (
                <option key={user.user_id} value={user.user_id}>
                  {user.display_name} · {user.role.replaceAll("_", " ")}
                </option>
              ))}
          </select>
        </label>
        <div className="action-links">
          <button className="button" type="button" onClick={() => void submit(selected || null)}>
            Save assignment
          </button>
          {auth.user ? (
            <button
              className="button"
              type="button"
              onClick={() => void submit(auth.user!.user_id)}
            >
              Assign to me
            </button>
          ) : null}
        </div>
        {message ? <p role="status">{message}</p> : null}
      </div>
    </section>
  );
}

function DispositionPanel({
  detail,
  onChanged,
}: {
  detail: WorkflowIncidentDetail;
  onChanged: () => void;
}) {
  const [disposition, setDisposition] = useState<IncidentDisposition>(
    detail.incident.disposition ?? "UNREVIEWED",
  );
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const submit = async () => {
    if (!reason.trim()) return;
    try {
      await setIncidentDisposition(
        detail.incident.incident_id,
        disposition,
        reason.trim(),
        detail.incident.version,
      );
      setReason("");
      setMessage("Analyst disposition recorded with rationale.");
      onChanged();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Disposition update failed.");
    }
  };
  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Analyst disposition</h2>
      </div>
      <div className="panel__content">
        <label>
          Disposition
          <select
            value={disposition}
            onChange={(event) => setDisposition(event.target.value as IncidentDisposition)}
          >
            <option>UNREVIEWED</option>
            <option>TRUE_POSITIVE</option>
            <option>FALSE_POSITIVE</option>
          </select>
        </label>
        <label>
          Required analyst rationale
          <textarea
            maxLength={2000}
            required
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <button
          className="button"
          disabled={!reason.trim()}
          type="button"
          onClick={() => void submit()}
        >
          Record disposition
        </button>
        <p className="safety-copy">
          TRUE_POSITIVE confirms the defined synthetic condition was identified. FALSE_POSITIVE
          records analyst interpretation; neither choice deletes or rewrites evidence.
        </p>
        {message ? <p role="status">{message}</p> : null}
      </div>
    </section>
  );
}

function LifecyclePanel({
  detail,
  onChanged,
}: {
  detail: WorkflowIncidentDetail;
  onChanged: () => void;
}) {
  const edges: Record<string, ("OPEN" | "INVESTIGATING" | "RESOLVED")[]> = {
    OPEN: ["INVESTIGATING", "RESOLVED"],
    INVESTIGATING: ["RESOLVED"],
    RESOLVED: ["INVESTIGATING"],
  };
  const options = edges[detail.incident.status] ?? [];
  const [next, setNext] = useState<(typeof options)[number] | "">("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const submit = async () => {
    if (!next) return;
    try {
      await patchIncidentStatus(detail.incident.incident_id, next, detail.incident.version, reason);
      setMessage("Lifecycle status updated.");
      onChanged();
    } catch (error) {
      setMessage(
        error instanceof ApiError && error.status === 409
          ? "The incident changed. Review the refreshed version before resubmitting."
          : error instanceof Error
            ? error.message
            : "Status update failed.",
      );
      if (error instanceof ApiError && error.status === 409) onChanged();
    }
  };
  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Lifecycle action</h2>
      </div>
      <div className="panel__content">
        {options.length ? (
          <>
            <label>
              Approved next status
              <select value={next} onChange={(event) => setNext(event.target.value as typeof next)}>
                <option value="">Select transition</option>
                {options.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
            <label>
              Reason
              {next === "RESOLVED" || detail.incident.status === "RESOLVED"
                ? " (required)"
                : " (optional)"}
              <textarea
                maxLength={500}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
            <button
              className="button"
              disabled={
                !next ||
                ((next === "RESOLVED" || detail.incident.status === "RESOLVED") &&
                  !reason.trim()) ||
                (next === "RESOLVED" &&
                  (detail.incident.disposition ?? "UNREVIEWED") === "UNREVIEWED")
              }
              type="button"
              onClick={() => void submit()}
            >
              Update lifecycle status
            </button>
            {next === "RESOLVED" &&
            (detail.incident.disposition ?? "UNREVIEWED") === "UNREVIEWED" ? (
              <p className="partial-banner">Record an analyst disposition before resolution.</p>
            ) : null}
          </>
        ) : (
          <p>RESOLVED has no approved outgoing transition.</p>
        )}
        {message ? <p role="status">{message}</p> : null}
        <p className="safety-copy">
          No severity, containment, asset, network, or process-control action is available.
        </p>
      </div>
    </section>
  );
}

function NoteForm({
  detail,
  onChanged,
}: {
  detail: WorkflowIncidentDetail;
  onChanged: () => void;
}) {
  const [content, setContent] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const submit = async () => {
    if (!content.trim()) return;
    try {
      await addIncidentNote(detail.incident.incident_id, content, detail.incident.version);
      setContent("");
      setMessage("Analyst note added as plain text.");
      onChanged();
    } catch (error) {
      setMessage(
        error instanceof ApiError && error.status === 409
          ? "The incident changed. Review the refreshed version before resubmitting the note."
          : error instanceof Error
            ? error.message
            : "Note could not be added.",
      );
      if (error instanceof ApiError && error.status === 409) onChanged();
    }
  };
  return (
    <div className="note-form">
      <label>
        Add analyst note
        <textarea
          value={content}
          onChange={(event) => setContent(event.target.value)}
          minLength={1}
          maxLength={2000}
          placeholder="Plain-text investigation context"
        />
      </label>
      <div>
        <span>{content.length} / 2000</span>
        <button
          className="button"
          disabled={!content.trim()}
          type="button"
          onClick={() => void submit()}
        >
          Add analyst note
        </button>
      </div>
      {message ? <p role="status">{message}</p> : null}
    </div>
  );
}

function History({
  title,
  items,
}: {
  title: string;
  items: { id: string; title: string; time: string; note: string }[];
}) {
  return (
    <section className="panel">
      <div className="panel__header">
        <h2>{title}</h2>
      </div>
      <div className="panel__content">
        {items.length ? (
          <ol className="history-list">
            {items.map((item) => (
              <li key={item.id}>
                <strong>{item.title}</strong>
                <span>{formatTimestamp(item.time)}</span>
                <small>{item.note}</small>
              </li>
            ))}
          </ol>
        ) : (
          <p>No history is stored.</p>
        )}
      </div>
    </section>
  );
}

function scenarioFromRule(ruleId: string): "S1" | "S2" | "S3" | "S4" {
  if (ruleId.includes("S4")) return "S4";
  if (ruleId.includes("S3")) return "S3";
  if (ruleId.includes("S2")) return "S2";
  return "S1";
}
