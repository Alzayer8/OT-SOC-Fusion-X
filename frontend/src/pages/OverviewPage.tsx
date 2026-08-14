import { Link } from "react-router-dom";

import { getOverview, type LabRun } from "../api/client";
import { Icon } from "../components/Icons";
import {
  KpiCard,
  LoadingSkeleton,
  ProductError,
  ProductEmpty,
  SafetyBanner,
} from "../components/ProductComponents";
import { ProcessSchematic } from "../components/ProcessSchematic";
import { BarChart, DonutChart, VisualizationPanel } from "../components/Visualizations";
import { useApiResource } from "../hooks/useApiResource";
import { useLab } from "../context/LabContext";
import { formatTimestamp } from "../utils/presentation";

export function OverviewPage() {
  const lab = useLab();
  const activeRun = lab.activeRun!;
  const state = useApiResource(`overview:${activeRun.run_id}`, getOverview);
  return (
    <div className="page-stack overview-page">
      <header className="product-page-header">
        <div>
          <p className="page-header__eyebrow">Operational investigation summary</p>
          <h1>Overview</h1>
          <p>Current-run synthetic evidence, qualified incidents, and coherent process context.</p>
        </div>
        <div className="page-header__context">
          <Icon name="clock" />
          <span>
            Current Run · {activeRun.scenario_id} · {activeRun.status}
          </span>
        </div>
      </header>
      <SafetyBanner />
      {state.status === "loading" ? <LoadingSkeleton label="Loading overview data" /> : null}
      {state.status === "error" ? <ProductError {...state} /> : null}
      {state.status === "success" ? (
        <OverviewContent activeRun={activeRun} data={state.data} />
      ) : null}
    </div>
  );
}

