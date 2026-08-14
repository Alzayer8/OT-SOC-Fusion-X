import { Link, useSearchParams } from "react-router-dom";

import {
  getOverview,
  getReplayForCorrelation,
  getReplayForIncident,
  type ReplayBundle,
  type ReplayEvent,
} from "../api/client";
import { Icon } from "../components/Icons";
import {
  EvidenceCard,
  ExactStatusBadge,
  LoadingSkeleton,
  ProductError,
  SafetyBanner,
} from "../components/ProductComponents";
import { ProcessSchematic } from "../components/ProcessSchematic";
import { useApiResource } from "../hooks/useApiResource";
import { useLab } from "../context/LabContext";
import { evidenceByType, recordAtOrBefore, valveCommandAtOrBefore } from "../utils/evidence";
import { asRecord, displayValue, formatTimestamp, numeric } from "../utils/presentation";
import {
  EmptyVisualization,
  TrendChart,
  VisualizationPanel,
  type TrendSeries,
} from "../components/Visualizations";

export function DigitalTwinPage() {
  const lab = useLab();
  const [params] = useSearchParams();
  const incidentId = params.get("incident");
  const correlationId = params.get("correlation");
  const state = useApiResource(
    `twin:${incidentId ?? correlationId ?? lab.activeRun?.run_id ?? "active"}`,
    async (signal) => {
      if (incidentId)
        return { mode: "bundle" as const, bundle: await getReplayForIncident(incidentId, signal) };
      if (correlationId)
        return {
          mode: "bundle" as const,
          bundle: await getReplayForCorrelation(correlationId, signal),
        };
      return { mode: "latest" as const, overview: await getOverview(signal) };
    },
  );
  return (
    <div className="page-stack">
      <header className="product-page-header">
        <div>
          <p className="page-header__eyebrow">Read-only process investigation</p>
          <h1>Digital Twin</h1>
          <p>
            Stored command, observed equipment state, and process effect shown as separate evidence
            layers.
          </p>
        </div>
        <div className="page-header__context">
          <Icon name="twin" />
          <span>
            {incidentId || correlationId
              ? "Historical Replay"
              : lab.activeRun?.scenario_id === "BASELINE"
                ? "Baseline"
                : "Current Scenario"}{" "}
            · read-only
          </span>
        </div>
      </header>
      <SafetyBanner />
      {state.status === "loading" ? <LoadingSkeleton label="Loading Digital Twin" /> : null}
      {state.status === "error" ? <ProductError {...state} /> : null}
      {state.status === "success" ? (
        state.data.mode === "latest" ? (
          <>
            <ProcessSchematic
              telemetry={state.data.overview.process_snapshot}
              valveCommand={state.data.overview.linked_valve_command}
            />
            <div className="status-row" aria-label="Digital Twin run context">
              <ExactStatusBadge value={lab.activeRun?.scenario_id ?? "BASELINE"} />
              <span>{lab.activeRun?.scenario_title ?? "Baseline"} active-run snapshot</span>
            </div>
            <VisualizationPanel
              title="Stored Process Trends"
              eyebrow="Same-run evidence requirement"
            >
              <EmptyVisualization message="The latest Overview projection contains one coherent snapshot; compatible trend history is unavailable in this context." />
            </VisualizationPanel>
          </>
        ) : (
          <TwinBundle bundle={state.data.bundle} context="HISTORICAL" />
        )
      ) : null}
      <p className="safety-copy">
        No process control is available. This page cannot start/stop P-101, change CV-101, alter
        simulation state, or transmit a protocol message.
      </p>
    </div>
  );
}

