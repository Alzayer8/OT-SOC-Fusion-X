import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import {
  getIncident,
  getIncidents,
  type RunScope,
  type WorkflowIncidentRecord,
} from "../api/client";
import { IncidentWorkspaceTabs } from "../components/IncidentWorkspaceTabs";
import {
  DataTable,
  ExactStatusBadge,
  LoadingSkeleton,
  ProductEmpty,
  ProductError,
  SeverityBadge,
} from "../components/ProductComponents";
import { BarChart, MiniStat, VisualizationPanel } from "../components/Visualizations";
import { useLab } from "../context/LabContext";
import { useApiResource } from "../hooks/useApiResource";
import { formatTimestamp, shortId } from "../utils/presentation";

const STATUSES = ["", "OPEN", "INVESTIGATING", "RESOLVED"];
const SEVERITIES = ["", "LOW", "MEDIUM", "HIGH"];
const DISPOSITIONS = ["", "UNREVIEWED", "TRUE_POSITIVE", "FALSE_POSITIVE"];
const CATEGORIES = [
  "",
  "ASSET_IDENTITY_ANOMALY",
  "COMMUNICATION_POLICY_VIOLATION",
  "CONTROL_COMMAND_INVESTIGATION",
  "PROCESS_INCONSISTENCY",
];

export function IncidentsPage() {
  const { incidentId } = useParams();
  return incidentId ? <IncidentWorkspace incidentId={incidentId} /> : <IncidentListPage />;
}

