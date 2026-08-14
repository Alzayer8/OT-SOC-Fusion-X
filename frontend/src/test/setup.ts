import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

beforeEach(() => {
  const now = "2026-08-11T12:00:00Z";
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const rawUrl =
        typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const url = new URL(rawUrl, "http://localhost");
      let body: unknown;
      if (url.pathname === "/api/v1/auth/session") {
        body = {
          authenticated: true,
          user: {
            user_id: "10000000-0000-4000-8000-000000000001",
            username: "test-admin",
            display_name: "Test Administrator",
            role: "ADMIN",
            active: true,
            version: 1,
          },
          expires_at: "2026-08-11T13:00:00Z",
        };
      } else if (url.pathname === "/api/v1/lab/context") {
        body = {
          active_run: {
            run_id: "20000000-0000-4000-8000-000000000001",
            scenario_id: "BASELINE",
            scenario_title: "Baseline / Normal Synthetic Operation",
            status: "COMPLETED",
            started_by: null,
            started_at: now,
            completed_at: now,
            incident_count: 0,
          },
        };
      } else if (url.pathname === "/api/v1/lab/catalog") {
        body = {
          items: [
            {
              scenario_id: "BASELINE",
              title: "Baseline / Normal Synthetic Operation",
              description: "Normal stored synthetic process context.",
              state: "READY",
            },
            {
              scenario_id: "S1",
              title: "Unknown OT Asset / Source Review",
              description: "Approved synthetic identity review.",
              state: "READY",
            },
            {
              scenario_id: "S2",
              title: "Unexpected IT-to-PLC Communication",
              description: "Approved synthetic policy review.",
              state: "READY",
            },
            {
              scenario_id: "S3",
              title: "Control Command Investigation",
              description: "Approved frozen command investigation.",
              state: "READY",
            },
            {
              scenario_id: "S4",
              title: "Pump / Flow Process Inconsistency",
              description: "Approved process-only inconsistency.",
              state: "READY",
            },
          ],
        };
      } else if (url.pathname === "/api/v1/lab/runs") {
        body = {
          items: [
            {
              run_id: "20000000-0000-4000-8000-000000000001",
              scenario_id: "BASELINE",
              scenario_title: "Baseline / Normal Synthetic Operation",
              status: "COMPLETED",
              started_by: null,
              started_at: now,
              completed_at: now,
              incident_count: 0,
            },
          ],
        };
      } else if (url.pathname === "/health/live") {
        body = { status: "ok", service: "OT-SOC Fusion X", version: "1.0.0" };
      } else if (url.pathname === "/health/ready") {
        body = { status: "ready", database: "available" };
      } else if (url.pathname === "/api/v1/meta") {
        body = {
          application_name: "OT-SOC Fusion X",
          application_version: "1.0.0",
          environment: "test",
          api_version: "v1",
          operating_mode: "SYNTHETIC_OFFLINE",
          domain: "oil_gas_transfer",
          active_profiles: [],
          active_schemas: [],
        };
      } else if (url.pathname === "/api/v1/overview/summary") {
        body = {
          as_of: now,
          window_start: "2026-08-10T12:00:00Z",
          window_end: now,
          window_complete: true,
          incidents: {
            total: 0,
            open: 0,
            investigating: 0,
            resolved: 0,
            low: 0,
            medium: 0,
            high: 0,
            high_non_resolved: 0,
            categories: {
              asset_identity_anomaly: 0,
              communication_policy_violation: 0,
              control_command_investigation: 0,
              process_inconsistency: 0,
            },
          },
          policy_findings: { total: 0, approved: 0, denied: 0, unknown: 0 },
          correlations: {
            total: 0,
            correlated: 0,
            not_correlated: 0,
            insufficient_evidence: 0,
            indeterminate: 0,
          },
          assets: { total: 11, enabled: 11, cyber: 6, process: 5 },
          recent_activity: [],
          process_snapshot_status: "UNAVAILABLE",
          process_snapshot_message: "Process telemetry is unavailable for this evidence window.",
          process_snapshot: null,
          linked_valve_command: null,
        };
      } else if (url.pathname === "/api/v1/assets") {
        body = {
          profile_id: "otsoc.asset_inventory.oil_gas_transfer",
          profile_version: "1.0.0",
          profile_sha256: "5".repeat(64),
          domain: "oil_gas_transfer",
          educational_only: true,
          disclaimer: "Fictional synthetic inventory.",
          zones: [],
          assets: [],
          relationships: [],
        };
      } else if (url.pathname === "/api/v1/incidents") {
        body = { items: [], limit: 50, next_cursor: null };
      } else if (url.pathname === "/api/v1/incident-assignees") {
        body = { items: [] };
      } else if (url.pathname.endsWith("/audit")) {
        body = { items: [] };
      } else if (url.pathname.endsWith("/report")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ error: { message: "Not found", request_id: "test-request" } }),
            {
              status: 404,
              headers: { "Content-Type": "application/json" },
            },
          ),
        );
      } else if (url.pathname === "/api/v1/users") {
        body = { items: [] };
      } else if (url.pathname === "/api/v1/evidence") {
        body = { items: [], limit: 50, offset: 0, next_cursor: null };
      } else {
        return Promise.resolve(
          new Response(
            JSON.stringify({ error: { message: "Not found", request_id: "test-request" } }),
            { status: 404, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
