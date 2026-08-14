import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BarChart, DonutChart, TrendChart } from "../components/Visualizations";
import { renderRouterAt } from "./renderRouter";

const INCIDENT_ID = "a6d7dfcb-4e70-5eeb-b4f3-a3644ec6c17f";
const SEMANTIC_ID = "00000000-0000-4000-8000-000000000010";
const RAW_ID = "00000000-0000-4000-8000-000000000011";
const now = "2026-08-11T12:00:00Z";

const incident = {
  incident_id: INCIDENT_ID,
  title: "Synthetic CV-101 control command investigation",
  summary: "Stored evidence met the deterministic S3 qualification rule.",
  category: "CONTROL_COMMAND_INVESTIGATION",
  severity: "HIGH",
  status: "OPEN",
  process_asset_keys: ["CV-101", "PL-101"],
  target_point_ids: ["control_valve_command_percent"],
  first_observed_at: now,
  last_observed_at: "2026-08-11T12:00:05Z",
  evidence_count: 2,
  version: 1,
  policy_context: "DENIED",
  correlation_context: "CORRELATED",
  s3_semantic_evidence_id: SEMANTIC_ID,
  qualification_rule_id: "OTSOC-INCIDENT-S3",
};

function overviewFixture() {
  return {
    as_of: now,
    window_start: "2026-08-10T12:00:00Z",
    window_end: now,
    window_complete: true,
    incidents: {
      total: 4,
      open: 4,
      investigating: 0,
      resolved: 0,
      low: 1,
      medium: 1,
      high: 2,
      high_non_resolved: 2,
      categories: {
        asset_identity_anomaly: 1,
        communication_policy_violation: 1,
        control_command_investigation: 1,
        process_inconsistency: 1,
      },
    },
    policy_findings: { total: 3, approved: 1, denied: 2, unknown: 0 },
    correlations: {
      total: 2,
      correlated: 2,
      not_correlated: 0,
      insufficient_evidence: 0,
      indeterminate: 0,
    },
    assets: { total: 11, enabled: 11, cyber: 6, process: 5 },
    recent_activity: [
      {
        activity_id: "activity-1",
        incident_id: INCIDENT_ID,
        observed_at: now,
        entry_type: "INCIDENT_CREATED",
        summary: "Qualified from stored evidence.",
      },
    ],
    process_snapshot_status: "COMPLETE",
    process_snapshot_message: "Latest integrity-verified stored telemetry snapshot.",
    process_snapshot: telemetryRecord("telemetry-overview", now, 0, 61, 8.5),
    linked_valve_command: semanticRecord,
  };
}

const rawRecord = {
  evidence_id: RAW_ID,
  evidence_type: "synthetic_protocol_event",
  payload_schema: "otsoc.synthetic.modbus",
  payload_schema_version: "1.0.0",
  observed_at: now,
  source_key: "synthetic_modbus",
  integrity_sha256: "a".repeat(64),
  provenance: {},
  payload: {
    function_code: 6,
    unit_id: 1,
    table_type: "HOLDING_REGISTER",
    address_offset: 1,
    raw_value: 250,
  },
};

const semanticRecord = {
  evidence_id: SEMANTIC_ID,
  evidence_type: "protocol_semantic_event",
  payload_schema: "otsoc.protocol.semantic",
  payload_schema_version: "1.0.0",
  observed_at: now,
  source_key: "offline_semantics",
  integrity_sha256: "b".repeat(64),
  provenance: {},
  payload: {
    source_evidence_id: RAW_ID,
    source_evidence_integrity_sha256: "a".repeat(64),
    interpretation_status: "MAPPED",
    operation_category: "WRITE",
    point_id: "control_valve_command_percent",
    decoded_value: "25.0",
    unit: "% open",
    reason_code: "MAPPING_MATCH",
    profile_id: "otsoc.synthetic_modbus.oil_gas_transfer",
    profile_version: "1.0.0",
    decoder_name: "otsoc_offline_modbus_semantics",
    decoder_version: "1.0.0",
    semantic_statement: "Set CV-101 command to 25.0% open.",
  },
};