function IncidentListPage() {
  const lab = useLab();
  const [params, setParams] = useSearchParams();
  const scope: RunScope = params.get("scope") === "HISTORY" ? "HISTORY" : "CURRENT";
  const selectedRunId =
    params.get("run") ?? (scope === "CURRENT" ? lab.activeRun?.run_id : undefined);
  const historicalRunId = scope === "HISTORY" ? params.get("run") : null;
  const queryKey = params.toString();
  const state = useApiResource(
    `incidents:${scope}:${selectedRunId ?? "all"}:${queryKey}`,
    (signal) =>
      getIncidents(
        {
          status: params.get("status") ?? undefined,
          severity: params.get("severity") ?? undefined,
          disposition: params.get("disposition") ?? undefined,
          category: params.get("category") ?? undefined,
          assetId: params.get("asset") ?? undefined,
          cursor: params.get("cursor") ?? undefined,
          runId: selectedRunId,
          scope,
          limit: 50,
        },
        signal,
      ),
  );
  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "cursor") next.delete("cursor");
    setParams(next);
  };
  const setScope = (nextScope: RunScope) => {
    const next = new URLSearchParams(params);
    next.set("scope", nextScope);
    next.delete("cursor");
    next.delete("run");
    setParams(next);
  };
  return (
    <div className="page-stack">
      <header className="product-page-header">
        <div>
          <p className="page-header__eyebrow">Authenticated case management</p>
          <h1>Incidents</h1>
          <p>
            Assignment, triage, disposition, reporting, and evidence-preserving lifecycle review.
          </p>
        </div>
        <div className="page-header__context">
          <span>
            {scope === "CURRENT"
              ? `Current Run · ${lab.activeRun?.scenario_id}`
              : historicalRunId
                ? `Historical Run · ${shortId(historicalRunId)}`
                : "All History"}
          </span>
        </div>
      </header>
      <div className="mode-tabs" role="tablist" aria-label="Incident run scope">
        <button
          aria-selected={scope === "CURRENT"}
          role="tab"
          type="button"
          onClick={() => setScope("CURRENT")}
        >
          Current Run
        </button>
        <button
          aria-selected={scope === "HISTORY"}
          role="tab"
          type="button"
          onClick={() => setScope("HISTORY")}
        >
          {historicalRunId ? "Historical Run" : "All History"}
        </button>
      </div>
      <section className="filter-bar" aria-label="Incident filters">
        <SelectFilter
          label="Status"
          value={params.get("status") ?? ""}
          options={STATUSES}
          empty="All statuses"
          onChange={(value) => setFilter("status", value)}
        />
        <SelectFilter
          label="Severity"
          value={params.get("severity") ?? ""}
          options={SEVERITIES}
          empty="All severities"
          onChange={(value) => setFilter("severity", value)}
        />
        <SelectFilter
          label="Disposition"
          value={params.get("disposition") ?? ""}
          options={DISPOSITIONS}
          empty="All dispositions"
          onChange={(value) => setFilter("disposition", value)}
        />
        <SelectFilter
          label="Category"
          value={params.get("category") ?? ""}
          options={CATEGORIES}
          empty="All categories"
          onChange={(value) => setFilter("category", value)}
        />
        {params.get("asset") ? (
          <span>
            Asset filter: <code>{shortId(params.get("asset") ?? "")}</code>
          </span>
        ) : null}
        {historicalRunId ? (
          <span>
            Exact stored run: <code>{shortId(historicalRunId)}</code>{" "}
            <button type="button" onClick={() => setScope("HISTORY")}>
              View all history
            </button>
          </span>
        ) : null}
      </section>
      {state.status === "loading" ? <LoadingSkeleton label="Loading incident list" /> : null}
      {state.status === "error" ? <ProductError {...state} /> : null}
      {state.status === "success" && state.data.items.length === 0 ? (
        <ProductEmpty
          title={
            scope === "CURRENT" && lab.activeRun?.scenario_id === "BASELINE"
              ? "No current incidents in Baseline"
              : "No incidents match"
          }
          message={
            scope === "CURRENT" && lab.activeRun?.scenario_id === "BASELINE"
              ? "No current incidents exist in the selected Baseline run. Use Scenario Lab for an approved synthetic demonstration or select All History."
              : "No qualified incident matches this exact run and filter selection. Missing incidents do not imply process safety."
          }
        />
      ) : null}
      {state.status === "success" && state.data.items.length ? (
        <>
          <IncidentPageInsights items={state.data.items} />
          <DataTable label="Qualified incidents">
            <thead>
              <tr>
                <th>Incident</th>
                <th>Category</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Disposition</th>
                <th>Assignee</th>
                <th>Affected assets</th>
                <th>Observed</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {state.data.items.map((item) => (
                <tr key={item.incident_id}>
                  <td>
                    <Link
                      className="record-link"
                      to={`/incidents/${item.incident_id}?return_scope=${scope}${historicalRunId ? `&return_run=${encodeURIComponent(historicalRunId)}` : ""}`}
                    >
                      <strong>{item.title}</strong>
                      <span className="mono">{shortId(item.incident_id)}</span>
                    </Link>
                  </td>
                  <td>{item.category.replaceAll("_", " ")}</td>
                  <td>
                    <SeverityBadge severity={item.severity} />
                  </td>
                  <td>
                    <ExactStatusBadge value={item.status} />
                  </td>
                  <td>
                    <ExactStatusBadge value={item.disposition ?? "UNREVIEWED"} />
                  </td>
                  <td>{item.assignee_display_name ?? "Unassigned"}</td>
                  <td>{item.process_asset_keys.join(", ") || "Unavailable"}</td>
                  <td>
                    <small>First {formatTimestamp(item.first_observed_at)}</small>
                    <small>Last {formatTimestamp(item.last_observed_at)}</small>
                  </td>
                  <td>{item.evidence_count}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
          <div className="pagination">
            <span>Showing this deterministic page · limit {state.data.limit}</span>
            {state.data.next_cursor ? (
              <button
                className="button compact"
                type="button"
                onClick={() => setFilter("cursor", state.data.next_cursor ?? "")}
              >
                Next page
              </button>
            ) : (
              <span>End of results</span>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}

function SelectFilter({
  label,
  value,
  options,
  empty,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  empty: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((item) => (
          <option key={item || "all"} value={item}>
            {item ? item.replaceAll("_", " ") : empty}
          </option>
        ))}
      </select>
    </label>
  );
}

function IncidentPageInsights({ items }: { items: WorkflowIncidentRecord[] }) {
  const severity = [
    {
      label: "High",
      value: items.filter((item) => item.severity === "HIGH").length,
      tone: "red" as const,
    },
    {
      label: "Medium",
      value: items.filter((item) => item.severity === "MEDIUM").length,
      tone: "amber" as const,
    },
    {
      label: "Low",
      value: items.filter((item) => item.severity === "LOW").length,
      tone: "green" as const,
    },
  ];
  return (
    <section className="incident-list-insights" aria-label="Visible incident page summary">
      <div className="mini-stat-grid">
        <MiniStat
          label="Visible Records"
          value={items.length}
          note="Current bounded page"
          tone="blue"
        />
        <MiniStat
          label="Open"
          value={items.filter((item) => item.status === "OPEN").length}
          note="Visible page only"
          tone="amber"
        />
        <MiniStat
          label="Unreviewed"
          value={items.filter((item) => (item.disposition ?? "UNREVIEWED") === "UNREVIEWED").length}
          note="Awaiting analyst disposition"
          tone="purple"
        />
        <MiniStat
          label="Unassigned"
          value={items.filter((item) => !item.assignee_user_id).length}
          note="No local owner"
          tone="cyan"
        />
      </div>
      <VisualizationPanel title="Visible Severity Profile" eyebrow="Current bounded page">
        <BarChart title="Visible incident severity profile" data={severity} />
      </VisualizationPanel>
    </section>
  );
}

function IncidentWorkspace({ incidentId }: { incidentId: string }) {
  const [params] = useSearchParams();
  const returnRun = params.get("return_run");
  const [revision, setRevision] = useState(0);
  const state = useApiResource(`incident:${incidentId}:${revision}`, (signal) =>
    getIncident(incidentId, signal),
  );
  return (
    <div className="page-stack">
      <header className="product-page-header">
        <div>
          <p className="page-header__eyebrow">Authenticated incident workspace</p>
          <h1>Investigation</h1>
          <p>Evidence, timeline, analyst triage, disposition, reporting, and audit.</p>
        </div>
        <Link
          className="button button--link"
          to={
            params.get("return_scope") === "HISTORY"
              ? `/incidents?scope=HISTORY${returnRun ? `&run=${encodeURIComponent(returnRun)}` : ""}`
              : "/incidents?scope=CURRENT"
          }
        >
          Back to incidents
        </Link>
      </header>
      {state.status === "loading" ? <LoadingSkeleton label="Loading incident workspace" /> : null}
      {state.status === "error" ? <ProductError {...state} /> : null}
      {state.status === "success" ? (
        <IncidentWorkspaceTabs
          detail={state.data}
          onChanged={() => setRevision((value) => value + 1)}
        />
      ) : null}
    </div>
  );
}
