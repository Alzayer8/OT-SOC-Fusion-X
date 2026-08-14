import { Link, useSearchParams } from "react-router-dom";

import {
  ApiError,
  getIncidentReport,
  getIncidents,
  type IncidentReport,
  type RunScope,
  type WorkflowIncidentRecord,
} from "../api/client";
import { Icon } from "../components/Icons";
import {
  DataTable,
  ExactStatusBadge,
  KpiCard,
  LoadingSkeleton,
  ProductEmpty,
  ProductError,
  SafetyBanner,
} from "../components/ProductComponents";
import { BarChart, DonutChart, VisualizationPanel } from "../components/Visualizations";
import { useLab } from "../context/LabContext";
import { useApiResource } from "../hooks/useApiResource";
import { formatTimestamp, shortId } from "../utils/presentation";

interface ReportRow {
  incident: WorkflowIncidentRecord;
  report: IncidentReport | null;
}

interface ReportData {
  scope: RunScope;
  runId: string | null;
  items: WorkflowIncidentRecord[];
  rows: ReportRow[];
  truncated: boolean;
}

export function ReportsPage() {
  const lab = useLab();
  const [params, setParams] = useSearchParams();
  const scope: RunScope = params.get("scope") === "HISTORY" ? "HISTORY" : "CURRENT";
  const runId = scope === "CURRENT" ? lab.activeRun?.run_id : undefined;
  const state = useApiResource(`reports:${scope}:${runId ?? "all"}`, async (signal) => {
    const incidents = await getIncidents({ scope, limit: 100 }, signal);
    const rows = await Promise.all(
      incidents.items.map(async (incident): Promise<ReportRow> => {
        try {
          return { incident, report: await getIncidentReport(incident.incident_id, signal) };
        } catch (error) {
          if (error instanceof ApiError && error.status === 404) return { incident, report: null };
          throw error;
        }
      }),
    );
    return {
      scope,
      runId: runId ?? null,
      items: incidents.items,
      rows,
      truncated: incidents.next_cursor !== null,
    } satisfies ReportData;
  });
  const selectScope = (next: RunScope) => setParams({ scope: next });

  return (
    <div className="page-stack">
      <header className="product-page-header">
        <div>
          <p className="page-header__eyebrow">Authenticated SOC reporting</p>
          <h1>Reports</h1>
          <p>Bounded run-aware incident analytics and stored analyst investigation reports.</p>
        </div>
        <div className="page-header__context">
          <Icon name="reports" />
          <span>
            {scope === "CURRENT" ? `Current Run · ${lab.activeRun?.scenario_id}` : "All History"} ·
            browser print
          </span>
        </div>
      </header>
      <SafetyBanner />
      <div className="mode-tabs" role="tablist" aria-label="Report run scope">
        <button
          aria-selected={scope === "CURRENT"}
          role="tab"
          type="button"
          onClick={() => selectScope("CURRENT")}
        >
          Current Run
        </button>
        <button
          aria-selected={scope === "HISTORY"}
          role="tab"
          type="button"
          onClick={() => selectScope("HISTORY")}
        >
          All History
        </button>
      </div>
      {state.status === "loading" ? <LoadingSkeleton label="Loading report data" /> : null}
      {state.status === "error" ? <ProductError {...state} /> : null}
      {state.status === "success" ? <ReportsContent data={state.data} /> : null}
    </div>
  );
}