function telemetryRecord(
  id: string,
  observedAt: string,
  sequence: number,
  flow: number,
  pressure: number,
) {
  return {
    evidence_id: id,
    evidence_type: "simulator_telemetry",
    payload_schema: "otsoc.simulator.telemetry",
    payload_schema_version: "2.0.0",
    observed_at: observedAt,
    source_key: "synthetic_simulator",
    integrity_sha256: String(sequence + 1)
      .repeat(64)
      .slice(0, 64),
    provenance: {},
    payload: {
      simulation_id: "sim-visual-test",
      sequence_number: sequence,
      source_tank_level_percent: 72 - sequence,
      receiving_tank_level_percent: 38 + sequence,
      transfer_pump_command_percent: 100,
      transfer_pump_running: true,
      pipeline_flow_rate_m3h: flow,
      pipeline_pressure_bar: pressure,
      process_temperature_c: 31,
      control_valve_position_percent: 25,
    },
  };
}

function response(body: unknown): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function installFixtureFetch() {
  const calls: { url: string; method: string }[] = [];
  const baseFetch = vi.mocked(fetch).getMockImplementation();
  vi.mocked(fetch).mockImplementation((input, init) => {
    const rawUrl =
      typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(rawUrl, "http://localhost");
    calls.push({ url: url.toString(), method: init?.method ?? "GET" });
    if (
      (url.pathname.startsWith("/api/v1/auth/") || url.pathname.startsWith("/api/v1/lab/")) &&
      baseFetch
    )
      return baseFetch(input, init);
    if (url.pathname === "/api/v1/overview/summary") return response(overviewFixture());
    if (url.pathname === "/api/v1/incidents")
      return response({ items: [incident], limit: 50, next_cursor: null });
    if (url.pathname === `/api/v1/incidents/${INCIDENT_ID}`) {
      return response({
        incident,
        context: {
          evidence_completeness: "COMPLETE",
          policy: "DENIED",
          correlation: "CORRELATED",
          unavailable: [],
        },
        evidence_memberships: [
          {
            membership_id: "membership-1",
            role: "SEMANTIC",
            evidence_type: "protocol_semantic_event",
            evidence_id: SEMANTIC_ID,
            observed_at: now,
            integrity_sha256: "b".repeat(64),
          },
          {
            membership_id: "membership-2",
            role: "CORRELATION",
            evidence_type: "correlation_finding",
            evidence_id: "00000000-0000-4000-8000-000000000012",
            observed_at: now,
            integrity_sha256: "c".repeat(64),
          },
        ],
        lineage_references: [
          {
            evidence_id: RAW_ID,
            evidence_type: "synthetic_protocol_event",
            integrity_sha256: "a".repeat(64),
            relationship: "SOURCE",
          },
          {
            evidence_id: SEMANTIC_ID,
            evidence_type: "protocol_semantic_event",
            integrity_sha256: "b".repeat(64),
            relationship: "DERIVED",
          },
        ],
        timeline: [
          {
            timeline_entry_id: "timeline-1",
            observed_at: now,
            recorded_at: now,
            entry_type: "INCIDENT_CREATED",
            summary: "Qualified from stored evidence.",
            aggregate_version: 1,
          },
        ],
        status_history: [],
        severity_history: [],
        notes: [],
      });
    }
    if (url.pathname === `/api/v1/evidence/${SEMANTIC_ID}`) return response(semanticRecord);
    if (url.pathname === `/api/v1/evidence/${RAW_ID}`) return response(rawRecord);
    if (url.pathname === "/api/v1/evidence")
      return response({ items: [rawRecord, semanticRecord], limit: 50, next_cursor: null });
    if (url.pathname === "/api/v1/replay") {
      const first = telemetryRecord("telemetry-1", now, 0, 60, 8.4);
      const second = telemetryRecord("telemetry-2", "2026-08-11T12:00:01Z", 1, 61, 8.5);
      return response({
        source_kind: "INCIDENT",
        incident,
        correlation_evidence_id: null,
        simulation_id: "sim-visual-test",
        configuration_hash: "d".repeat(64),
        observed_from: now,
        observed_to: "2026-08-11T12:00:01Z",
        completeness: "COMPLETE",
        gaps: [],
        truncated: false,
        events: [first, second].map((evidence, index) => ({
          event_id: `00000000-0000-4000-8000-00000000002${index}`,
          event_class: "TELEMETRY",
          sort_rank: 50,
          observed_at: evidence.observed_at,
          summary: "Stored telemetry",
          evidence,
          incident_event: null,
          integrity_verified: true,
        })),
      });
    }
    if (url.pathname === "/health/live")
      return response({ status: "ok", service: "OT-SOC Fusion X", version: "1.0.0" });
    if (url.pathname === "/health/ready")
      return response({ status: "ready", database: "available" });
    if (url.pathname === "/api/v1/meta")
      return response({
        application_name: "OT-SOC Fusion X",
        application_version: "1.0.0",
        environment: "test",
        api_version: "v1",
        operating_mode: "SYNTHETIC_OFFLINE",
        domain: "oil_gas_transfer",
        active_profiles: [],
        active_schemas: [],
      });
    return response({ items: [] });
  });
  return calls;
}

