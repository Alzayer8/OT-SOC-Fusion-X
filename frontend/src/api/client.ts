import type { components, paths } from "./generated/schema";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

const CSRF_COOKIE_NAMES = ["otsoc_csrf_token", "otsoc_csrf", "csrf_token"] as const;
let csrfToken: string | null = null;

export type LivenessResponse = components["schemas"]["LivenessResponse"];
export type ReadinessResponse = components["schemas"]["ReadinessResponse"];
export type MetadataResponse = components["schemas"]["MetadataResponse"];
export type OverviewSummary = components["schemas"]["OverviewSummaryResponse"];
export type AssetCatalog = components["schemas"]["AssetCatalogResponse"];
export type AssetDetail = components["schemas"]["AssetDetailResponse"];
export type ProductAsset = components["schemas"]["ProductAsset"];
export type EvidenceRecord = components["schemas"]["EvidenceRecordResponse"];
export type EvidenceList = components["schemas"]["EvidenceListResponse"];
export type IncidentRecord = components["schemas"]["IncidentRecordResponse"];
export type IncidentList = components["schemas"]["IncidentListResponse"];
export type IncidentDetail = components["schemas"]["IncidentDetailResponse"];
export type IncidentMutation = components["schemas"]["IncidentMutationResponse"];
export type ReplayBundle = components["schemas"]["ReplayBundleResponse"];
export type ReplayEvent = components["schemas"]["ReplayEvent"];

export type LocalRole = "ADMIN" | "SOC_ANALYST" | "OT_ENGINEER" | "READ_ONLY";
export type ScenarioId = "BASELINE" | "S1" | "S2" | "S3" | "S4";
export type ScenarioState = "READY" | "RUNNING" | "COMPLETED" | "FAILED";
export type IncidentDisposition = "UNREVIEWED" | "TRUE_POSITIVE" | "FALSE_POSITIVE";
export type RunScope = "CURRENT" | "HISTORY";

export interface LocalUser {
  user_id: string;
  username: string;
  display_name: string;
  role: LocalRole;
  active: boolean;
  version: number;
  created_at?: string;
  updated_at?: string;
}

export interface AssignableUser {
  user_id: string;
  username: string;
  display_name: string;
  role: "ADMIN" | "SOC_ANALYST";
}

export interface AuthSession {
  authenticated: boolean;
  user: LocalUser | null;
  expires_at: string | null;
  csrf_token?: string;
}

export interface ScenarioDefinition {
  scenario_id: ScenarioId;
  title: string;
  description: string;
  state: "READY";
}

export interface LabRun {
  run_id: string;
  scenario_id: ScenarioId;
  scenario_title: string;
  status: ScenarioState;
  started_by: string | null;
  started_by_display_name?: string | null;
  started_at: string | null;
  completed_at: string | null;
  incident_count: number;
  simulation_id?: string | null;
  configuration_hash?: string | null;
  window_start?: string | null;
  window_end?: string | null;
}

export interface LabContextResponse {
  active_run: LabRun;
}

export interface ScenarioCatalogResponse {
  items: ScenarioDefinition[];
}

export interface LabRunListResponse {
  items: LabRun[];
}

export interface LabStartResponse extends LabContextResponse {
  run: LabRun;
}

export type WorkflowIncidentRecord = IncidentRecord & {
  run_id?: string | null;
  scenario_id?: ScenarioId | null;
  disposition?: IncidentDisposition;
  assignee_user_id?: string | null;
  assignee_display_name?: string | null;
  assigned_at?: string | null;
};

export interface WorkflowIncidentList extends Omit<IncidentList, "items"> {
  items: WorkflowIncidentRecord[];
}

export interface WorkflowIncidentDetail extends Omit<IncidentDetail, "incident"> {
  incident: WorkflowIncidentRecord;
}

export interface IncidentAuditEntry {
  audit_id: string;
  action: string;
  actor_display_name: string;
  occurred_at: string;
  summary: string;
}

export interface IncidentAuditResponse {
  items: IncidentAuditEntry[];
}