function TwinBundle({
  bundle,
  context,
}: {
  bundle: ReplayBundle;
  context: "BASELINE" | "CURRENT SCENARIO" | "HISTORICAL";
}) {
  const cursor = bundle.events.length - 1;
  const telemetry = recordAtOrBefore(bundle.events, cursor, "simulator_telemetry");
  const command = valveCommandAtOrBefore(bundle.events, cursor);
  const correlation = evidenceByType(bundle.events, "correlation_finding");
  const policy = evidenceByType(bundle.events, "communication_policy_finding");
  const correlationPayload = correlation ? asRecord(correlation.payload) : {};
  const policyPayload = policy ? asRecord(policy.payload) : {};
  return (
    <>
      <div className="status-row">
        <ExactStatusBadge value={context} />
        <ExactStatusBadge value={bundle.completeness} />
        {bundle.incident ? (
          <ExactStatusBadge value={`${bundle.incident.severity} INCIDENT`} />
        ) : null}
      </div>
      {bundle.gaps.length ? (
        <div className="partial-banner">
          {bundle.gaps.join(" ")} Missing evidence does not imply safety.
        </div>
      ) : null}
      <ProcessSchematic
        telemetry={telemetry}
        valveCommand={command}
        incidentSeverity={bundle.incident?.severity}
        historical={context === "HISTORICAL"}
      />
      <TwinTrends events={bundle.events} />
      <section className="panel correlation-overlay">
        <div className="panel__header">
          <h2>Cyber-physical investigation overlay</h2>
        </div>
        <div className="panel__content">
          <div className="overlay-flow">
            <OverlayNode
              label="Protocol Event"
              value={command ? "Verified CV-101 command evidence" : "Unavailable"}
            />
            <span>→</span>
            <OverlayNode
              label="Policy Status"
              value={displayValue(policyPayload.policy_status, "UNAVAILABLE")}
            />
            <span>→</span>
            <OverlayNode
              label="Process Asset"
              value={bundle.incident?.process_asset_keys.join(", ") ?? "Stored correlation context"}
            />
            <span>→</span>
            <OverlayNode
              label="Observed Process Change"
              value={telemetry ? "Typed telemetry observations" : "Unavailable"}
            />
            <span>→</span>
            <OverlayNode
              label="Correlation Status"
              value={displayValue(correlationPayload.correlation_status, "UNAVAILABLE")}
            />
          </div>
          <p>
            {correlationPayload.correlation_status === "CORRELATED"
              ? "Temporally Correlated under the configured synthetic rule; cause and malicious intent are not determined."
              : "Correlation context is unavailable or did not match the configured rule."}
          </p>
          {correlation ? (
            <EvidenceCard record={correlation} title="Correlation evidence and provenance" />
          ) : null}
          {bundle.incident ? (
            <Link to={`/replay?incident=${bundle.incident.incident_id}`}>Open bounded Replay</Link>
          ) : null}
        </div>
      </section>
    </>
  );
}

function TwinTrends({ events }: { events: ReplayEvent[] }) {
  const telemetry = events.flatMap((event, eventIndex) => {
    if (event.evidence?.evidence_type !== "simulator_telemetry") return [];
    return [{ event, eventIndex, payload: asRecord(event.evidence.payload) }];
  });
  const build = (
    label: string,
    field: string,
    tone: TrendSeries["tone"],
    unit: string,
  ): TrendSeries => ({
    label,
    tone,
    unit,
    points: telemetry.flatMap(({ event, eventIndex, payload }) => {
      const value = numeric(payload[field]);
      return value === null
        ? []
        : [{ x: eventIndex, label: formatTimestamp(event.observed_at), value }];
    }),
  });
  return (
    <section className="twin-trend-grid" aria-label="Same-run stored telemetry trends">
      <VisualizationPanel title="Flow & Pressure Trend" eyebrow="Verified same-run telemetry">
        <TrendChart
          title="Flow and pressure stored telemetry trend"
          series={[
            build("Pipeline flow", "pipeline_flow_rate_m3h", "cyan", "synthetic m³/h"),
            build("Pipeline pressure", "pipeline_pressure_bar", "purple", "synthetic bar"),
          ]}
        />
      </VisualizationPanel>
      <VisualizationPanel title="Tank & Valve Trend" eyebrow="Verified same-run telemetry">
        <TrendChart
          title="Tank levels and observed valve position trend"
          series={[
            build("TK-101 level", "source_tank_level_percent", "blue", "%"),
            build("TK-102 level", "receiving_tank_level_percent", "green", "%"),
            build("CV-101 observed", "control_valve_position_percent", "amber", "% open"),
          ]}
        />
      </VisualizationPanel>
    </section>
  );
}

function OverlayNode({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}