describe("v1.1.1 visual experience polish", () => {
  it("renders the enhanced Overview with exact sourced KPI and distribution values", async () => {
    installFixtureFetch();
    renderRouterAt("/");
    expect(await screen.findByRole("heading", { name: "Incident Severity" })).toBeVisible();
    expect(
      screen.getByRole("img", {
        name: /Incident severity distribution.*High 2.*Medium 1.*Low 1.*Total 4/i,
      }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Cyber-Physical Investigation" })).toBeVisible();
    expect(screen.getByText("2 Temporally Correlated")).toBeVisible();
  });

  it("does not fabricate a chart when a complete aggregate has zero records", async () => {
    renderRouterAt("/");
    expect(
      await screen.findByText("Incident severity distribution: no sourced records."),
    ).toBeVisible();
    expect(
      screen.queryByRole("img", { name: /Incident severity distribution/i }),
    ).not.toBeInTheDocument();
  });

  it("keeps command, observed equipment state, and process effect visibly separate", async () => {
    installFixtureFetch();
    renderRouterAt("/digital-twin");
    expect(await screen.findByText("P-101 Pump Command", { exact: true })).toBeVisible();
    expect(screen.getByText("P-101 Pump Running State", { exact: true })).toBeVisible();
    expect(screen.getByText("CV-101 Valve Command", { exact: true })).toBeVisible();
    expect(screen.getByText("CV-101 Observed Valve Position", { exact: true })).toBeVisible();
    expect(screen.getByText("Observed Process Effect", { exact: true })).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /start pump|stop pump|open valve|close valve/i }),
    ).not.toBeInTheDocument();
  });

  it("renders an enhanced bounded incident list without claiming a global list total", async () => {
    installFixtureFetch();
    renderRouterAt("/incidents");
    expect(await screen.findByText("Visible Records")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Visible Severity Profile" })).toBeVisible();
    expect(screen.getByRole("img", { name: "High: 1" })).toBeVisible();
    expect(screen.getAllByText("Current bounded page")).toHaveLength(2);
  });

  it("renders the enhanced incident workspace, evidence chain, timeline, and lifecycle boundary", async () => {
    installFixtureFetch();
    const user = userEvent.setup();
    renderRouterAt(`/incidents/${INCIDENT_ID}`);
    expect(await screen.findByLabelText("Incident context summary")).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "Evidence" }));
    expect(
      await screen.findByRole("heading", { name: "Evidence membership and lineage" }),
    ).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "Timeline" }));
    expect(
      await screen.findByRole("heading", { name: "Deterministic incident timeline" }),
    ).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "Investigation" }));
    expect(
      await screen.findByText(
        /No severity, containment, asset, network, or process-control action/i,
      ),
    ).toBeVisible();
  });

  it("visually distinguishes verified RAW evidence from SEMANTIC translation", async () => {
    installFixtureFetch();
    renderRouterAt(`/protocol-analysis?evidence=${SEMANTIC_ID}`);
    expect(
      await screen.findByRole("heading", { name: "Offline synthetic Modbus evidence" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Derived typed interpretation" })).toBeVisible();
    expect(screen.getByText("250", { exact: true })).toBeVisible();
    expect(screen.getByText("25.0 % open", { exact: true })).toBeVisible();
    expect(screen.getByText("VERIFIED LINEAGE")).toBeVisible();
  });

  it("uses accessible native charts with exact supplied values", () => {
    render(
      <>
        <DonutChart
          title="Exact sample"
          data={[
            { label: "One", value: 2, tone: "blue" },
            { label: "Two", value: 3, tone: "cyan" },
          ]}
        />
        <BarChart title="Exact bars" data={[{ label: "Stored", value: 7, tone: "purple" }]} />
        <TrendChart
          title="Exact trend"
          series={[
            {
              label: "Flow",
              tone: "cyan",
              unit: "m³/h",
              points: [
                { x: 0, label: "t0", value: 1 },
                { x: 1, label: "t1", value: 2 },
              ],
            },
          ]}
        />
      </>,
    );
    expect(screen.getByRole("img", { name: /Exact sample.*One 2.*Two 3.*Total 5/i })).toBeVisible();
    expect(screen.getByRole("img", { name: "Stored: 7" })).toBeVisible();
    expect(screen.getByRole("img", { name: /Exact trend.*2 stored points/i })).toBeVisible();
  });

  it("renders cursor-synchronized Replay trends while controls remain client-only", async () => {
    const calls = installFixtureFetch();
    const user = userEvent.setup();
    renderRouterAt(`/replay?incident=${INCIDENT_ID}`);
    expect(await screen.findByRole("heading", { name: "Flow & Pressure" })).toBeVisible();
    expect(screen.getByRole("img", { name: /Replay flow and pressure trend/i })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    expect(screen.getByText("2 / 2")).toBeVisible();
    expect(
      calls.filter((call) => ["POST", "PATCH", "PUT", "DELETE"].includes(call.method)),
    ).toEqual([]);
    expect(screen.getByText(/controls are client-only/i)).toBeVisible();
  });

  it("keeps exactly four advisory playbooks and exposes no execution action", async () => {
    renderRouterAt("/playbooks");
    await screen.findByRole("heading", { name: "Approved advisory guides" });
    const list = screen
      .getByRole("heading", { name: "Approved advisory guides" })
      .closest("section");
    expect(list).not.toBeNull();
    expect(within(list!).getAllByRole("button")).toHaveLength(4);
    expect(screen.getByText("Exactly S1–S4")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /execute|automate|contain|isolate|block|shutdown/i }),
    ).not.toBeInTheDocument();
  });

  it("renders Reports charts from the bounded incident response", async () => {
    installFixtureFetch();
    renderRouterAt("/reports");
    expect(await screen.findByRole("heading", { name: "Severity Distribution" })).toBeVisible();
    expect(
      screen.getByRole("img", { name: /Report incident severity distribution.*High 1/i }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Disposition Distribution" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Scenario Run Summary" })).toBeVisible();
  });

  it("keeps Settings narrow while presenting health and release context", async () => {
    installFixtureFetch();
    renderRouterAt("/settings");
    expect(await screen.findByText("Visual experience")).toBeVisible();
    expect(screen.getByText("v1.1.1")).toBeVisible();
    expect(screen.getByText("Stored synthetic records only")).toBeVisible();
    expect(screen.queryByText(/LDAP|API keys|SIEM|SOAR|packet capture/i)).not.toBeInTheDocument();
  });

  it("preserves synthetic and offline labels on every product route", async () => {
    for (const route of ["/", "/digital-twin", "/replay", "/playbooks", "/reports", "/settings"]) {
      const view = renderRouterAt(route);
      expect(await screen.findByText("Synthetic / Offline")).toBeVisible();
      view.unmount();
    }
  });

  it("uses a textual severity cue in addition to its symbol and color", async () => {
    installFixtureFetch();
    const { container } = renderRouterAt("/incidents");
    await screen.findByText("Visible Records");
    expect(container.querySelector(".severity")).toHaveTextContent("▲HIGH");
  });

  it("loads only the configured local frontend and backend origins", async () => {
    const calls = installFixtureFetch();
    renderRouterAt("/");
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(
      calls.every((call) => new URL(call.url, "http://localhost").origin === "http://localhost"),
    ).toBe(true);
  });
});
