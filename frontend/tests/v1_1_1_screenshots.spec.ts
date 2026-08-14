import { mkdir, readdir, stat, unlink, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

type ScenarioId = "BASELINE" | "S1" | "S2" | "S3" | "S4";
type Disposition = "TRUE_POSITIVE" | "FALSE_POSITIVE";

interface AuthSession {
  authenticated: boolean;
  user: { user_id: string; display_name: string; role: string; active: boolean } | null;
}

interface IncidentRecord {
  incident_id: string;
  title: string;
  category: string;
  severity: string;
  disposition: "UNREVIEWED" | Disposition;
  version: number;
  s3_semantic_evidence_id?: string | null;
}

interface IncidentListResponse {
  items: IncidentRecord[];
}

interface IncidentDetailResponse {
  incident: IncidentRecord;
  evidence_memberships: { evidence_id: string; integrity_sha256: string }[];
}

interface EvidenceRecord {
  evidence_id: string;
  evidence_type: string;
  payload: Record<string, unknown>;
}

interface ReplayResponse {
  events: { evidence: EvidenceRecord | null }[];
}

interface CaptureRecord {
  number: number;
  filename: string;
  width: number;
  height: number;
  size: number;
  capturedAt: string;
  route: string;
  page: string;
  scenario: ScenarioId | "AUTH" | "HISTORY";
  visible: string;
  proves: string;
  reportSection: string;
}

const FRONTEND_URL = process.env.OTSOC_E2E_BASE_URL ?? "http://127.0.0.1:5173";
const BACKEND_URL = process.env.OTSOC_E2E_BACKEND_URL ?? "http://127.0.0.1:8000";
const EVIDENCE_ROOT =
  process.env.OTSOC_EVIDENCE_ROOT ?? path.resolve("test-results", "screenshot-validation");
const SCREENSHOT_DIR = path.join(EVIDENCE_ROOT, "screenshots");
const REPORT_DIR = path.join(EVIDENCE_ROOT, "reports");
const LOG_DIR = path.join(EVIDENCE_ROOT, "logs");
const VIEWPORT = { width: 1920, height: 1080 } as const;
const ALLOWED_ORIGINS = new Set([new URL(FRONTEND_URL).origin, new URL(BACKEND_URL).origin]);
const captures: CaptureRecord[] = [];
const visualResults = new Map<string, "PASS" | "FAIL">();
const consoleErrors: string[] = [];
const expectedAuthenticationWarnings: string[] = [];
const failedRequests: string[] = [];
const abortedNavigationRequests: string[] = [];
const externalRequests: string[] = [];
const incidentIds = new Map<ScenarioId, string>();

test.use({ viewport: VIEWPORT });
test.describe.configure({ mode: "serial" });
test.setTimeout(600_000);

test.beforeAll(async () => {
  await Promise.all([
    mkdir(SCREENSHOT_DIR, { recursive: true }),
    mkdir(REPORT_DIR, { recursive: true }),
    mkdir(LOG_DIR, { recursive: true }),
  ]);
  for (const filename of await readdir(SCREENSHOT_DIR)) {
    if (/^\d{2}-[a-z0-9-]+\.png$/u.test(filename)) {
      await unlink(path.join(SCREENSHOT_DIR, filename));
    }
  }
});

test.afterAll(async () => {
  await writeEvidenceReports();
});

test("v1.1.1 real-stack academic report evidence", async ({ page }) => {
  monitorBrowser(page);

  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "OT-SOC Fusion X" })).toBeVisible();
  await expect(page.getByLabel("Username")).toHaveValue("");
  await expect(page.getByRole("textbox", { name: "Password", exact: true })).toHaveValue("");
  await capture(
    page,
    "01-login.png",
    "Login",
    "AUTH",
    "Empty local login form and offline branding",
    "Unauthenticated entry point without any entered credential",
    "Authentication",
  );

  const session = await login(page);
  expect(session.user?.role).toBe("ADMIN");
  await returnToBaseline(page);

  await page.goto("/");
  await expect(page.locator(".top-header__run")).toContainText(/Active Scenario:\s*BASELINE/i);
  await expectKpi(page, "Open Incidents", "0");
  await expectKpi(page, "High Severity", "0");
  await expectKpi(page, "Denied Policy Findings", "0");
  await expectKpi(page, "Temporally Correlated", "0");
  await capture(
    page,
    "02-overview-baseline.png",
    "Overview",
    "BASELINE",
    "Baseline context, zero incident KPIs, health, process schematic, and normal metrics",
    "Clean current-run Baseline",
    "SOC Dashboard",
  );

  await gotoProductPage(page, "/incidents?scope=CURRENT", "Incidents");
  await expect(
    page.getByRole("heading", { name: "No current incidents in Baseline" }),
  ).toBeVisible();
  await capture(
    page,
    "03-incidents-baseline.png",
    "Incidents",
    "BASELINE",
    "Current-run filter and empty Baseline incident queue",
    "Historical incidents are not presented as current",
    "Incident Management",
  );

  await gotoProductPage(page, "/protocol-analysis", "Protocol Analysis");
  await capture(
    page,
    "04-protocol-analysis-baseline.png",
    "Protocol Analysis",
    "BASELINE",
    "Stored Baseline protocol evidence and read-only boundary",
    "Protocol analysis is bounded to stored evidence",
    "Protocol Analysis",
  );

  await gotoProductPage(page, "/digital-twin", "Digital Twin");
  await expect(page.locator(".process-node")).toHaveCount(5);
  await capture(
    page,
    "05-digital-twin-baseline.png",
    "Digital Twin",
    "BASELINE",
    "Normal TK-101, P-101, PL-101, CV-101, and TK-102 process context",
    "Baseline Digital Twin is readable and control-free",
    "Digital Twin",
  );

  await gotoProductPage(page, "/assets", "Asset Inventory");
  await expect(page.getByText("11 of 11 approved assets", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Synthetic asset inventory").locator("tbody tr")).toHaveCount(11);
  await capture(
    page,
    "06-asset-inventory.png",
    "Asset Inventory",
    "BASELINE",
    "Exact 11-asset inventory, cyber/process distribution, zones, and topology",
    "Six cyber and five process assets use approved static context",
    "Asset/Policy Context",
  );

  await gotoProductPage(page, "/replay", "Replay");
  await expect(page.getByRole("heading", { name: "Recent Historical Incidents" })).toBeVisible();
  await capture(
    page,
    "07-replay-landing.png",
    "Replay",
    "BASELINE",
    "Current-run and historical stored-evidence selectors",
    "Replay selection preserves current/history separation",
    "Replay",
  );

  await gotoProductPage(page, "/playbooks", "Playbooks");
  await expect(page.locator(".playbook-list > button")).toHaveCount(4);
  await capture(
    page,
    "08-playbooks.png",
    "Playbooks",
    "BASELINE",
    "Four advisory review guides and advisory-only language",
    "Playbooks cannot execute or contain",
    "SOC Analyst Workflow",
  );

  await gotoProductPage(page, "/reports?scope=CURRENT", "Reports");
  await capture(
    page,
    "09-reports-baseline.png",
    "Reports",
    "BASELINE",
    "Baseline/current report analytics and stored-report state",
    "Reports are based on persisted incident data",
    "Results",
  );

  await gotoProductPage(page, "/settings", "Settings");
  await expect(page.getByRole("heading", { name: "Local Account" })).toBeVisible();
  await capture(
    page,
    "10-settings-account.png",
    "Settings",
    "BASELINE",
    "Authenticated account, session, application, and local system context",
    "Settings exposes no credential hash or session secret",
    "Authentication",
  );

  await page.goto("/");
  const lab = await openScenarioLab(page);
  await expect(lab.locator(".scenario-catalog article")).toHaveCount(5);
  expect(await lab.locator(".scenario-catalog article > span").allTextContents()).toEqual([
    "BASELINE",
    "S1",
    "S2",
    "S3",
    "S4",
  ]);
  await expect(lab.locator("input, textarea, select")).toHaveCount(0);
  await capture(
    page,
    "11-scenario-lab.png",
    "Scenario Lab",
    "BASELINE",
    "Exact Baseline/S1-S4 catalog and bounded run history",
    "No arbitrary target, register, packet, or payload can be supplied",
    "Scenario Lab",
  );
  await lab.getByRole("button", { name: "Close Scenario Lab" }).click();

  await startScenario(page, "S1");
  const s1 = await openCurrentIncident(page, "S1", "ASSET_IDENTITY_ANOMALY");
  incidentIds.set("S1", s1.incident_id);
  await expect(page.getByText("LOW", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/SOURCE_UNKNOWN|UNKNOWN/u).first()).toBeVisible();
  await capture(
    page,
    "12-s1-incident.png",
    "Incident Workspace",
    "S1",
    "LOW asset-identity anomaly with unknown/source-unknown context",
    "S1 makes no compromise or guessed-identity claim",
    "Scenario Validation",
  );
  await returnToBaseline(page);

  await startScenario(page, "S2");
  const s2 = await openCurrentIncident(page, "S2", "COMMUNICATION_POLICY_VIOLATION");
  incidentIds.set("S2", s2.incident_id);
  await expect(page.getByText("MEDIUM", { exact: true }).first()).toBeVisible();
  const s2Replay = await getJson<ReplayResponse>(
    page,
    `/api/v1/replay?incident_id=${encodeURIComponent(s2.incident_id)}`,
  );
  const s2Policy = s2Replay.events
    .map((event) => event.evidence)
    .find((evidence) => evidence?.evidence_type === "communication_policy_finding");
  expect(s2Policy?.payload.policy_status).toBe("DENIED");
  expect(s2Policy?.payload.reason_code).toBe("COMMUNICATION_NOT_APPROVED");
  await gotoProductPage(
    page,
    `/protocol-analysis?evidence=${encodeURIComponent(s2Policy!.evidence_id)}`,
    "Protocol Analysis",
  );
  await expect(page.locator(".exact-status").filter({ hasText: "DENIED" })).toBeVisible();
  await expect(page.getByText(/does not establish maliciousness/i)).toBeVisible();
  await page.getByText("Typed payload and provenance", { exact: true }).click();
  await expect(page.locator(".json-view")).toContainText("COMMUNICATION_NOT_APPROVED");
  await capture(
    page,
    "13-s2-policy-incident.png",
    "Incident Workspace",
    "S2",
    "MEDIUM communication-policy violation with DENIED policy context",
    "DENIED is shown as policy non-approval, not maliciousness",
    "Asset/Policy Context",
  );
  await returnToBaseline(page);

  await startScenario(page, "S3");
  await page.goto("/");
  await expect(page.locator(".top-header__run")).toContainText(/Active Scenario:\s*S3/i);
  await capture(
    page,
    "14-s3-overview.png",
    "Overview",
    "S3",
    "Active S3 context with coherent incident and process metrics",
    "Current dashboard changes with the selected synthetic run",
    "SOC Dashboard",
  );

  const s3 = await openCurrentIncident(page, "S3", "CONTROL_COMMAND_INVESTIGATION");
  incidentIds.set("S3", s3.incident_id);
  await expect(page.getByText("HIGH", { exact: true }).first()).toBeVisible();
  await capture(
    page,
    "15-s3-incident-workspace.png",
    "Incident Workspace",
    "S3",
    "HIGH control-command investigation, triage state, disposition, and evidence links",
    "Primary S3 incident investigation workspace",
    "Incident Management",
  );

  await page.goto(`/incidents/${s3.incident_id}?tab=investigation`);
  await expectInvestigation(page);
  await mutate(page, `/api/v1/incidents/${s3.incident_id}/assignment`, "PATCH", async () =>
    page.getByRole("button", { name: "Assign to me" }).click(),
  );
  await page.reload();
  await expectInvestigation(page);

  const s3Detail = await getJson<IncidentDetailResponse>(
    page,
    `/api/v1/incidents/${s3.incident_id}`,
  );
  expect(s3Detail.incident.s3_semantic_evidence_id).toBeTruthy();
  await gotoProductPage(
    page,
    `/protocol-analysis?evidence=${encodeURIComponent(s3Detail.incident.s3_semantic_evidence_id!)}`,
    "Protocol Analysis",
  );
  for (const text of ["6", "holding_register", "250", "CV-101", "25.0 % open"] as const) {
    await expect(page.getByText(text, { exact: false }).first()).toBeVisible();
  }
  await capture(
    page,
    "16-s3-protocol-raw-semantic.png",
    "Protocol Analysis",
    "S3",
    "RAW FC06 offset 1 value 250 beside semantic CV-101 at 25.0%",
    "Frozen S3 protocol golden path and provenance",
    "Protocol Analysis",
  );

  await page.goto(`/incidents/${s3.incident_id}?tab=evidence`);
  await expect(page.getByLabel("Verified evidence lineage")).toBeVisible();
  await page.getByLabel("Verified evidence lineage").scrollIntoViewIfNeeded();
  await capture(
    page,
    "17-s3-correlation-lineage.png",
    "Evidence Lineage",
    "S3",
    "Evidence membership and verified raw-to-incident lineage",
    "Correlation and process context remain evidence-linked and causality-neutral",
    "Cyber-Physical Correlation",
  );

  await gotoProductPage(page, `/digital-twin?incident=${s3.incident_id}`, "Digital Twin");
  await expect(page.locator(".process-node")).toHaveCount(5);
  await expect(page.getByText("P-101 Pump Command", { exact: true })).toBeVisible();
  await expect(page.getByText("P-101 Pump Running State", { exact: true })).toBeVisible();
  await capture(
    page,
    "18-s3-digital-twin.png",
    "Digital Twin",
    "S3",
    "Five-node process path with command, observed state, flow, pressure, and tank effects",
    "Cyber-physical context is separated and read-only",
    "Digital Twin",
  );

  await gotoProductPage(page, `/replay?incident=${s3.incident_id}`, "Replay");
  const scrub = page.getByLabel("Replay timeline scrub");
  const max = Number(await scrub.getAttribute("max"));
  await scrub.fill(String(Math.max(0, Math.floor(max * 0.7))));
  await expect(page.getByText(/Selected event/u).first()).toBeVisible();
  await capture(
    page,
    "19-s3-replay.png",
    "Replay",
    "S3",
    "Deterministic timeline, selected event, cursor-synchronized metrics, and process context",
    "Replay uses stored evidence without mutation",
    "Replay",
  );

  await gotoProductPage(page, `/playbooks?type=S3&incident=${s3.incident_id}`, "Playbooks");
  await expect(page.getByRole("heading", { name: "Control Command Investigation" })).toBeVisible();
  await expect(page.locator(".exact-status").filter({ hasText: "ADVISORY ONLY" })).toBeVisible();
  await capture(
    page,
    "20-s3-advisory-playbook.png",
    "Playbooks",
    "S3",
    "S3 advisory review guide and browser-local checklist",
    "No execute, containment, or process action is available",
    "SOC Analyst Workflow",
  );

  await page.goto(`/incidents/${s3.incident_id}?tab=investigation`);
  await expectInvestigation(page);
  await page
    .getByLabel("Add analyst note")
    .fill("Final validation review completed for the synthetic S3 investigation.");
  await mutate(page, `/api/v1/incidents/${s3.incident_id}/notes`, "POST", async () =>
    page.getByRole("button", { name: "Add analyst note" }).click(),
  );
  await page.reload();
  await expectInvestigation(page);
  await recordDisposition(
    page,
    s3.incident_id,
    "TRUE_POSITIVE",
    "The stored evidence matches the defined synthetic S3 control-command investigation condition. This disposition does not establish real-world malicious intent or causation.",
  );
  await capture(
    page,
    "21-s3-true-positive.png",
    "Incident Investigation",
    "S3",
    "TRUE_POSITIVE, bounded rationale, assignee, and separate lifecycle state",
    "Defined synthetic detection is distinguished from maliciousness and causation",
    "SOC Analyst Workflow",
  );

  await page.getByRole("tab", { name: "Report" }).click();
  await expect(page.getByRole("heading", { name: "Analyst report draft" })).toBeVisible();
  const reportFields = {
    "Investigation Summary":
      "Synthetic S3 investigation reviewed through the verified protocol, asset, policy, correlation, process, and incident evidence path.",
    "Analyst Assessment":
      "The defined synthetic S3 condition was correctly detected; this does not identify a real attacker.",
    "Evidence Assessment":
      "FC06 Holding Register offset 1 raw value 250 maps to CV-101 at 25.0%, with policy, telemetry, and temporal-correlation evidence preserved.",
    "Process Impact Assessment":
      "Stored synthetic telemetry shows the bounded flow, pressure, valve-position, and tank response; no real-plant impact is claimed.",
    "Disposition Rationale":
      "TRUE_POSITIVE records correct detection of the defined synthetic condition, not proof of maliciousness or causation.",
    "Recommended Follow-up":
      "Continue advisory evidence review, documentation, and academic analysis only; perform no PLC or process-control action.",
    "Final Conclusion":
      "Stored evidence supports the defined academic S3 condition. Temporal correlation is not causation, and DENIED is not proof of maliciousness.",
  } as const;
  for (const [label, value] of Object.entries(reportFields))
    await page.getByLabel(label).fill(value);
  await mutate(page, `/api/v1/incidents/${s3.incident_id}/report`, "PUT", async () =>
    page.getByRole("button", { name: "Save Draft" }).click(),
  );
  await page.getByRole("heading", { name: "Analyst report draft" }).scrollIntoViewIfNeeded();
  await capture(
    page,
    "22-s3-incident-report-editor.png",
    "Incident Report Editor",
    "S3",
    "Completed seven-field factual synthetic incident report",
    "Authenticated analyst report authoring",
    "Incident Reporting",
  );

  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText(reportFields["Final Conclusion"], { exact: true })).toBeVisible();
  await expect(
    page.locator(".analyst-report-preview script, .analyst-report-preview img"),
  ).toHaveCount(0);
  await capture(
    page,
    "23-s3-incident-report-preview.png",
    "Incident Report Preview",
    "S3",
    "Safe printable report preview with completed factual sections",
    "Report content is safely rendered and report-ready",
    "Incident Reporting",
  );

  await page.getByRole("tab", { name: "Investigation" }).click();
  const audit = page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: "Authenticated incident audit trail" }) });
  await expect(audit).toContainText("ASSIGNMENT CHANGED");
  await expect(audit).toContainText("DISPOSITION CHANGED");
  await expect(audit).toContainText("REPORT SAVED");
  await audit.scrollIntoViewIfNeeded();
  await capture(
    page,
    "24-s3-audit-trail.png",
    "Incident Audit",
    "S3",
    "Authenticated assignment, note, disposition, and report audit history",
    "SOC actions are attributable and retained",
    "SOC Analyst Workflow",
  );

  const s1Id = incidentIds.get("S1")!;
  const beforeFalsePositive = await evidenceSnapshot(page, s1Id);
  await page.goto(`/incidents/${s1Id}?tab=investigation`);
  await expectInvestigation(page);
  await recordDisposition(
    page,
    s1Id,
    "FALSE_POSITIVE",
    "Academic validation records this historical S1 investigation as FALSE_POSITIVE while retaining all source evidence and qualification history.",
  );
  expect(await evidenceSnapshot(page, s1Id)).toEqual(beforeFalsePositive);
  await capture(
    page,
    "25-false-positive-workflow.png",
    "Incident Investigation",
    "HISTORY",
    "FALSE_POSITIVE rationale with historical incident and preserved evidence state",
    "Disposition does not delete or rewrite evidence",
    "SOC Analyst Workflow",
  );

  await returnToBaseline(page);
  await startScenario(page, "S4");
  const s4 = await openCurrentIncident(page, "S4", "PROCESS_INCONSISTENCY");
  incidentIds.set("S4", s4.incident_id);
  await expect(page.getByText("HIGH", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/no cyber cause|process-only|causality/iu).first()).toBeVisible();
  await capture(
    page,
    "26-s4-incident.png",
    "Incident Workspace",
    "S4",
    "HIGH process inconsistency with pump-running/low-flow context",
    "S4 remains process-only with no invented cyber cause",
    "Scenario Validation",
  );

  await gotoProductPage(page, `/digital-twin?incident=${s4.incident_id}`, "Digital Twin");
  await expect(page.getByText("P-101 Pump Running State", { exact: true })).toBeVisible();
  await capture(
    page,
    "27-s4-digital-twin.png",
    "Digital Twin",
    "S4",
    "Pump-running state, low-flow process inconsistency, and process metrics",
    "Process state is visualized without control actions",
    "Digital Twin",
  );

  await gotoProductPage(page, `/replay?incident=${s4.incident_id}`, "Replay");
  await expect(page.getByText(/process/i).first()).toBeVisible();
  await capture(
    page,
    "28-s4-replay.png",
    "Replay",
    "S4",
    "Stored S4 process-only timeline and selected evidence",
    "Replay contains no fabricated cyber parent",
    "Replay",
  );

  await gotoProductPage(page, "/reports?scope=HISTORY", "Reports");
  await expect(page.getByRole("heading", { name: "Incident Reports" })).toBeVisible();
  await capture(
    page,
    "29-reports-final.png",
    "Reports",
    "HISTORY",
    "Severity, status, category, disposition, affected assets, and stored reports",
    "Analytics reflect actual accumulated synthetic analyst activity",
    "Results",
  );

  await gotoProductPage(page, "/incidents?scope=HISTORY", "Incidents");
  await expect(page.getByRole("region", { name: "Qualified incidents" })).toBeVisible();
  await capture(
    page,
    "30-incidents-history.png",
    "Incidents",
    "HISTORY",
    "All-history queue with scenario investigations and scope controls",
    "Historical incidents remain distinct from current Baseline",
    "Incident Management",
  );

  await returnToBaseline(page);
  await page.goto("/");
  await expectKpi(page, "Open Incidents", "0");
  await expectKpi(page, "High Severity", "0");
  await capture(
    page,
    "31-final-baseline.png",
    "Overview",
    "BASELINE",
    "Final clean Baseline with zero current incidents and retained synthetic context",
    "Validation leaves the active product in clean Baseline",
    "Results",
  );

  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page).toHaveURL(/\/login(?:\?.*)?$/u);
  await expect(page.getByRole("textbox", { name: "Password", exact: true })).toHaveValue("");
  await capture(
    page,
    "32-logout-login-return.png",
    "Login",
    "AUTH",
    "Empty login page after authenticated logout",
    "Logout invalidates the protected product session",
    "Authentication",
  );

  expect(captures).toHaveLength(32);
  expect(expectedAuthenticationWarnings).toHaveLength(2);
  expect(consoleErrors, "Unexpected browser console errors").toEqual([]);
  expect(failedRequests, "Unexpected failed local application requests").toEqual([]);
  expect(externalRequests, "Unexpected external runtime requests").toEqual([]);
  expect([...visualResults.values()].every((result) => result === "PASS")).toBe(true);
});