function OverviewContent({
  activeRun,
  data,
}: {
  activeRun: LabRun;
  data: Awaited<ReturnType<typeof getOverview>>;
}) {
  const empty =
    data.incidents.total === 0 &&
    data.policy_findings.denied === 0 &&
    data.correlations.correlated === 0;
  const statusData = [
    { label: "Open", value: data.incidents.open, tone: "amber" as const },
    { label: "Investigating", value: data.incidents.investigating, tone: "blue" as const },
    { label: "Resolved", value: data.incidents.resolved, tone: "green" as const },
  ];
  const severityData = [
    { label: "High", value: data.incidents.high, tone: "red" as const },
    { label: "Medium", value: data.incidents.medium, tone: "amber" as const },
    { label: "Low", value: data.incidents.low, tone: "green" as const },
  ];
  const categoryData = [
    {
      label: "Asset identity",
      value: data.incidents.categories.asset_identity_anomaly,
      tone: "purple" as const,
    },
    {
      label: "Communication policy",
      value: data.incidents.categories.communication_policy_violation,
      tone: "amber" as const,
    },
    {
      label: "Control command",
      value: data.incidents.categories.control_command_investigation,
      tone: "red" as const,
    },
    {
      label: "Process inconsistency",
      value: data.incidents.categories.process_inconsistency,
      tone: "cyan" as const,
    },
  ];
  return (
    <>
      <section className="kpi-grid" aria-label="Operational key indicators">
        <KpiCard
          icon="incidents"
          label="Open Incidents"
          value={data.incidents.open}
          note={`Current ${activeRun.scenario_id} run`}
          to="/incidents?scope=CURRENT&status=OPEN"
          tone="warning"
        />
        <KpiCard
          icon="shield"
          label="High Severity"
          value={data.incidents.high_non_resolved}
          note={`HIGH and not RESOLVED · ${activeRun.scenario_id}`}
          to="/incidents?scope=CURRENT&severity=HIGH"
          tone="critical"
        />
        <KpiCard
          icon="protocol"
          label="Denied Policy Findings"
          value={data.policy_findings.denied}
          note={`${data.policy_findings.total} total classified in current run`}
          to="/protocol-analysis?type=communication_policy_finding"
          tone="warning"
        />
        <KpiCard
          icon="link"
          label="Temporally Correlated"
          value={data.correlations.correlated}
          note="Configured process deviations"
          to="/protocol-analysis?type=correlation_finding"
          tone="info"
        />
        <KpiCard
          icon="assets"
          label="Synthetic Assets"
          value={data.assets.total}
          note={`${data.assets.cyber} cyber · ${data.assets.process} process`}
          to="/assets"
          tone="success"
        />
        <KpiCard
          icon="database"
          label="Evidence Window"
          value="RUN"
          note={`${activeRun.scenario_id} · as of ${formatTimestamp(data.as_of)}`}
          tone="info"
        />
      </section>
      {empty ? (
        <ProductEmpty
          title={
            activeRun.scenario_id === "BASELINE"
              ? "Baseline has no current incidents"
              : "No current-run activity"
          }
          message={
            activeRun.scenario_id === "BASELINE"
              ? "No current incidents exist in the selected Baseline run. Normal stored process context remains available below."
              : "No qualified incident, policy, or correlation record exists in this exact run. Missing evidence does not imply safety."
          }
        />
      ) : null}
      <section className="overview-analysis-grid" aria-label="Sourced incident visualizations">
        <VisualizationPanel title="Incident Severity" eyebrow="Exact enum distribution">
          <DonutChart
            title="Incident severity distribution"
            data={severityData}
            centerLabel="incidents"
          />
        </VisualizationPanel>
        <VisualizationPanel title="Investigation Status" eyebrow="Current aggregate">
          <DonutChart
            title="Incident status distribution"
            data={statusData}
            centerLabel="incidents"
          />
        </VisualizationPanel>
        <VisualizationPanel
          title="Incident Category"
          eyebrow="Qualified investigations"
          className="visual-panel--wide"
        >
          <BarChart title="Incident category distribution" data={categoryData} />
        </VisualizationPanel>
        <VisualizationPanel
          title="Cyber-Physical Investigation"
          eyebrow="Verified lineage · not causation"
          className="visual-panel--lineage"
        >
          <div
            className="investigation-lineage"
            aria-label="Protocol evidence to incident investigation lineage"
          >
            {[
              [
                "01",
                "Protocol Evidence",
                `${data.policy_findings.total} policy-classified findings`,
              ],
              [
                "02",
                "Asset / Policy Context",
                `${data.policy_findings.denied} DENIED · not a maliciousness claim`,
              ],
              ["03", "Correlation", `${data.correlations.correlated} Temporally Correlated`],
              ["04", "Process Context", data.process_snapshot_status],
              ["05", "Incident", `${data.incidents.total} qualified records`],
            ].map(([marker, label, value], index) => (
              <div className="investigation-lineage__step" key={label}>
                <span>{marker}</span>
                <div>
                  <strong>{label}</strong>
                  <small>{value}</small>
                </div>
                {index < 4 ? <i aria-hidden="true" /> : null}
              </div>
            ))}
          </div>
          <p className="causality-note">
            Temporal correlation organizes investigation context; it does not establish cause or
            malicious intent.
          </p>
        </VisualizationPanel>
      </section>
      <ProcessSchematic
        telemetry={data.process_snapshot}
        valveCommand={data.linked_valve_command}
      />
      <section className="overview-lower-grid">
        <section className="panel recent-activity">
          <div className="panel__header">
            <div>
              <span className="section-kicker">
                <Icon name="activity" /> Bounded activity
              </span>
              <h2>Recent verified incident activity</h2>
            </div>
          </div>
          <div className="panel__content">
            {data.recent_activity.length === 0 ? (
              <p>No incident timeline activity is stored.</p>
            ) : (
              <ol className="activity-list">
                {data.recent_activity.map((item) => (
                  <li key={item.activity_id}>
                    <time>{formatTimestamp(item.observed_at)}</time>
                    <strong>{item.entry_type.replaceAll("_", " ")}</strong>
                    <p>{item.summary}</p>
                    <Link to={`/incidents/${item.incident_id}`}>
                      Open incident <span aria-hidden="true">→</span>
                    </Link>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>
        <aside className="panel evidence-window-card" aria-label="Evidence window integrity">
          <div className="panel__header">
            <h2>Evidence Window</h2>
          </div>
          <div className="panel__content">
            <span className="window-status">
              <i aria-hidden="true" />
              Complete server aggregate
            </span>
            <dl>
              <div>
                <dt>Start</dt>
                <dd>{formatTimestamp(data.window_start)}</dd>
              </div>
              <div>
                <dt>End</dt>
                <dd>{formatTimestamp(data.window_end)}</dd>
              </div>
              <div>
                <dt>Process snapshot</dt>
                <dd>{data.process_snapshot_status}</dd>
              </div>
            </dl>
            <p>{data.process_snapshot_message}</p>
          </div>
        </aside>
      </section>
    </>
  );
}