function ReportsContent({ data }: { data: ReportData }) {
  const high = data.items.filter((item) => item.severity === "HIGH").length;
  const completedDispositions = data.items.filter(
    (item) => item.disposition && item.disposition !== "UNREVIEWED",
  ).length;
  const savedReports = data.rows.filter((row) => (row.report?.version ?? 0) > 0).length;
  return (
    <>
      {data.truncated ? (
        <p className="partial-banner">
          Analytics are limited to the first 100 incidents in this selected scope. No global total
          is inferred.
        </p>
      ) : null}
      <section className="kpi-grid">
        <KpiCard
          icon="incidents"
          label="Bounded Incidents"
          value={data.items.length}
          note="At most 100 records"
          tone="info"
        />
        <KpiCard
          icon="shield"
          label="HIGH"
          value={high}
          note="Exact within bounded response"
          tone="critical"
        />
        <KpiCard
          icon="reports"
          label="Completed Dispositions"
          value={completedDispositions}
          note="Authenticated analyst decisions"
          tone="warning"
        />
        <KpiCard
          icon="reports"
          label="Saved Reports"
          value={savedReports}
          note="Stored report version above zero"
          tone="info"
        />
      </section>
      <ReportVisuals data={data} />
      <section className="panel">
        <div className="panel__header">
          <h2>Incident Reports</h2>
        </div>
        <div className="panel__content">
          {data.rows.length ? (
            <DataTable label="Stored incident reports">
              <thead>
                <tr>
                  <th>Incident</th>
                  <th>Status</th>
                  <th>Disposition</th>
                  <th>Assignee</th>
                  <th>Report Author</th>
                  <th>Last Updated</th>
                  <th>Completeness</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map(({ incident, report }) => (
                  <tr key={incident.incident_id}>
                    <td>
                      <strong>{incident.title}</strong>
                      <small className="mono">{incident.incident_id}</small>
                    </td>
                    <td>
                      <ExactStatusBadge value={incident.status} />
                    </td>
                    <td>
                      <ExactStatusBadge value={incident.disposition ?? "UNREVIEWED"} />
                    </td>
                    <td>{incident.assignee_display_name ?? "Unassigned"}</td>
                    <td>
                      {report?.updated_by_user_id
                        ? `Local user ${shortId(report.updated_by_user_id)}`
                        : "No report author"}
                    </td>
                    <td>{report?.updated_at ? formatTimestamp(report.updated_at) : "Not saved"}</td>
                    <td>{report?.fields_filled ?? 0} of 7 fields</td>
                    <td>
                      <Link
                        className="button button--link compact"
                        to={`/incidents/${incident.incident_id}?tab=report`}
                      >
                        Open / Edit / Print
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          ) : (
            <ProductEmpty
              title="No analyst dispositions or reports in this scope"
              message="No report row can be constructed until a qualified incident exists in this selected run context."
            />
          )}
        </div>
      </section>
    </>
  );
}

function ReportVisuals({ data }: { data: ReportData }) {
  const count = (predicate: (item: WorkflowIncidentRecord) => boolean) =>
    data.items.filter(predicate).length;
  const affected = new Map<string, number>();
  for (const incident of data.items)
    for (const asset of incident.process_asset_keys)
      affected.set(asset, (affected.get(asset) ?? 0) + 1);
  return (
    <section className="report-chart-grid" aria-label="Bounded report visualizations">
      <VisualizationPanel
        title="Disposition Distribution"
        eyebrow="Authenticated analyst decisions"
      >
        <DonutChart
          title="Analyst disposition distribution"
          centerLabel="incidents"
          data={[
            {
              label: "Unreviewed",
              value: count((item) => (item.disposition ?? "UNREVIEWED") === "UNREVIEWED"),
              tone: "slate",
            },
            {
              label: "True Positive",
              value: count((item) => item.disposition === "TRUE_POSITIVE"),
              tone: "cyan",
            },
            {
              label: "False Positive",
              value: count((item) => item.disposition === "FALSE_POSITIVE"),
              tone: "purple",
            },
          ]}
        />
      </VisualizationPanel>
      <VisualizationPanel title="Severity Distribution" eyebrow="Bounded selected scope">
        <DonutChart
          title="Report incident severity distribution"
          centerLabel="incidents"
          data={[
            { label: "High", value: count((item) => item.severity === "HIGH"), tone: "red" },
            {
              label: "Medium",
              value: count((item) => item.severity === "MEDIUM"),
              tone: "amber",
            },
            { label: "Low", value: count((item) => item.severity === "LOW"), tone: "green" },
          ]}
        />
      </VisualizationPanel>
      <VisualizationPanel title="Status Distribution" eyebrow="Bounded selected scope">
        <DonutChart
          title="Report incident status distribution"
          centerLabel="incidents"
          data={[
            { label: "Open", value: count((item) => item.status === "OPEN"), tone: "amber" },
            {
              label: "Investigating",
              value: count((item) => item.status === "INVESTIGATING"),
              tone: "blue",
            },
            {
              label: "Resolved",
              value: count((item) => item.status === "RESOLVED"),
              tone: "green",
            },
          ]}
        />
      </VisualizationPanel>
      <VisualizationPanel title="Category Distribution" eyebrow="Bounded selected scope">
        <BarChart
          title="Report incident category distribution"
          data={[
            {
              label: "Asset identity",
              value: count((item) => item.category === "ASSET_IDENTITY_ANOMALY"),
              tone: "purple",
            },
            {
              label: "Communication policy",
              value: count((item) => item.category === "COMMUNICATION_POLICY_VIOLATION"),
              tone: "amber",
            },
            {
              label: "Control command",
              value: count((item) => item.category === "CONTROL_COMMAND_INVESTIGATION"),
              tone: "red",
            },
            {
              label: "Process inconsistency",
              value: count((item) => item.category === "PROCESS_INCONSISTENCY"),
              tone: "cyan",
            },
          ]}
        />
      </VisualizationPanel>
      <VisualizationPanel title="Affected Asset Summary" eyebrow="Bounded incident response">
        <BarChart
          title="Affected process assets"
          data={[...affected.entries()]
            .sort(([left], [right]) => left.localeCompare(right))
            .map(([label, value], index) => ({
              label,
              value,
              tone: (["cyan", "blue", "purple", "green", "amber"] as const)[index % 5],
            }))}
        />
      </VisualizationPanel>
      <VisualizationPanel title="Scenario Run Summary" eyebrow="Exact selected context">
        <dl className="detail-grid">
          <div>
            <dt>Scope</dt>
            <dd>{data.scope === "CURRENT" ? "CURRENT" : "ALL_HISTORY"}</dd>
          </div>
          <div>
            <dt>Run ID</dt>
            <dd className="mono">{data.runId ?? "All historical runs"}</dd>
          </div>
          <div>
            <dt>Bounded report rows</dt>
            <dd>{data.rows.length}</dd>
          </div>
          <div>
            <dt>Analytic boundary</dt>
            <dd>At most 100 incident records</dd>
          </div>
        </dl>
      </VisualizationPanel>
    </section>
  );
}
