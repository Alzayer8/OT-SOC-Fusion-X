import { spawnSync } from "node:child_process";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

type ScenarioId = "S1" | "S2" | "S3" | "S4";
type Disposition = "TRUE_POSITIVE" | "FALSE_POSITIVE";

interface AuthSession {
  authenticated: boolean;
  user: {
    user_id: string;
    username: string;
    display_name: string;
    role: string;
    active: boolean;
  } | null;
}

interface LabRun {
  run_id: string;
  scenario_id: "BASELINE" | ScenarioId;
  status: string;
  evidence_count: number;
  incident_count: number;
}

interface LabContextResponse {
  active_run: LabRun;
}

interface LabRunListResponse {
  items: LabRun[];
  total: number;
}

interface OverviewResponse {
  active_run: {
    run_id: string;
    scenario_id: "BASELINE" | ScenarioId;
    scenario_state: "COMPLETED";
    context_scope: "CURRENT_RUN";
  };
  incidents: {
    total: number;
    open: number;
    high: number;
    high_non_resolved: number;
  };
  policy_findings: { total: number; denied: number };
  correlations: { total: number; correlated: number };
  process_snapshot_status: string;
  process_snapshot_scope: string;
}

interface IncidentRecord {
  incident_id: string;
  title: string;
  category: string;
  severity: string;
  status: "OPEN" | "INVESTIGATING" | "RESOLVED";
  disposition: "UNREVIEWED" | Disposition;
  version: number;
  evidence_count: number;
  policy_context: string;
  correlation_context: string;
  malicious_intent_inferred: boolean;
  causality_inferred: boolean;
}

interface IncidentListResponse {
  items: IncidentRecord[];
}

interface EvidenceMembership {
  evidence_id: string;
  evidence_type: string;
  integrity_sha256: string;
}

interface IncidentDetailResponse {
  incident: IncidentRecord;
  evidence_memberships: EvidenceMembership[];
}

interface EvidenceRecord {
  evidence_id: string;
  evidence_type: string;
  integrity_sha256: string;
  observed_at: string;
  payload: Record<string, unknown>;
}

interface IncidentAuditResponse {
  items: { action: string; actor_display_name: string; summary: string }[];
}

interface ReplayResponse {
  events: { evidence: EvidenceRecord | null }[];
}

const FRONTEND_URL = process.env.OTSOC_E2E_BASE_URL ?? "http://127.0.0.1:5173";
const BACKEND_URL = process.env.OTSOC_E2E_BACKEND_URL ?? "http://127.0.0.1:8000";
const ALLOWED_BROWSER_ORIGINS = new Set([
  new URL(FRONTEND_URL).origin,
  new URL(BACKEND_URL).origin,
]);
const externalRequests = new WeakMap<Page, string[]>();
const scenarioIncidents: Partial<Record<ScenarioId, string>> = {};
let authenticatedDisplayName = "";
let historyCountBeforeRestart = 0;

const SCENARIO_EXPECTATIONS = {
  S1: {
    category: "ASSET_IDENTITY_ANOMALY",
    categoryLabel: "ASSET IDENTITY ANOMALY",
    playbook: "Unknown OT Asset Review",
  },
  S2: {
    category: "COMMUNICATION_POLICY_VIOLATION",
    categoryLabel: "COMMUNICATION POLICY VIOLATION",
    playbook: "Unexpected IT-to-PLC Communication Review",
  },
  S3: {
    category: "CONTROL_COMMAND_INVESTIGATION",
    categoryLabel: "CONTROL COMMAND INVESTIGATION",
    playbook: "Control Command Investigation",
  },
  S4: {
    category: "PROCESS_INCONSISTENCY",
    categoryLabel: "PROCESS INCONSISTENCY",
    playbook: "Pump / Flow Process Inconsistency Review",
  },
} as const;

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => {
  const unexpected: string[] = [];
  externalRequests.set(page, unexpected);
  page.on("request", (request) => {
    const url = request.url();
    if (url.startsWith("data:") || url.startsWith("blob:")) return;
    const origin = new URL(url).origin;
    if (!ALLOWED_BROWSER_ORIGINS.has(origin)) unexpected.push(url);
  });
});

test.afterEach(async ({ page }) => {
  expect(externalRequests.get(page) ?? [], "The frontend must remain local/offline.").toEqual([]);
  await expectForbiddenControlsAbsent(page);
});