function credentials(): { username: string; password: string } {
  const username = process.env.OTSOC_E2E_USERNAME?.trim();
  const password = process.env.OTSOC_E2E_PASSWORD;
  if (!username || !password)
    throw new Error("Set OTSOC_E2E_USERNAME and OTSOC_E2E_PASSWORD for local evidence capture.");
  return { username, password };
}

function monitorBrowser(page: Page): void {
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    if (
      message.text() ===
      "Failed to load resource: the server responded with a status of 401 (Unauthorized)"
    ) {
      expectedAuthenticationWarnings.push(message.text());
      return;
    }
    consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    const failure = request.failure()?.errorText ?? "unknown failure";
    const finding = `${request.method()} ${request.url()} :: ${failure}`;
    if (failure === "net::ERR_ABORTED") {
      abortedNavigationRequests.push(finding);
      return;
    }
    failedRequests.push(finding);
  });
  page.on("request", (request) => {
    const url = request.url();
    if (url.startsWith("data:") || url.startsWith("blob:")) return;
    if (!ALLOWED_ORIGINS.has(new URL(url).origin)) externalRequests.push(url);
  });
}

async function login(page: Page): Promise<AuthSession> {
  const { username, password } = credentials();
  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByRole("textbox", { name: "Password", exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
  const session = await getJson<AuthSession>(page, "/api/v1/auth/session");
  expect(session.authenticated).toBe(true);
  expect(session.user?.active).toBe(true);
  return session;
}

async function openScenarioLab(page: Page) {
  await page.getByRole("button", { name: "Scenario Lab" }).click();
  const panel = page.getByRole("region", { name: "Synthetic Scenario Lab" });
  await expect(panel).toBeVisible();
  return panel;
}

async function returnToBaseline(page: Page): Promise<void> {
  await page.goto("/");
  const panel = await openScenarioLab(page);
  const baselineButton = panel.getByRole("button", { name: "Return to Baseline" });
  if (await baselineButton.isEnabled()) {
    const response = page.waitForResponse(
      (item) =>
        new URL(item.url()).pathname === "/api/v1/lab/baseline" &&
        item.request().method() === "POST",
    );
    await baselineButton.click();
    expect((await response).ok()).toBe(true);
  }
  await expect(page.locator(".top-header__run")).toContainText(/Active Scenario:\s*BASELINE/i);
  await panel.getByRole("button", { name: "Close Scenario Lab" }).click();
}

async function startScenario(page: Page, scenario: Exclude<ScenarioId, "BASELINE">): Promise<void> {
  await page.goto("/");
  const panel = await openScenarioLab(page);
  const index = { S1: 1, S2: 2, S3: 3, S4: 4 }[scenario];
  const card = panel.locator(".scenario-catalog article").nth(index);
  const response = page.waitForResponse(
    (item) =>
      new URL(item.url()).pathname === "/api/v1/lab/start" && item.request().method() === "POST",
  );
  await card.getByRole("button", { name: "Start Synthetic Scenario" }).click();
  expect((await response).ok()).toBe(true);
  await expect(panel.getByRole("status")).toContainText(
    `${scenario} completed with 1 resulting incident(s).`,
  );
  await expect(page.locator(".top-header__run")).toContainText(`Active Scenario: ${scenario}`);
  await panel.getByRole("button", { name: "Close Scenario Lab" }).click();
}

async function openCurrentIncident(
  page: Page,
  scenario: Exclude<ScenarioId, "BASELINE">,
  category: string,
): Promise<IncidentRecord> {
  const list = await getJson<IncidentListResponse>(
    page,
    `/api/v1/incidents?scope=CURRENT&category=${category}&limit=50`,
  );
  expect(list.items).toHaveLength(1);
  const incident = list.items[0]!;
  await page.goto(`/incidents/${incident.incident_id}`);
  await expect(page.getByRole("heading", { level: 1, name: "Investigation" })).toBeVisible();
  await expect(page.getByText(category, { exact: true })).toBeVisible();
  await expect(page.locator(".top-header__run")).toContainText(`Active Scenario: ${scenario}`);
  await waitForStablePage(page);
  return incident;
}

async function expectInvestigation(page: Page): Promise<void> {
  await expect(page.getByRole("heading", { name: "Incident assignment" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Analyst disposition" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Analyst notes" })).toBeVisible();
}

async function recordDisposition(
  page: Page,
  incidentId: string,
  disposition: Disposition,
  rationale: string,
): Promise<void> {
  await page.getByLabel("Disposition").selectOption(disposition);
  await page.getByLabel("Required analyst rationale").fill(rationale);
  await mutate(page, `/api/v1/incidents/${incidentId}/disposition`, "PATCH", async () =>
    page.getByRole("button", { name: "Record disposition" }).click(),
  );
  await page.reload();
  await expectInvestigation(page);
  await expect(page.locator(".incident-hero__status")).toContainText(disposition);
}

async function evidenceSnapshot(
  page: Page,
  incidentId: string,
): Promise<{ evidenceId: string; integrity: string }[]> {
  const detail = await getJson<IncidentDetailResponse>(page, `/api/v1/incidents/${incidentId}`);
  return detail.evidence_memberships
    .map((item) => ({ evidenceId: item.evidence_id, integrity: item.integrity_sha256 }))
    .sort((left, right) => left.evidenceId.localeCompare(right.evidenceId));
}

async function mutate(
  page: Page,
  pathname: string,
  method: string,
  action: () => Promise<void>,
): Promise<void> {
  const response = page.waitForResponse(
    (item) => new URL(item.url()).pathname === pathname && item.request().method() === method,
  );
  await action();
  const result = await response;
  expect(
    result.ok(),
    `${method} ${pathname} returned HTTP ${result.status()}: ${await result.text()}`,
  ).toBe(true);
}

async function gotoProductPage(page: Page, route: string, heading: string): Promise<void> {
  await page.goto(route);
  await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  await waitForStablePage(page);
}

async function waitForStablePage(page: Page): Promise<void> {
  await expect(page.locator(".loading-skeleton")).toHaveCount(0);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(250);
}

async function expectKpi(page: Page, label: string, value: string): Promise<void> {
  const card = page.locator(".kpi-card").filter({ hasText: label });
  await expect(card).toHaveCount(1);
  await expect(card.locator("strong")).toHaveText(value);
}

async function capture(
  page: Page,
  filename: string,
  pageName: string,
  scenario: CaptureRecord["scenario"],
  visible: string,
  proves: string,
  reportSection: string,
): Promise<void> {
  await waitForStablePage(page);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, `${pageName} has document-level horizontal overflow`).toBeLessThanOrEqual(1);
  visualResults.set(pageName, "PASS");
  const output = path.join(SCREENSHOT_DIR, filename);
  await page.screenshot({ path: output, animations: "disabled", fullPage: false });
  const file = await stat(output);
  captures.push({
    number: Number(filename.slice(0, 2)),
    filename,
    width: VIEWPORT.width,
    height: VIEWPORT.height,
    size: file.size,
    capturedAt: new Date().toISOString(),
    route: new URL(page.url()).pathname + new URL(page.url()).search,
    page: pageName,
    scenario,
    visible,
    proves,
    reportSection,
  });
}

async function getJson<T>(page: Page, url: string): Promise<T> {
  const response = await page.request.get(url);
  const text = await response.text();
  expect(response.ok(), `GET ${url} returned HTTP ${response.status()}: ${text}`).toBe(true);
  return JSON.parse(text) as T;
}

async function writeEvidenceReports(): Promise<void> {
  const index = [
    "# OT-SOC Fusion X v1.1.1 Screenshot Index",
    "",
    `Captured: ${captures.length} PNG files at ${VIEWPORT.width} x ${VIEWPORT.height}.`,
    "",
    "| Number | Filename | Page | Scenario | What is visible | What it proves | Recommended graduation-report section |",
    "|---:|---|---|---|---|---|---|",
    ...captures
      .sort((left, right) => left.number - right.number)
      .map(
        (item) =>
          `| ${item.number} | \`${item.filename}\` | ${item.page} | ${item.scenario} | ${item.visible} | ${item.proves} | ${item.reportSection} |`,
      ),
    "",
  ].join("\n");
  const manifest = [
    "# OT-SOC Fusion X v1.1.1 Screenshot Manifest",
    "",
    "| Filename | Pixel dimensions | File size (bytes) | Capture timestamp (UTC) | Route | Scenario/run context |",
    "|---|---:|---:|---|---|---|",
    ...captures
      .sort((left, right) => left.number - right.number)
      .map(
        (item) =>
          `| \`${item.filename}\` | ${item.width} x ${item.height} | ${item.size} | ${item.capturedAt} | \`${item.route}\` | ${item.scenario} |`,
      ),
    "",
  ].join("\n");
  const findings = {
    viewport: VIEWPORT,
    screenshotCount: captures.length,
    pageVisualResults: Object.fromEntries(visualResults),
    consoleErrors,
    expectedAuthenticationWarnings,
    failedApplicationRequests: failedRequests,
    expectedNavigationAborts: abortedNavigationRequests,
    externalNetworkRequests: externalRequests,
  };
  await Promise.all([
    writeFile(path.join(REPORT_DIR, "SCREENSHOT_INDEX.md"), index, "utf8"),
    writeFile(path.join(REPORT_DIR, "SCREENSHOT_MANIFEST.md"), manifest, "utf8"),
    writeFile(
      path.join(LOG_DIR, "browser-console-network.json"),
      `${JSON.stringify(findings, null, 2)}\n`,
      "utf8",
    ),
  ]);
}
