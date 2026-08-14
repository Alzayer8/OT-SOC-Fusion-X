import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { numeric } from "../utils/presentation";
import { renderRouterAt } from "./renderRouter";

const INCIDENT_ID = "a6d7dfcb-4e70-5eeb-b4f3-a3644ec6c17f";

function jsonResponse(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

const incident = {
  incident_id: INCIDENT_ID,
  title: "Synthetic CV-101 control command investigation",
  summary: "Stored evidence met the deterministic S3 qualification rule.",
  category: "CONTROL_COMMAND_INVESTIGATION",
  severity: "HIGH",
  status: "OPEN",
  process_asset_keys: ["CV-101", "PL-101"],
  target_point_ids: ["control_valve_command_percent"],
  first_observed_at: "2026-08-11T12:00:00Z",
  last_observed_at: "2026-08-11T12:00:05Z",
  evidence_count: 6,
  version: 1,
};

describe("Phase 8B product behavior", () => {
  it("renders a neutral complete-empty overview without implying safety", async () => {
    renderRouterAt("/");

    expect(
      await screen.findByRole("heading", { name: "Baseline has no current incidents" }),
    ).toBeVisible();
    expect(
      screen.getByText(/No current incidents exist in the selected Baseline run/i),
    ).toBeVisible();
    expect(screen.getByText("Open Incidents").nextElementSibling).toHaveTextContent("0");
    expect(screen.queryByText(/all systems operational/i)).not.toBeInTheDocument();
  });

  it("maps incident filters and opaque pagination cursor to bounded API queries", async () => {
    const fallback = vi.mocked(fetch).getMockImplementation();
    expect(fallback).toBeDefined();
    const calls: string[] = [];
    vi.mocked(fetch).mockImplementation((input, init) => {
      const raw = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const url = new URL(raw, "http://localhost");
      if (url.pathname === "/api/v1/incidents") {
        calls.push(url.toString());
        return jsonResponse({ items: [incident], limit: 50, next_cursor: "opaque-page-token" });
      }
      return fallback!(input, init);
    });
    const user = userEvent.setup();
    renderRouterAt("/incidents");

    expect(await screen.findByText(incident.title)).toBeVisible();
    await user.selectOptions(screen.getByLabelText("Severity"), "HIGH");
    await waitFor(() => expect(calls.at(-1)).toContain("severity=HIGH"));
    await user.click(await screen.findByRole("button", { name: "Next page" }));
    await waitFor(() => expect(calls.at(-1)).toContain("cursor=opaque-page-token"));
    expect(calls.at(-1)).toContain("limit=50");
  });

  it("keeps replay navigation client-only after one bounded read", async () => {
    const fallback = vi.mocked(fetch).getMockImplementation();
    expect(fallback).toBeDefined();
    let replayReads = 0;
    vi.mocked(fetch).mockImplementation((input, init) => {
      const raw = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const url = new URL(raw, "http://localhost");
      if (url.pathname === "/api/v1/replay") {
        replayReads += 1;
        return jsonResponse({
          source_kind: "INCIDENT",
          incident,
          correlation_evidence_id: null,
          simulation_id: "sim-phase8b",
          configuration_hash: "a".repeat(64),
          observed_from: "2026-08-11T12:00:00Z",
          observed_to: "2026-08-11T12:00:01Z",
          completeness: "COMPLETE",
          gaps: [],
          truncated: false,
          events: [
            {
              event_id: "00000000-0000-4000-8000-000000000001",
              event_class: "INCIDENT_EVENT",
              sort_rank: 70,
              observed_at: "2026-08-11T12:00:00Z",
              summary: "Incident created",
              evidence: null,
              incident_event: { entry_type: "INCIDENT_CREATED" },
              integrity_verified: true,
            },
            {
              event_id: "00000000-0000-4000-8000-000000000002",
              event_class: "INCIDENT_EVENT",
              sort_rank: 70,
              observed_at: "2026-08-11T12:00:01Z",
              summary: "Evidence linked",
              evidence: null,
              incident_event: { entry_type: "EVIDENCE_LINKED" },
              integrity_verified: true,
            },
          ],
        });
      }
      return fallback!(input, init);
    });
    const user = userEvent.setup();
    renderRouterAt(`/replay?incident=${INCIDENT_ID}`);

    expect(await screen.findByText(/event 1 of 2/i)).toBeVisible();
    expect(replayReads).toBe(1);
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    expect(await screen.findByText(/event 2 of 2/i)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Step back" }));
    expect(await screen.findByText(/event 1 of 2/i)).toBeVisible();
    expect(replayReads).toBe(1);
  });

  it("renders exactly four advisory guides and exposes no execution control", async () => {
    renderRouterAt("/playbooks");

    await screen.findByRole("heading", { level: 1, name: "Playbooks" });

    for (const title of [
      "Unknown OT Asset Review",
      "Unexpected IT-to-PLC Communication Review",
      "Control Command Investigation",
      "Pump / Flow Process Inconsistency Review",
    ]) {
      expect(screen.getByRole("button", { name: new RegExp(title) })).toBeVisible();
    }
    expect(screen.getByText("ADVISORY ONLY")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /execute|automate|contain|isolate|block|shutdown/i }),
    ).not.toBeInTheDocument();
  });

  it("formats the API decimal-string command as a legitimate numeric value", () => {
    expect(numeric("25.0")).toBe(25);
    expect(numeric("not-a-number")).toBeNull();
    expect(numeric({ value: 25 })).toBeNull();
  });
});