test("V11-T086 Playwright first-start Baseline", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login(?:\?.*)?$/);
  await expect(page.getByRole("heading", { name: "OT-SOC Fusion X" })).toBeVisible();
  await expect(page.getByText("Academic Synthetic Environment", { exact: true })).toBeVisible();
  await expect(page.getByText("Synthetic / Offline", { exact: true })).toBeVisible();

  const unauthenticatedOverview = await page.request.get("/api/v1/overview/summary");
  expect(unauthenticatedOverview.status()).toBe(401);

  await login(page);
  await expect(page.locator(".top-header__run")).toContainText(/Active Scenario:\s*BASELINE/i);
  await expect(page.getByText(/Current Run.*BASELINE.*COMPLETED/i)).toBeVisible();
  await expectKpi(page, "Open Incidents", "0");
  await expectKpi(page, "High Severity", "0");
  await expectKpi(page, "Denied Policy Findings", "0");
  await expectKpi(page, "Temporally Correlated", "0");
  await expect(
    page.getByRole("heading", { name: "Baseline has no current incidents" }),
  ).toBeVisible();

  const overview = await getJson<OverviewResponse>(page, "/api/v1/overview/summary");
  expect(overview.active_run.scenario_id).toBe("BASELINE");
  expect(overview.active_run.scenario_state).toBe("COMPLETED");
  expect(overview.incidents.total).toBe(0);
  expect(overview.incidents.high).toBe(0);
  expect(overview.policy_findings.denied).toBe(0);
  expect(overview.correlations.correlated).toBe(0);
  expect(overview.process_snapshot_status).toBe("COMPLETE");
  expect(overview.process_snapshot_scope).toBe("ACTIVE_RUN");

  await page.goto("/incidents?scope=CURRENT");
  await expect(
    page.getByRole("heading", { name: "No current incidents in Baseline" }),
  ).toBeVisible();
  const currentIncidents = await getJson<IncidentListResponse>(
    page,
    "/api/v1/incidents?scope=CURRENT&limit=50",
  );
  expect(currentIncidents.items).toEqual([]);

  await page.goto("/digital-twin");
  await expect(page.getByRole("heading", { level: 1, name: "Digital Twin" })).toBeVisible();
  await expect(page.getByText(/Baseline.*read-only/i)).toBeVisible();
  await expect(page.locator(".process-node")).toHaveCount(5);
  await expect(page.getByText("P-101 Pump Running State", { exact: true })).toBeVisible();
  await expect(page.getByText("Pipeline Flow", { exact: true })).toBeVisible();
  await expect(page.getByText("Pipeline Pressure", { exact: true })).toBeVisible();

  await openScenarioLab(page);
  const lab = page.getByRole("region", { name: "Synthetic Scenario Lab" });
  await expect(lab.locator(".scenario-catalog article")).toHaveCount(5);
  expect(await lab.locator(".scenario-catalog article > span").allTextContents()).toEqual([
    "BASELINE",
    "S1",
    "S2",
    "S3",
    "S4",
  ]);
  await expect(lab.locator("input, textarea, select")).toHaveCount(0);
});

test("V11-T087 Playwright login", async ({ page }) => {
  const { username, password } = credentials();
  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByRole("textbox", { name: "Password", exact: true }).fill(`${password}-invalid`);
  const rejected = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/v1/auth/login" &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Sign In" }).click();
  expect((await rejected).status()).toBe(401);
  await expect(page.getByRole("alert")).toContainText("Sign in failed");
  await expect(page.getByRole("textbox", { name: "Password", exact: true })).toHaveValue("");

  await page.getByRole("textbox", { name: "Password", exact: true }).fill(password);
  const accepted = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/v1/auth/login" &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Sign In" }).click();
  expect((await accepted).ok()).toBeTruthy();
  await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
  const session = await getJson<AuthSession>(page, "/api/v1/auth/session");
  expect(session.authenticated).toBe(true);
  expect(session.user?.username).toBe(username);
  expect(session.user?.role).toBe("ADMIN");
  authenticatedDisplayName = session.user?.display_name ?? "";
  await expect(page.getByLabel("Authenticated analyst")).toContainText(authenticatedDisplayName);
  await expect(page.getByLabel("Authenticated analyst")).toContainText("ADMIN");

  const logout = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/v1/auth/logout" &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Logout" }).click();
  expect((await logout).ok()).toBeTruthy();
  await expect(page).toHaveURL(/\/login(?:\?.*)?$/);
  const protectedAfterLogout = await page.request.get("/api/v1/incidents?scope=CURRENT&limit=1");
  expect(protectedAfterLogout.status()).toBe(401);
});

test("V11-T088 Playwright S1 analyst journey", async ({ page }) => {
  await login(page);
  await startScenario(page, "S1");
  const overview = await getJson<OverviewResponse>(page, "/api/v1/overview/summary");
  expect(overview.active_run.scenario_id).toBe("S1");
  expect(overview.incidents.total).toBe(1);
  expect(overview.process_snapshot_scope).toBe("BASELINE_REFERENCE");

  const incident = await openCurrentIncident(page, "S1");
  scenarioIncidents.S1 = incident.incident_id;
  expect(incident.category).toBe("ASSET_IDENTITY_ANOMALY");
  expect(incident.severity).toBe("LOW");
  expect(incident.policy_context).toBe("UNKNOWN");
  expect(incident.malicious_intent_inferred).toBe(false);
  expect(incident.causality_inferred).toBe(false);
  await expect(
    page.getByText(/does not prove an attacker, compromise, maliciousness, or cause/i),
  ).toBeVisible();

  await inspectEvidenceTab(page, incident.evidence_count);
  await verifyLinkedPlaybook(page, "S1");
  await completeSocWorkflow(page, "S1", "TRUE_POSITIVE");
});

