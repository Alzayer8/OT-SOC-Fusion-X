import type { EvidenceRecord } from "../api/client";
import {
  asRecord,
  displayValue,
  formatMetric,
  formatTimestamp,
  numeric,
  textual,
} from "../utils/presentation";
import { Icon } from "./Icons";
import { ExactStatusBadge } from "./ProductComponents";

interface ProcessSchematicProps {
  telemetry?: EvidenceRecord | null;
  valveCommand?: EvidenceRecord | null;
  incidentSeverity?: string | null;
  historical?: boolean;
  title?: string;
}

function commandValue(record?: EvidenceRecord | null): string {
  if (!record) return "Unavailable";
  const payload = asRecord(record.payload);
  const pointId = textual(payload.point_id);
  return pointId === "control_valve_command_percent"
    ? formatMetric(payload.decoded_value, "% open")
    : "Unavailable";
}

function percent(value: unknown): number | null {
  const parsed = numeric(value);
  return parsed === null ? null : Math.min(100, Math.max(0, parsed));
}

export function ProcessSchematic({
  telemetry,
  valveCommand,
  incidentSeverity,
  historical = false,
  title = "Synthetic Oil & Gas transfer path",
}: ProcessSchematicProps) {
  const payload = telemetry ? asRecord(telemetry.payload) : {};
  const observedAt = telemetry?.observed_at;
  const running =
    typeof payload.transfer_pump_running === "boolean" ? payload.transfer_pump_running : null;
  const flow = numeric(payload.pipeline_flow_rate_m3h);
  const state = telemetry ? (historical ? "HISTORICAL" : "STORED OBSERVATION") : "UNAVAILABLE";
  const sourceLevel = percent(payload.source_tank_level_percent);
  const receivingLevel = percent(payload.receiving_tank_level_percent);
  const valvePosition = percent(payload.control_valve_position_percent);
  const activeFlow = flow !== null && flow > 0;

  return (
    <section className="process-panel" aria-labelledby="process-title">
      <div className="process-panel__header">
        <div>
          <span className="section-kicker">
            <Icon name="twin" /> Read-only process canvas
          </span>
          <h2 id="process-title">{title}</h2>
          <p>One coherent typed evidence context · no process control</p>
        </div>
        <div className="status-row">
          {incidentSeverity ? <ExactStatusBadge value={`${incidentSeverity} INCIDENT`} /> : null}
          <ExactStatusBadge value={state} />
        </div>
      </div>
      <div className="process-canvas" aria-label="TK-101 to P-101 to PL-101 to CV-101 to TK-102">
        <ProcessNode
          kind="tank"
          keyName="TK-101"
          label="Source Tank"
          metric={formatMetric(payload.source_tank_level_percent, "% level")}
          fill={sourceLevel}
        />
        <ProcessConnector active={activeFlow} label="Suction" />
        <ProcessNode
          active={running === true}
          kind="pump"
          keyName="P-101"
          label="Transfer Pump"
          metric={running === null ? "State unavailable" : running ? "RUNNING" : "STOPPED"}
        />
        <ProcessConnector active={activeFlow} label="Discharge" />
        <ProcessNode
          active={activeFlow}
          kind="pipeline"
          keyName="PL-101"
          label="Pipeline"
          metric={formatMetric(payload.pipeline_flow_rate_m3h, "synthetic m³/h", 2)}
        />
        <ProcessConnector active={activeFlow} label="Flow" />
        <ProcessNode
          active={valvePosition !== null && valvePosition > 0}
          kind="valve"
          keyName="CV-101"
          label="Control Valve"
          metric={formatMetric(payload.control_valve_position_percent, "% observed open")}
        />
        <ProcessConnector active={activeFlow} label="Transfer" />
        <ProcessNode
          kind="tank"
          keyName="TK-102"
          label="Receiving Tank"
          metric={formatMetric(payload.receiving_tank_level_percent, "% level")}
          fill={receivingLevel}
        />
      </div>
      <div
        className="command-state-effect"
        aria-label="Command, observed state, and process effect"
      >
        <MetricGroup title="Command" marker="01">
          <Metric
            label="P-101 Pump Command"
            value={formatMetric(payload.transfer_pump_command_percent, "%")}
          />
          <Metric label="CV-101 Valve Command" value={commandValue(valveCommand)} />
        </MetricGroup>
        <MetricGroup title="Observed Equipment State" marker="02">
          <Metric
            label="P-101 Pump Running State"
            value={running === null ? "Unavailable" : running ? "RUNNING" : "STOPPED"}
          />
          <Metric
            label="CV-101 Observed Valve Position"
            value={formatMetric(payload.control_valve_position_percent, "% open")}
          />
        </MetricGroup>
        <MetricGroup title="Observed Process Effect" marker="03">
          <Metric
            label="Pipeline Flow"
            value={formatMetric(payload.pipeline_flow_rate_m3h, "synthetic m³/h", 2)}
          />
          <Metric
            label="Pipeline Pressure"
            value={formatMetric(payload.pipeline_pressure_bar, "synthetic bar", 3)}
          />
          <Metric
            label="Process Temperature"
            value={formatMetric(payload.process_temperature_c, "°C")}
          />
        </MetricGroup>
      </div>
      <p className="process-provenance">
        <Icon name="evidence" />
        {telemetry && observedAt
          ? `Stored evidence · ${textual(payload.simulation_id) ?? "run unavailable"} · sequence ${displayValue(payload.sequence_number, "unavailable")} · ${formatTimestamp(observedAt)}`
          : "Process telemetry is unavailable for this evidence window."}
      </p>
    </section>
  );
}

function ProcessNode({
  keyName,
  label,
  metric,
  kind,
  active = false,
  fill,
}: {
  keyName: string;
  label: string;
  metric: string;
  kind: "tank" | "pump" | "pipeline" | "valve";
  active?: boolean;
  fill?: number | null;
}) {
  return (
    <div
      className={`process-node process-node--${kind}${active ? " process-node--active" : ""}`}
      tabIndex={0}
      aria-label={`${keyName}, ${label}, ${metric}`}
    >
      <span className="process-node__tag">{keyName}</span>
      <span className="process-node__graphic" aria-hidden="true">
        {kind === "tank" && fill !== null && fill !== undefined ? (
          <span className="process-node__liquid" style={{ height: `${fill}%` }} />
        ) : null}
        {kind === "pump" ? <span className="process-node__rotor" /> : null}
        {kind === "pipeline" ? <span className="process-node__pipe" /> : null}
        {kind === "valve" ? <span className="process-node__valve" /> : null}
      </span>
      <strong>{label}</strong>
      <small>{metric}</small>
    </div>
  );
}

function ProcessConnector({ active, label }: { active: boolean; label: string }) {
  return (
    <span
      className={`process-connector${active ? " process-connector--active" : ""}`}
      aria-hidden="true"
    >
      <small>{label}</small>
      <i />
    </span>
  );
}

function MetricGroup({
  title,
  marker,
  children,
}: {
  title: string;
  marker: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3>
        <span>{marker}</span>
        {title}
      </h3>
      <div className="metric-list">{children}</div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="process-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
