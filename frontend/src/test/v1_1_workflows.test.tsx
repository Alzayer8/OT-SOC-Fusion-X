import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { clearCsrfToken, getIncidents, startLabScenario } from "../api/client";
import { renderRouterAt } from "./renderRouter";

function rawUrl(input: RequestInfo | URL): string {
  return typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
}

describe("v1.1 authenticated SOC workflow foundation", () => {
  it("redirects an unauthenticated protected route to the shell-free login page", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "authentication_required", message: "Authentication is required." },
        }),
        { status: 401, headers: { "Content-Type": "application/json" } },
      ),
    );

    const { router } = renderRouterAt("/incidents");

    expect(await screen.findByRole("button", { name: "Sign In" })).toBeVisible();
    expect(router.state.location.pathname).toBe("/login");
    expect(
      screen.queryByRole("navigation", { name: "Primary navigation" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/Credentials are never stored in browser local storage/i),
    ).toBeVisible();
  });

  it("shows the exact approved catalog and reserves Scenario Lab mutations for ADMIN", async () => {
    const user = userEvent.setup();
    renderRouterAt("/");
    await screen.findByRole("heading", { level: 1, name: "Overview" });

    await user.click(screen.getByRole("button", { name: "Scenario Lab" }));
    const lab = screen.getByRole("region", { name: "Synthetic Scenario Lab" });
    const catalog = within(lab).getByLabelText("Approved scenario catalog");
    for (const id of ["BASELINE", "S1", "S2", "S3", "S4"])
      expect(within(catalog).getByText(id, { exact: true })).toBeVisible();
    expect(within(lab).getAllByRole("button", { name: "Start Synthetic Scenario" })).toHaveLength(
      4,
    );
    expect(within(lab).getByRole("button", { name: "Reset Synthetic Lab" })).toBeVisible();
  });

  it("keeps Scenario Lab mutation controls unavailable to a SOC_ANALYST", async () => {
    const baseFetch = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = new URL(rawUrl(input), "http://localhost");
      if (url.pathname !== "/api/v1/auth/session") return baseFetch(input, init);
      return Promise.resolve(
        new Response(
          JSON.stringify({
            authenticated: true,
            user: {
              user_id: "10000000-0000-4000-8000-000000000002",
              username: "test-analyst",
              display_name: "Test Analyst",
              role: "SOC_ANALYST",
              active: true,
              version: 1,
            },
            expires_at: "2026-08-11T13:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    const user = userEvent.setup();
    renderRouterAt("/");
    await screen.findByRole("heading", { level: 1, name: "Overview" });
    await user.click(screen.getByRole("button", { name: "Scenario Lab" }));

    const lab = screen.getByRole("region", { name: "Synthetic Scenario Lab" });
    expect(within(lab).getAllByRole("button", { name: "Start Synthetic Scenario" })).toHaveLength(
      4,
    );
    for (const button of within(lab).getAllByRole("button", {
      name: "Start Synthetic Scenario",
    }))
      expect(button).toBeDisabled();
    expect(
      within(lab).queryByRole("button", { name: "Reset Synthetic Lab" }),
    ).not.toBeInTheDocument();
    expect(within(lab).getByText(/may inspect runs but cannot start them/i)).toBeVisible();
  });

  it("keeps advisory checklist state view-only for READ_ONLY users", async () => {
    const baseFetch = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = new URL(rawUrl(input), "http://localhost");
      if (url.pathname !== "/api/v1/auth/session") return baseFetch(input, init);
      return Promise.resolve(
        new Response(
          JSON.stringify({
            authenticated: true,
            user: {
              user_id: "10000000-0000-4000-8000-000000000003",
              username: "test-reader",
              display_name: "Test Reader",
              role: "READ_ONLY",
              active: true,
              version: 1,
            },
            expires_at: "2026-08-11T13:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });

    renderRouterAt("/playbooks");
    await screen.findByRole("heading", { level: 1, name: "Playbooks" });

    const checklist = screen.getByRole("list", { name: "S1 analyst review checklist" });
    for (const checkbox of within(checklist).getAllByRole("checkbox"))
      expect(checkbox).toBeDisabled();
    expect(screen.getByText(/may read this guidance but cannot mark review state/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /execute playbook/i })).not.toBeInTheDocument();
  });

  it("uses first-party cookies and readable-cookie CSRF without spoofed identity headers", async () => {
    clearCsrfToken();
    document.cookie = "otsoc_csrf=local-readable-csrf; path=/";
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({}), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await startLabScenario("S3");

    const calls = vi.mocked(fetch).mock.calls;
    const [input, init] = calls.at(-1)!;
    const headers = init?.headers as Record<string, string>;
    expect(rawUrl(input)).toBe("/api/v1/lab/start");
    expect(init?.credentials).toBe("include");
    expect(headers["X-CSRF-Token"]).toBe("local-readable-csrf");
    expect(Object.keys(headers).some((name) => name.toLowerCase().startsWith("x-otsoc"))).toBe(
      false,
    );
    expect(JSON.parse(init?.body as string)).toEqual({ scenario_id: "S3" });

    clearCsrfToken();
    document.cookie = "otsoc_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  });

  it("maps current, all-history, and exact historical-run views to backend authority", async () => {
    await getIncidents({ scope: "CURRENT", runId: "active-run", limit: 10 });
    await getIncidents({ scope: "HISTORY", limit: 10 });
    await getIncidents({ scope: "HISTORY", runId: "historical-run", limit: 10 });

    const urls = vi
      .mocked(fetch)
      .mock.calls.slice(-3)
      .map(([input]) => new URL(rawUrl(input), "http://localhost"));
    expect(urls[0].searchParams.get("scope")).toBe("CURRENT");
    expect(urls[0].searchParams.has("run_id")).toBe(false);
    expect(urls[1].searchParams.get("scope")).toBe("ALL_HISTORY");
    expect(urls[1].searchParams.has("run_id")).toBe(false);
    expect(urls[2].searchParams.get("scope")).toBe("RUN");
    expect(urls[2].searchParams.get("run_id")).toBe("historical-run");
  });
});