test("V11-T089 Playwright S2 analyst journey", async ({ page }) => {
  await login(page);
  await startScenario(page, "S2");
  const overview = await getJson<OverviewResponse>(page, "/api/v1/overview/summary");
  expect(overview.active_run.scenario_id).toBe("S2");
  expect(overview.incidents.total).toBe(1);
  expect(overview.policy_findings.denied).toBeGreaterThan(0);

  const incident = await openCurrentIncident(page, "S2");
  scenarioIncidents.S2 = incident.incident_id;
  expect(incident.category).toBe("COMMUNICATION_POLICY_VIOLATION");
  expect(incident.severity).toBe("MEDIUM");
  expect(incident.policy_context).toBe("DENIED");
  expect(incident.malicious_intent_inferred).toBe(false);

  const evidence = await replayEvidence(page, incident.incident_id);
  const policy = evidence.find((item) => item.evidence_type === "communication_policy_finding");
  expect(policy, "S2 must expose its stored communication-policy finding.").toBeDefined();
  expect(policy?.payload.policy_status).toBe("DENIED");
  expect(policy?.payload.reason_code).toBe("COMMUNICATION_NOT_APPROVED");
  await page.goto(`/protocol-analysis?evidence=${encodeURIComponent(policy!.evidence_id)}`);
  await expect(page.locator(".exact-status").filter({ hasText: "DENIED" })).toBeVisible();
  await expect(page.getByText(/does not establish maliciousness/i)).toBeVisible();
  await expect(page.getByText(/confirmed malicious|confirmed attack|compromised/i)).toHaveCount(0);

  await page.goto(`/incidents/${incident.incident_id}`);
  await verifyLinkedPlaybook(page, "S2");
  await completeSocWorkflow(page, "S2", "TRUE_POSITIVE");
});