export interface IncidentReportFields {
  investigation_summary: string;
  analyst_assessment: string;
  evidence_assessment: string;
  process_impact_assessment: string;
  disposition_rationale: string;
  recommended_follow_up: string;
  final_conclusion: string;
}

export interface IncidentReport extends IncidentReportFields {
  incident_id: string;
  created_by_user_id: string | null;
  created_at: string | null;
  updated_by_user_id: string | null;
  updated_at: string | null;
  version: number;
  fields_filled: number;
  fields_total: 7;
}

export class ApiError extends Error {
  readonly status: number;
  readonly requestId?: string;

  constructor(status: number, message: string, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.requestId = requestId;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

function readCsrfCookie(): string | null {
  if (typeof document === "undefined") return null;
  const cookies = new Map(
    document.cookie.split(";").flatMap((value) => {
      const separator = value.indexOf("=");
      if (separator < 0) return [];
      return [[value.slice(0, separator).trim(), decodeURIComponent(value.slice(separator + 1))]];
    }),
  );
  for (const name of CSRF_COOKIE_NAMES) {
    const value = cookies.get(name);
    if (value) return value;
  }
  return null;
}

export function refreshCsrfTokenFromCookie(): void {
  csrfToken = readCsrfCookie();
}

export function clearCsrfToken(): void {
  csrfToken = null;
}

async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  const method = options.method ?? "GET";
  if (["POST", "PATCH", "PUT", "DELETE"].includes(method)) {
    csrfToken ??= readCsrfCookie();
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
    credentials: "include",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      error?: { message?: string; request_id?: string };
      detail?: string | { msg?: string }[];
    } | null;
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : Array.isArray(payload?.detail)
          ? payload.detail
              .flatMap((item) => (typeof item.msg === "string" ? [item.msg] : []))
              .join(" ")
          : null;
    const error = new ApiError(
      response.status,
      payload?.error?.message || detail || `API request failed with status ${response.status}.`,
      payload?.error?.request_id,
    );
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("otsoc:session-expired"));
    }
    throw error;
  }
  refreshCsrfTokenFromCookie();
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function withQuery(path: string, values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export function getLiveness(signal?: AbortSignal): Promise<LivenessResponse> {
  return apiRequest<LivenessResponse>("/health/live", { signal });
}

export function getReadiness(signal?: AbortSignal): Promise<ReadinessResponse> {
  return apiRequest<ReadinessResponse>("/health/ready", { signal });
}

export function getMetadata(signal?: AbortSignal): Promise<MetadataResponse> {
  return apiRequest<MetadataResponse>("/api/v1/meta", { signal });
}

export function getAuthSession(signal?: AbortSignal): Promise<AuthSession> {
  return apiRequest<AuthSession>("/api/v1/auth/session", { signal });
}

export function login(username: string, password: string): Promise<AuthSession> {
  return apiRequest<AuthSession>("/api/v1/auth/login", {
    method: "POST",
    body: { username, password },
  });
}

export function logout(): Promise<void> {
  return apiRequest<void>("/api/v1/auth/logout", { method: "POST" });
}

export function getOverview(signal?: AbortSignal): Promise<OverviewSummary> {
  return apiRequest<OverviewSummary>("/api/v1/overview/summary", { signal });
}

export function getAssetCatalog(signal?: AbortSignal): Promise<AssetCatalog> {
  return apiRequest<AssetCatalog>("/api/v1/assets", { signal });
}

export function getAsset(assetKey: string, signal?: AbortSignal): Promise<AssetDetail> {
  return apiRequest<AssetDetail>(`/api/v1/assets/${encodeURIComponent(assetKey)}`, { signal });
}

export interface IncidentFilters {
  status?: string;
  category?: string;
  severity?: string;
  disposition?: string;
  assetId?: string;
  observedFrom?: string;
  observedTo?: string;
  limit?: number;
  cursor?: string;
  runId?: string;
  scope?: RunScope;
}

export function getIncidents(
  filters: IncidentFilters = {},
  signal?: AbortSignal,
): Promise<WorkflowIncidentList> {
  const backendScope =
    filters.scope === "HISTORY" ? (filters.runId ? "RUN" : "ALL_HISTORY") : "CURRENT";
  return apiRequest<WorkflowIncidentList>(
    withQuery("/api/v1/incidents", {
      status: filters.status,
      category: filters.category,
      severity: filters.severity,
      asset_id: filters.assetId,
      observed_from: filters.observedFrom,
      observed_to: filters.observedTo,
      limit: filters.limit ?? 50,
      cursor: filters.cursor,
      run_id: backendScope === "RUN" ? filters.runId : undefined,
      scope: backendScope,
    }),
    { signal },
  ).then((response) =>
    filters.disposition
      ? {
          ...response,
          items: response.items.filter(
            (incident) => (incident.disposition ?? "UNREVIEWED") === filters.disposition,
          ),
        }
      : response,
  );
}

export function getIncident(
  incidentId: string,
  signal?: AbortSignal,
): Promise<WorkflowIncidentDetail> {
  return apiRequest<WorkflowIncidentDetail>(`/api/v1/incidents/${encodeURIComponent(incidentId)}`, {
    signal,
  });
}

export function patchIncidentStatus(
  incidentId: string,
  newStatus: "OPEN" | "INVESTIGATING" | "RESOLVED",
  expectedVersion: number,
  reason?: string,
): Promise<IncidentMutation> {
  return apiRequest<IncidentMutation>(
    `/api/v1/incidents/${encodeURIComponent(incidentId)}/status`,
    {
      method: "PATCH",
      body: { new_status: newStatus, expected_version: expectedVersion, reason: reason || null },
    },
  );
}

export function addIncidentNote(
  incidentId: string,
  content: string,
  expectedVersion: number,
): Promise<IncidentMutation> {
  return apiRequest<IncidentMutation>(`/api/v1/incidents/${encodeURIComponent(incidentId)}/notes`, {
    method: "POST",
    body: { content, expected_version: expectedVersion },
  });
}

export interface EvidenceFilters {
  evidenceType?: string;
  sourceKey?: string;
  observedFrom?: string;
  observedTo?: string;
  limit?: number;
  cursor?: string;
  runId?: string;
  scope?: RunScope;
}

export function getEvidenceList(
  filters: EvidenceFilters = {},
  signal?: AbortSignal,
): Promise<EvidenceList> {
  const backendScope =
    filters.scope === "HISTORY" ? (filters.runId ? "RUN" : "ALL_HISTORY") : "CURRENT";
  return apiRequest<EvidenceList>(
    withQuery("/api/v1/evidence", {
      evidence_type: filters.evidenceType,
      source_key: filters.sourceKey,
      observed_from: filters.observedFrom,
      observed_to: filters.observedTo,
      limit: filters.limit ?? 50,
      cursor: filters.cursor,
      scope: backendScope,
      run_id: backendScope === "RUN" ? filters.runId : undefined,
    }),
    { signal },
  );
}

export function getEvidence(evidenceId: string, signal?: AbortSignal): Promise<EvidenceRecord> {
  return apiRequest<EvidenceRecord>(`/api/v1/evidence/${encodeURIComponent(evidenceId)}`, {
    signal,
  });
}

export function getReplayForIncident(
  incidentId: string,
  signal?: AbortSignal,
): Promise<ReplayBundle> {
  return apiRequest<ReplayBundle>(withQuery("/api/v1/replay", { incident_id: incidentId }), {
    signal,
  });
}

export function getReplayForCorrelation(
  evidenceId: string,
  signal?: AbortSignal,
): Promise<ReplayBundle> {
  return apiRequest<ReplayBundle>(
    withQuery("/api/v1/replay", { correlation_evidence_id: evidenceId }),
    { signal },
  );
}

export function getLabContext(signal?: AbortSignal): Promise<LabContextResponse> {
  return apiRequest<LabContextResponse>("/api/v1/lab/context", { signal });
}

export function getScenarioCatalog(signal?: AbortSignal): Promise<ScenarioCatalogResponse> {
  return apiRequest<ScenarioCatalogResponse>("/api/v1/lab/catalog", { signal });
}

export function getLabRuns(signal?: AbortSignal): Promise<LabRunListResponse> {
  return apiRequest<LabRunListResponse>(withQuery("/api/v1/lab/runs", { limit: 20 }), { signal });
}

export function startLabScenario(scenarioId: ScenarioId): Promise<LabStartResponse> {
  return apiRequest<LabStartResponse>("/api/v1/lab/start", {
    method: "POST",
    body: { scenario_id: scenarioId },
  });
}

export function returnLabToBaseline(): Promise<LabContextResponse> {
  return apiRequest<LabContextResponse>("/api/v1/lab/baseline", { method: "POST" });
}

export function resetSyntheticLab(): Promise<LabContextResponse> {
  return apiRequest<LabContextResponse>("/api/v1/lab/reset", { method: "POST" });
}

export function getIncidentAssignees(signal?: AbortSignal): Promise<{ items: AssignableUser[] }> {
  return apiRequest<{ items: AssignableUser[] }>("/api/v1/incident-assignees", { signal });
}

export function assignIncident(
  incidentId: string,
  assigneeUserId: string | null,
  expectedVersion: number,
): Promise<IncidentMutation> {
  return apiRequest<IncidentMutation>(
    `/api/v1/incidents/${encodeURIComponent(incidentId)}/assignment`,
    {
      method: "PATCH",
      body: { assignee_user_id: assigneeUserId, expected_version: expectedVersion },
    },
  );
}

export function setIncidentDisposition(
  incidentId: string,
  disposition: IncidentDisposition,
  reason: string,
  expectedVersion: number,
): Promise<IncidentMutation> {
  return apiRequest<IncidentMutation>(
    `/api/v1/incidents/${encodeURIComponent(incidentId)}/disposition`,
    {
      method: "PATCH",
      body: { disposition, reason, expected_version: expectedVersion },
    },
  );
}

export function getIncidentReport(
  incidentId: string,
  signal?: AbortSignal,
): Promise<IncidentReport> {
  return apiRequest<IncidentReport>(`/api/v1/incidents/${encodeURIComponent(incidentId)}/report`, {
    signal,
  });
}

export function saveIncidentReport(
  incidentId: string,
  fields: IncidentReportFields,
  expectedVersion: number,
): Promise<IncidentReport> {
  return apiRequest<IncidentReport>(`/api/v1/incidents/${encodeURIComponent(incidentId)}/report`, {
    method: "PUT",
    body: { ...fields, expected_version: expectedVersion },
  });
}

export function getIncidentAudit(
  incidentId: string,
  signal?: AbortSignal,
): Promise<IncidentAuditResponse> {
  return apiRequest<IncidentAuditResponse>(
    `/api/v1/incidents/${encodeURIComponent(incidentId)}/audit`,
    { signal },
  );
}

export function getLocalUsers(signal?: AbortSignal): Promise<{ items: LocalUser[] }> {
  return apiRequest<{ items: LocalUser[] }>("/api/v1/users", { signal });
}

export function createLocalUser(payload: {
  username: string;
  display_name: string;
  role: LocalRole;
  password: string;
}): Promise<LocalUser> {
  return apiRequest<{ user: LocalUser }>("/api/v1/users", { method: "POST", body: payload }).then(
    (response) => response.user,
  );
}

export function updateLocalUser(
  userId: string,
  payload: { active?: boolean; role?: LocalRole; display_name?: string; expected_version: number },
): Promise<LocalUser> {
  return apiRequest<{ user: LocalUser }>(`/api/v1/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: payload,
  }).then((response) => response.user);
}

export function resetLocalUserPassword(
  userId: string,
  password: string,
  expectedVersion: number,
): Promise<LocalUser> {
  return apiRequest<{ user: LocalUser }>(
    `/api/v1/users/${encodeURIComponent(userId)}/password-reset`,
    {
      method: "POST",
      body: { password, expected_version: expectedVersion },
    },
  ).then((response) => response.user);
}

export type IncidentStatusPatch = NonNullable<
  paths["/api/v1/incidents/{incident_id}/status"]["patch"]
>;