test("V11-T090 Playwright S3 full SOC journey", async ({ page }) => {
  await login(page);
  await startScenario(page, "S3");
  const overview = await getJson<OverviewResponse>(page, "/api/v1/overview/summary");
  expect(overview.active_run.scenario_id).toBe("S3");
  expect(overview.incidents.total).toBe(1);
  expect(overview.incidents.high).toBe(1);
  expect(overview.policy_findings.denied).toBeGreaterThan(0);
  expect(overview.correlations.correlated).toBeGreaterThan(0);

  const incident = await openCurrentIncident(page, "S3");
  scenarioIncidents.S3 = incident.incident_id;
  expect(incident.category).toBe("CONTROL_COMMAND_INVESTIGATION");
  expect(incident.severity).toBe("HIGH");
  expect(incident.policy_context).toBe("DENIED");
  expect(incident.correlation_context).toBe("CORRELATED");
  expect(incident.malicious_intent_inferred).toBe(false);
  expect(incident.causality_inferred).toBe(false);

  const evidence = await replayEvidence(page, incident.incident_id);
  const raw = evidence.find((item) => item.evidence_type === "synthetic_protocol_event");
  const semantic = evidence.find((item) => item.evidence_type === "protocol_semantic_event");
  expect(raw, "S3 must contain the frozen raw protocol record.").toBeDefined();
  expect(semantic, "S3 must contain the verified semantic derivative.").toBeDefined();
  expect(raw?.payload.function_code).toBe(6);
  expect(raw?.payload.address_offset).toBe(1);
  expect(raw?.payload.raw_value).toBe(250);
  expect(semantic?.payload.point_id).toBe("control_valve_command_percent");
  expect(semantic?.payload.fictional_target_component).toBe("CV-101");
  expect(String(semantic?.payload.decoded_value)).toBe("25.0");

  await page.getByRole("link", { name: "Open protocol semantic evidence" }).click();
  await expect(
    page.getByRole("heading", { name: "Offline synthetic Modbus evidence" }),
  ).toBeVisible();
  await expect(page.getByText("250", { exact: true })).toBeVisible();
  await expect(page.getByText("25.0 % open", { exact: true })).toBeVisible();

  await page.goto(`/incidents/${incident.incident_id}`);
  await page.getByRole("link", { name: "Open read-only Digital Twin" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Digital Twin" })).toBeVisible();
  const valveCommand = page.locator(".process-metric").filter({ hasText: "CV-101 Valve Command" });
  const valveObserved = page
    .locator(".process-metric")
    .filter({ hasText: "CV-101 Observed Valve Position" });
  const pumpCommand = page.locator(".process-metric").filter({ hasText: "P-101 Pump Command" });
  const pumpRunning = page
    .locator(".process-metric")
    .filter({ hasText: "P-101 Pump Running State" });
  await expect(valveCommand).toContainText("25.0 % open");
  await expect(valveObserved).toContainText("25.0 % open");
  await expect(pumpCommand).toContainText("55.0 %");
  await expect(pumpRunning).toContainText("RUNNING");
  await expect(
    page.getByText(/Temporally Correlated.*cause and malicious intent are not determined/i),
  ).toBeVisible();

  await page.goto(`/incidents/${incident.incident_id}`);
  await page.getByRole("link", { name: "Open stored-evidence Replay" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Replay" })).toBeVisible();
  await expect(
    page.locator(".exact-status").filter({ hasText: "HISTORICAL STORED EVIDENCE" }),
  ).toBeVisible();
  const mutationRequests: string[] = [];
  page.on("request", (request) => {
    if (["POST", "PATCH", "PUT", "DELETE"].includes(request.method())) {
      mutationRequests.push(`${request.method()} ${request.url()}`);
    }
  });
  await page.getByRole("button", { name: "Step forward" }).click();
  await page.getByRole("button", { name: "Play replay" }).click();
  await page.getByRole("button", { name: "Pause replay" }).click();
  expect(mutationRequests).toEqual([]);

  await page.goto(`/incidents/${incident.incident_id}`);
  await verifyLinkedPlaybook(page, "S3");
  await completeSocWorkflow(page, "S3", "TRUE_POSITIVE", { xssSentinel: true });
});

test("V11-T091 Playwright S4 full SOC journey", async ({ page }) => {
  await login(page);
  await startScenario(page, "S4");
  const overview = await getJson<OverviewResponse>(page, "/api/v1/overview/summary");
  expect(overview.active_run.scenario_id).toBe("S4");
  expect(overview.incidents.total).toBe(1);
  expect(overview.policy_findings.denied).toBe(0);
  expect(overview.correlations.correlated).toBeGreaterThan(0);

  const incident = await openCurrentIncident(page, "S4");
  scenarioIncidents.S4 = incident.incident_id;
  expect(incident.category).toBe("PROCESS_INCONSISTENCY");
  expect(incident.policy_context).toBe("UNAVAILABLE");
  expect(incident.correlation_context).toBe("CORRELATED");
  expect(incident.malicious_intent_inferred).toBe(false);
  expect(incident.causality_inferred).toBe(false);

  const evidence = await replayEvidence(page, incident.incident_id);
  expect(new Set(evidence.map((item) => item.evidence_type))).toEqual(
    new Set(["simulator_telemetry", "correlation_finding"]),
  );
  const correlation = evidence.find((item) => item.evidence_type === "correlation_finding");
  expect(correlation?.payload.primary_cyber_evidence_id).toBeNull();
  expect(correlation?.payload.causality_inferred).toBe(false);
  expect(correlation?.payload.malicious_intent_inferred).toBe(false);

  await page.getByRole("link", { name: "Open read-only Digital Twin" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Digital Twin" })).toBeVisible();
  await expect(page.getByText("P-101 Pump Running State", { exact: true })).toBeVisible();
  await expect(page.getByText("RUNNING", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Pipeline Flow", { exact: true })).toBeVisible();
  await expect(page.getByText("Pipeline Pressure", { exact: true })).toBeVisible();
  await expect(page.getByText(/cause and malicious intent are not determined/i)).toBeVisible();
  await expect(page.getByText("Verified CV-101 command evidence", { exact: true })).toHaveCount(0);

  await page.goto(`/incidents/${incident.incident_id}`);
  await verifyLinkedPlaybook(page, "S4");
  await completeSocWorkflow(page, "S4", "TRUE_POSITIVE");

  const runs = await getJson<LabRunListResponse>(page, "/api/v1/lab/runs?limit=100");
  expect(new Set(runs.items.map((run) => run.scenario_id))).toEqual(
    new Set(["BASELINE", "S1", "S2", "S3", "S4"]),
  );
  historyCountBeforeRestart = runs.total;
});

test("V11-T092 Playwright FALSE_POSITIVE workflow", async ({ page }) => {
  await login(page);
  const incidentId = requiredIncidentId("S1");
  const evidenceBefore = await evidenceSnapshot(page, incidentId);
  const statusBefore = (await incidentDetail(page, incidentId)).incident.status;

  await page.goto(`/incidents/${incidentId}?tab=investigation`);
  await expect(page.getByRole("heading", { level: 1, name: "Investigation" })).toBeVisible();
  await recordDisposition(
    page,
    incidentId,
    "FALSE_POSITIVE",
    "Analyst review determined that this qualification did not represent the condition as initially interpreted; source evidence remains preserved.",
  );
  const afterDisposition = await incidentDetail(page, incidentId);
  expect(afterDisposition.incident.disposition).toBe("FALSE_POSITIVE");
  expect(afterDisposition.incident.status).toBe(statusBefore);

  await page.getByRole("tab", { name: "Report" }).click();
  await expect(page.getByRole("heading", { name: "Analyst report draft" })).toBeVisible();
  const reportRationale = "FALSE_POSITIVE rationale recorded separately from immutable evidence.";
  const reportConclusion =
    "FALSE_POSITIVE analyst conclusion; no source evidence was deleted or invalidated.";
  await page.getByLabel("Disposition Rationale").fill(reportRationale);
  await page.getByLabel("Final Conclusion").fill(reportConclusion);
  await saveReport(page, incidentId);
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText(reportRationale, { exact: true })).toBeVisible();
  await expect(page.getByText(reportConclusion, { exact: true })).toBeVisible();

  const evidenceAfter = await evidenceSnapshot(page, incidentId);
  expect(evidenceAfter).toEqual(evidenceBefore);

  await page.getByRole("tab", { name: "Investigation" }).click();
  const auditSection = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Authenticated incident audit trail" }),
  });
  await expect(auditSection.getByText("DISPOSITION CHANGED", { exact: true }).last()).toBeVisible();
  const audit = await getJson<IncidentAuditResponse>(
    page,
    `/api/v1/incidents/${encodeURIComponent(incidentId)}/audit`,
  );
  expect(
    audit.items.filter((item) => item.action === "DISPOSITION_CHANGED").length,
  ).toBeGreaterThanOrEqual(2);

  await page.goto("/reports?scope=HISTORY");
  await expect(page.getByRole("heading", { level: 1, name: "Reports" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Stored incident reports" })).toContainText(
    "FALSE_POSITIVE",
  );
  await expect(
    page.getByRole("img", {
      name: /Analyst disposition distribution.*False Positive\s+[1-9]/i,
    }),
  ).toBeVisible();
});

test("V11-T093 Playwright restart to Baseline", async ({ page }) => {
  await login(page);
  const before = await getJson<LabRunListResponse>(page, "/api/v1/lab/runs?limit=100");
  expect(before.total).toBeGreaterThanOrEqual(historyCountBeforeRestart || 5);
  for (const scenario of ["S1", "S2", "S3", "S4"]) {
    expect(before.items.some((run) => run.scenario_id === scenario)).toBe(true);
  }

  const repositoryRoot = path.resolve(import.meta.dirname, "..", "..");
  const restarted = spawnSync("docker", ["compose", "restart", "backend"], {
    cwd: repositoryRoot,
    encoding: "utf8",
    timeout: 120_000,
    windowsHide: true,
  });
  if (restarted.error || restarted.status !== 0) {
    throw new Error(
      `docker compose restart backend failed: ${restarted.error?.message ?? restarted.stderr ?? restarted.stdout}`,
    );
  }
  await waitForBackendReadiness();

  await page.context().clearCookies();
  await page.goto("/login");
  await login(page);
  await expect(page.locator(".top-header__run")).toContainText(/Active Scenario:\s*BASELINE/i);
  await expectKpi(page, "Open Incidents", "0");
  await expectKpi(page, "High Severity", "0");
  await expectKpi(page, "Denied Policy Findings", "0");
  await expectKpi(page, "Temporally Correlated", "0");

  const context = await getJson<LabContextResponse>(page, "/api/v1/lab/context");
  expect(context.active_run.scenario_id).toBe("BASELINE");
  expect(context.active_run.incident_count).toBe(0);
  const overview = await getJson<OverviewResponse>(page, "/api/v1/overview/summary");
  expect(overview.incidents.total).toBe(0);
  expect(overview.incidents.high).toBe(0);
  expect(overview.policy_findings.denied).toBe(0);
  expect(overview.correlations.correlated).toBe(0);

  const after = await getJson<LabRunListResponse>(page, "/api/v1/lab/runs?limit=100");
  expect(after.total).toBe(before.total);
  for (const scenario of ["S1", "S2", "S3", "S4"]) {
    expect(after.items.some((run) => run.scenario_id === scenario)).toBe(true);
  }

  await page.goto("/replay");
  await expect(
    page.getByRole("heading", { name: "Available Current-Run Incidents" }),
  ).toBeVisible();
  await expect(
    page.getByText("No current incidents exist in the selected run.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recent Historical Incidents" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open Replay" }).first()).toBeVisible();
});

function credentials(): { username: string; password: string } {
  const username = process.env.OTSOC_E2E_USERNAME?.trim();
  const password = process.env.OTSOC_E2E_PASSWORD;
  if (!username || !password) {
    throw new Error(
      "Playwright credentials were not provided through the required environment variables.",
    );
  }
  return { username, password };
}

async function login(page: Page): Promise<AuthSession> {
  const { username, password } = credentials();
  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByRole("textbox", { name: "Password", exact: true }).fill(password);
  const responsePromise = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/v1/auth/login" &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Sign In" }).click();
  const response = await responsePromise;
  expect(response.ok(), `Real local login returned HTTP ${response.status()}.`).toBeTruthy();
  await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
  const session = await getJson<AuthSession>(page, "/api/v1/auth/session");
  expect(session.authenticated).toBe(true);
  expect(session.user?.active).toBe(true);
  expect(session.user?.role, "The E2E account must be an ADMIN to run the allowlisted lab.").toBe(
    "ADMIN",
  );
  authenticatedDisplayName = session.user?.display_name ?? authenticatedDisplayName;
  return session;
}

async function openScenarioLab(page: Page) {
  await page.getByRole("button", { name: "Scenario Lab" }).click();
  const panel = page.getByRole("region", { name: "Synthetic Scenario Lab" });
  await expect(panel).toBeVisible();
  return panel;
}

async function startScenario(page: Page, scenario: ScenarioId): Promise<void> {
  await page.goto("/");
  const panel = await openScenarioLab(page);
  const scenarioIndex: Record<ScenarioId, number> = { S1: 1, S2: 2, S3: 3, S4: 4 };
  const cards = panel.locator(".scenario-catalog article");
  await expect(cards).toHaveCount(5);
  const card = cards.nth(scenarioIndex[scenario]);
  await expect(card.getByText(scenario, { exact: true })).toBeVisible();
  const responsePromise = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/v1/lab/start" &&
      response.request().method() === "POST",
  );
  await card.getByRole("button", { name: "Start Synthetic Scenario" }).click();
  const response = await responsePromise;
  expect(response.ok(), `${scenario} start returned HTTP ${response.status()}.`).toBeTruthy();
  await expect(panel.getByRole("status")).toContainText(
    `${scenario} completed with 1 resulting incident(s).`,
  );
  await expect(page.locator(".top-header__run")).toContainText(`Active Scenario: ${scenario}`);
  await panel.getByRole("button", { name: "Close Scenario Lab" }).click();
  await expect(
    page.getByText(new RegExp(`Current Run.*${scenario}.*COMPLETED`, "i")),
  ).toBeVisible();

  const context = await getJson<LabContextResponse>(page, "/api/v1/lab/context");
  expect(context.active_run.scenario_id).toBe(scenario);
  expect(context.active_run.status).toBe("COMPLETED");
  expect(context.active_run.incident_count).toBe(1);
}

async function openCurrentIncident(page: Page, scenario: ScenarioId): Promise<IncidentRecord> {
  const expected = SCENARIO_EXPECTATIONS[scenario];
  const list = await getJson<IncidentListResponse>(
    page,
    `/api/v1/incidents?scope=CURRENT&category=${expected.category}&limit=50`,
  );
  expect(list.items).toHaveLength(1);
  const incident = list.items[0]!;
  await page.goto(`/incidents?scope=CURRENT&category=${expected.category}`);
  const table = page.getByRole("region", { name: "Qualified incidents" });
  await expect(table).toBeVisible();
  const row = table.getByRole("row").filter({ hasText: expected.categoryLabel });
  await expect(row).toHaveCount(1);
  await row.getByRole("link").click();
  await expect(page.getByRole("heading", { level: 1, name: "Investigation" })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/incidents/${incident.incident_id}`));
  await expect(page.getByText(incident.category, { exact: true })).toBeVisible();
  return incident;
}

async function inspectEvidenceTab(page: Page, minimumEvidenceCount: number): Promise<void> {
  await page.getByRole("tab", { name: "Evidence" }).click();
  const table = page.getByRole("region", { name: "Incident evidence memberships" });
  await expect(table).toBeVisible();
  expect(await table.locator("tbody tr").count()).toBeGreaterThanOrEqual(minimumEvidenceCount);
  await expect(page.getByLabel("Verified evidence lineage")).toBeVisible();
}

async function verifyLinkedPlaybook(page: Page, scenario: ScenarioId): Promise<void> {
  await page.getByRole("tab", { name: "Overview" }).click();
  await page.getByRole("link", { name: "Open Recommended Playbook" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Playbooks" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: SCENARIO_EXPECTATIONS[scenario].playbook }),
  ).toBeVisible();
  await expect(page.locator(".exact-status").filter({ hasText: "ADVISORY ONLY" })).toBeVisible();
  await expect(
    page.getByLabel(`${scenario} analyst review checklist`).getByRole("checkbox"),
  ).toHaveCount(3);
  await expectForbiddenControlsAbsent(page);
  await page.getByRole("link", { name: "Return to Incident" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Investigation" })).toBeVisible();
}

async function completeSocWorkflow(
  page: Page,
  scenario: ScenarioId,
  disposition: Disposition,
  options: { xssSentinel?: boolean } = {},
): Promise<void> {
  const incidentId = requiredIncidentId(scenario);
  await page.goto(`/incidents/${incidentId}?tab=investigation`);
  await expectInvestigationControls(page);

  await performMutation(page, `/api/v1/incidents/${incidentId}/assignment`, "PATCH", async () => {
    await page.getByRole("button", { name: "Assign to me" }).click();
  });
  await reloadInvestigation(page);
  const assigned = await incidentDetail(page, incidentId);
  expect(assigned.incident).toHaveProperty("status");
  await expect(page.locator(".incident-hero__status")).toContainText(authenticatedDisplayName);

  const note = options.xssSentinel
    ? `<script>window.__otsocNoteExecuted=true</script> ${scenario} bounded analyst note.`
    : `${scenario} bounded analyst note using verified stored evidence only.`;
  await page.getByLabel("Add analyst note").fill(note);
  await performMutation(page, `/api/v1/incidents/${incidentId}/notes`, "POST", async () => {
    await page.getByRole("button", { name: "Add analyst note" }).click();
  });
  await reloadInvestigation(page);
  await expect(page.locator(".note-list")).toContainText(`${scenario} bounded analyst note`);
  await expect(page.locator(".note-list script")).toHaveCount(0);
  expect(await page.evaluate(() => Reflect.get(window, "__otsocNoteExecuted"))).toBeUndefined();

  await recordDisposition(
    page,
    incidentId,
    disposition,
    `${scenario} analyst rationale: the defined synthetic condition was reviewed without inferring an attacker, maliciousness, or causation.`,
  );

  await page.getByRole("tab", { name: "Report" }).click();
  await expect(page.getByRole("heading", { name: "Analyst report draft" })).toBeVisible();
  const fields = {
    "Investigation Summary": `${scenario} current-run incident investigated through verified stored evidence.`,
    "Analyst Assessment": `${scenario} assessment remains synthetic, offline, and causality-neutral.`,
    "Evidence Assessment": `${scenario} evidence lineage and integrity references were reviewed.`,
    "Process Impact Assessment": `${scenario} process impact is limited to the supported stored observations.`,
    "Disposition Rationale": `${disposition} means the defined synthetic qualification was reviewed; it is not proof of compromise.`,
    "Recommended Follow-up": `${scenario} follow-up is advisory review and documentation only.`,
    "Final Conclusion": options.xssSentinel
      ? `<img src=x onerror="document.documentElement.dataset.otsocUnsafe='true'"> ${scenario} final conclusion is plain text.`
      : `${scenario} final conclusion records the analyst decision without rewriting evidence.`,
  } as const;
  for (const [label, value] of Object.entries(fields)) {
    await page.getByLabel(label).fill(value);
  }
  await saveReport(page, incidentId);
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText(fields["Final Conclusion"], { exact: true })).toBeVisible();
  await expect(
    page.locator(".analyst-report-preview img, .analyst-report-preview script"),
  ).toHaveCount(0);
  await expect(page.locator("html")).not.toHaveAttribute("data-otsoc-unsafe", "true");
  await page.evaluate(() => {
    window.print = () => document.documentElement.setAttribute("data-print-invoked", "true");
  });
  await page.getByRole("button", { name: "Print" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-print-invoked", "true");

  await page.getByRole("tab", { name: "Investigation" }).click();
  await resolveIncident(page, incidentId, scenario);
  const completed = await incidentDetail(page, incidentId);
  expect(completed.incident.status).toBe("RESOLVED");
  expect(completed.incident.disposition).toBe(disposition);

  const audit = await getJson<IncidentAuditResponse>(
    page,
    `/api/v1/incidents/${encodeURIComponent(incidentId)}/audit`,
  );
  const actions = new Set(audit.items.map((item) => item.action));
  for (const action of [
    "ASSIGNMENT_CHANGED",
    "ANALYST_NOTE_ADDED",
    "DISPOSITION_CHANGED",
    "REPORT_SAVED",
    "STATUS_TRANSITIONED",
  ]) {
    expect(actions.has(action), `Incident audit is missing ${action}.`).toBe(true);
  }
  const auditSection = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Authenticated incident audit trail" }),
  });
  await expect(auditSection).toContainText("ASSIGNMENT CHANGED");
  await expect(auditSection).toContainText("DISPOSITION CHANGED");
  await expect(auditSection).toContainText("REPORT SAVED");
  await expect(auditSection).toContainText(authenticatedDisplayName);
}

async function expectInvestigationControls(page: Page): Promise<void> {
  await expect(page.getByRole("heading", { name: "Incident assignment" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Analyst disposition" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Lifecycle action" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Analyst notes" })).toBeVisible();
}

async function recordDisposition(
  page: Page,
  incidentId: string,
  disposition: Disposition,
  reason: string,
): Promise<void> {
  await expectInvestigationControls(page);
  await page.getByLabel("Disposition").selectOption(disposition);
  await page.getByLabel("Required analyst rationale").fill(reason);
  await performMutation(page, `/api/v1/incidents/${incidentId}/disposition`, "PATCH", async () => {
    await page.getByRole("button", { name: "Record disposition" }).click();
  });
  await reloadInvestigation(page);
  await expect(page.locator(".incident-hero__status")).toContainText(disposition);
}

async function resolveIncident(
  page: Page,
  incidentId: string,
  scenario: ScenarioId,
): Promise<void> {
  let status = (await incidentDetail(page, incidentId)).incident.status;
  if (status === "RESOLVED") {
    await transitionIncident(
      page,
      incidentId,
      "INVESTIGATING",
      `${scenario} reopened by the deterministic E2E workflow for authenticated review.`,
    );
    status = "INVESTIGATING";
  }
  if (status === "OPEN") {
    await transitionIncident(
      page,
      incidentId,
      "INVESTIGATING",
      `${scenario} entered authenticated analyst investigation.`,
    );
  }
  await transitionIncident(
    page,
    incidentId,
    "RESOLVED",
    `${scenario} analyst workflow completed with preserved evidence and a saved conclusion.`,
  );
}

async function transitionIncident(
  page: Page,
  incidentId: string,
  next: "INVESTIGATING" | "RESOLVED",
  reason: string,
): Promise<void> {
  await expectInvestigationControls(page);
  await page.getByLabel("Approved next status").selectOption(next);
  await page.getByLabel(/^Reason/).fill(reason);
  await performMutation(page, `/api/v1/incidents/${incidentId}/status`, "PATCH", async () => {
    await page.getByRole("button", { name: "Update lifecycle status" }).click();
  });
  await reloadInvestigation(page);
  expect((await incidentDetail(page, incidentId)).incident.status).toBe(next);
}

async function saveReport(page: Page, incidentId: string): Promise<void> {
  await performMutation(page, `/api/v1/incidents/${incidentId}/report`, "PUT", async () => {
    await page.getByRole("button", { name: "Save Draft" }).click();
  });
  await expect(page.getByRole("status")).toContainText("Analyst report draft saved");
}

async function performMutation(
  page: Page,
  pathname: string,
  method: string,
  action: () => Promise<void>,
): Promise<void> {
  const responsePromise = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === pathname && response.request().method() === method,
  );
  await action();
  const response = await responsePromise;
  const body = await response.text();
  expect(
    response.ok(),
    `${method} ${pathname} returned HTTP ${response.status()}: ${body}`,
  ).toBeTruthy();
}

async function reloadInvestigation(page: Page): Promise<void> {
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Investigation" })).toBeVisible();
  await expectInvestigationControls(page);
}

async function incidentDetail(page: Page, incidentId: string): Promise<IncidentDetailResponse> {
  return getJson<IncidentDetailResponse>(
    page,
    `/api/v1/incidents/${encodeURIComponent(incidentId)}`,
  );
}

async function incidentEvidence(page: Page, incidentId: string): Promise<EvidenceRecord[]> {
  const detail = await incidentDetail(page, incidentId);
  return Promise.all(
    detail.evidence_memberships.map((membership) =>
      getJson<EvidenceRecord>(
        page,
        `/api/v1/evidence/${encodeURIComponent(membership.evidence_id)}`,
      ),
    ),
  );
}

async function replayEvidence(page: Page, incidentId: string): Promise<EvidenceRecord[]> {
  const replay = await getJson<ReplayResponse>(
    page,
    `/api/v1/replay?incident_id=${encodeURIComponent(incidentId)}`,
  );
  return replay.events.flatMap((event) => (event.evidence ? [event.evidence] : []));
}

async function evidenceSnapshot(
  page: Page,
  incidentId: string,
): Promise<{ evidenceId: string; integritySha256: string }[]> {
  const evidence = await incidentEvidence(page, incidentId);
  return evidence
    .map((item) => ({ evidenceId: item.evidence_id, integritySha256: item.integrity_sha256 }))
    .sort((left, right) => left.evidenceId.localeCompare(right.evidenceId));
}

async function expectKpi(page: Page, label: string, value: string): Promise<void> {
  const card = page.locator(".kpi-card").filter({ hasText: label });
  await expect(card).toHaveCount(1);
  await expect(card.locator("strong")).toHaveText(value);
}

async function expectForbiddenControlsAbsent(page: Page): Promise<void> {
  if (page.isClosed()) return;
  await expect(
    page.getByRole("button", {
      name: /execute playbook|send modbus|transmit|scan|capture|inject|isolate|contain|shutdown|stop pump|start pump|open valve|close valve|block traffic/i,
    }),
  ).toHaveCount(0);
}

async function getJson<T>(page: Page, url: string): Promise<T> {
  const response = await page.request.get(url);
  const body = await response.text();
  expect(response.ok(), `GET ${url} returned HTTP ${response.status()}: ${body}`).toBeTruthy();
  return JSON.parse(body) as T;
}

function requiredIncidentId(scenario: ScenarioId): string {
  const incidentId = scenarioIncidents[scenario];
  if (!incidentId)
    throw new Error(`${scenario} incident state is unavailable from the serial journey.`);
  return incidentId;
}

async function waitForBackendReadiness(): Promise<void> {
  const deadline = Date.now() + 120_000;
  let lastError = "no response";
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${BACKEND_URL}/health/ready`, {
        signal: AbortSignal.timeout(5_000),
      });
      if (response.ok) {
        const body = (await response.json()) as { status?: string };
        if (body.status === "ready") return;
        lastError = `readiness status ${String(body.status)}`;
      } else {
        lastError = `HTTP ${response.status}`;
      }
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }
  throw new Error(`Backend did not become ready after restart: ${lastError}`);
}
