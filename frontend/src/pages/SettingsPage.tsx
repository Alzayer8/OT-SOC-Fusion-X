import { useEffect, useState } from "react";

import { getLiveness, getMetadata, getReadiness } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icons";
import {
  ExactStatusBadge,
  LoadingSkeleton,
  ProductError,
  SafetyBanner,
} from "../components/ProductComponents";
import { useApiResource } from "../hooks/useApiResource";
import { MiniStat } from "../components/Visualizations";
import { UserAdministration } from "../components/UserAdministration";
import { useLab } from "../context/LabContext";
import { formatTimestamp, shortId } from "../utils/presentation";

const STORAGE_KEY = "otsoc.phase8.preferences.v1";
type Preferences = {
  refresh: "0" | "30" | "60" | "120" | "300";
  time: "UTC" | "LOCAL";
  pageSize: "25" | "50" | "100";
  density: "COMPACT" | "COMFORTABLE";
};
const DEFAULTS: Preferences = { refresh: "60", time: "UTC", pageSize: "50", density: "COMPACT" };

function loadPreferences(): Preferences {
  try {
    const parsed = JSON.parse(
      localStorage.getItem(STORAGE_KEY) ?? "null",
    ) as Partial<Preferences> | null;
    if (
      !parsed ||
      !["0", "30", "60", "120", "300"].includes(parsed.refresh ?? "") ||
      !["UTC", "LOCAL"].includes(parsed.time ?? "") ||
      !["25", "50", "100"].includes(parsed.pageSize ?? "") ||
      !["COMPACT", "COMFORTABLE"].includes(parsed.density ?? "")
    )
      return DEFAULTS;
    return parsed as Preferences;
  } catch {
    return DEFAULTS;
  }
}

export function SettingsPage() {
  const auth = useAuth();
  const lab = useLab();
  const [preferences, setPreferences] = useState(loadPreferences);
  const state = useApiResource(
    "settings-system",
    async (signal) => {
      const [meta, live, ready] = await Promise.all([
        getMetadata(signal),
        getLiveness(signal),
        getReadiness(signal),
      ]);
      return { meta, live, ready };
    },
    30_000,
  );
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
    document.documentElement.dataset.density = preferences.density.toLowerCase();
  }, [preferences]);
  const update = <K extends keyof Preferences>(key: K, value: Preferences[K]) =>
    setPreferences((current) => ({ ...current, [key]: value }));
  return (
    <div className="page-stack">
      <header className="product-page-header">
        <div>
          <p className="page-header__eyebrow">Display and system context</p>
          <h1>Settings</h1>
          <p>
            Local account, session, safe display preferences, and synthetic environment information.
          </p>
        </div>
        <div className="page-header__context">
          <Icon name="settings" />
          <span>Browser-local + read-only facts</span>
        </div>
      </header>
      <SafetyBanner />
      <div className="settings-grid">
        <section className="panel">
          <div className="panel__header">
            <h2>Local Account</h2>
          </div>
          <div className="panel__content">
            <dl className="detail-grid">
              <div>
                <dt>Display name</dt>
                <dd>{auth.user?.display_name ?? "Unavailable"}</dd>
              </div>
              <div>
                <dt>Username</dt>
                <dd>{auth.user?.username ?? "Unavailable"}</dd>
              </div>
              <div>
                <dt>Role</dt>
                <dd>
                  <ExactStatusBadge value={auth.user?.role ?? "UNAVAILABLE"} />
                </dd>
              </div>
              <div>
                <dt>Account state</dt>
                <dd>{auth.user?.active ? "ACTIVE" : "UNAVAILABLE"}</dd>
              </div>
            </dl>
          </div>
        </section>
        <section className="panel">
          <div className="panel__header">
            <h2>Session</h2>
          </div>
          <div className="panel__content">
            <dl className="detail-grid">
              <div>
                <dt>Authentication</dt>
                <dd>Backend-enforced local session</dd>
              </div>
              <div>
                <dt>Expires</dt>
                <dd>{auth.expiresAt ? formatTimestamp(auth.expiresAt) : "Unavailable"}</dd>
              </div>
              <div>
                <dt>Credential storage</dt>
                <dd>HttpOnly session cookie; no token in localStorage</dd>
              </div>
            </dl>
            <button className="button" type="button" onClick={() => void auth.logout()}>
              Logout
            </button>
          </div>
        </section>
        <section className="panel">
          <div className="panel__header">
            <h2>Display preferences</h2>
          </div>
          <div className="settings-form">
            <label>
              Data refresh
              <select
                value={preferences.refresh}
                onChange={(event) =>
                  update("refresh", event.target.value as Preferences["refresh"])
                }
              >
                <option value="0">Off</option>
                <option value="30">30 seconds</option>
                <option value="60">60 seconds</option>
                <option value="120">120 seconds</option>
                <option value="300">300 seconds</option>
              </select>
            </label>
            <label>
              Time display
              <select
                value={preferences.time}
                onChange={(event) => update("time", event.target.value as Preferences["time"])}
              >
                <option value="UTC">UTC</option>
                <option value="LOCAL">Browser local</option>
              </select>
            </label>
            <label>
              Incident page size
              <select
                value={preferences.pageSize}
                onChange={(event) =>
                  update("pageSize", event.target.value as Preferences["pageSize"])
                }
              >
                <option value="25">25</option>
                <option value="50">50</option>
                <option value="100">100</option>
              </select>
            </label>
            <label>
              Display density
              <select
                value={preferences.density}
                onChange={(event) =>
                  update("density", event.target.value as Preferences["density"])
                }
              >
                <option value="COMPACT">Compact</option>
                <option value="COMFORTABLE">Comfortable</option>
              </select>
            </label>
          </div>
        </section>
        <section className="panel">
          <div className="panel__header">
            <h2>Read-only system information</h2>
          </div>
          <div className="panel__content">
            {state.status === "loading" ? (
              <LoadingSkeleton label="Loading system information" />
            ) : null}
            {state.status === "error" ? <ProductError {...state} /> : null}
            {state.status === "success" ? (
              <>
                <div className="settings-health-grid" aria-label="Application health summary">
                  <MiniStat
                    label="Backend"
                    value={state.data.live.status.toUpperCase()}
                    note="Liveness response"
                    tone="green"
                  />
                  <MiniStat
                    label="Database"
                    value={state.data.ready.database.toUpperCase()}
                    note="Readiness dependency"
                    tone="green"
                  />
                  <MiniStat
                    label="Operating Mode"
                    value="OFFLINE"
                    note={state.data.meta.operating_mode}
                    tone="cyan"
                  />
                </div>
                <div className="status-row">
                  <ExactStatusBadge value={state.data.meta.operating_mode} />
                  <ExactStatusBadge value={state.data.live.status.toUpperCase()} />
                  <ExactStatusBadge value={state.data.ready.database.toUpperCase()} />
                </div>
                <dl className="detail-grid">
                  <div>
                    <dt>Application</dt>
                    <dd>
                      {state.data.meta.application_name} {state.data.meta.application_version}
                    </dd>
                  </div>
                  <div>
                    <dt>Visual experience</dt>
                    <dd>v1.1.1</dd>
                  </div>
                  <div>
                    <dt>Environment</dt>
                    <dd>{state.data.meta.environment}</dd>
                  </div>
                  <div>
                    <dt>Domain</dt>
                    <dd>{state.data.meta.domain}</dd>
                  </div>
                  <div>
                    <dt>API</dt>
                    <dd>{state.data.meta.api_version}</dd>
                  </div>
                </dl>
                <h3>Active profiles</h3>
                <ul className="profile-list">
                  {state.data.meta.active_profiles.map((item) => (
                    <li key={item.profile_id}>
                      <strong>{item.profile_id}</strong>
                      <span>{item.version}</span>
                      <code title={item.sha256}>{item.sha256.slice(0, 12)}…</code>
                    </li>
                  ))}
                </ul>
                <h3>Active schemas</h3>
                <ul className="profile-list">
                  {state.data.meta.active_schemas.map((item) => (
                    <li key={item.schema_id}>
                      <strong>{item.schema_id}</strong>
                      <span>{item.version}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
        </section>
      </div>
      <section className="panel">
        <div className="panel__header">
          <h2>Synthetic Lab Information</h2>
        </div>
        <div className="panel__content">
          <dl className="detail-grid">
            <div>
              <dt>Default startup</dt>
              <dd>Baseline / Normal Synthetic Operation</dd>
            </div>
            <div>
              <dt>Active scenario</dt>
              <dd>{lab.activeRun?.scenario_title ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Run ID</dt>
              <dd className="mono">
                {lab.activeRun ? shortId(lab.activeRun.run_id) : "Unavailable"}
              </dd>
            </div>
            <div>
              <dt>Scenario state</dt>
              <dd>{lab.activeRun?.status ?? "Unavailable"}</dd>
            </div>
          </dl>
          <p className="safety-copy">
            Historical runs remain stored while the default active application context is Baseline.
          </p>
        </div>
      </section>
      {auth.hasRole("ADMIN") ? <UserAdministration /> : null}
      <section className="settings-scope-grid" aria-label="Product safety boundaries">
        <article>
          <Icon name="database" />
          <div>
            <strong>Evidence source</strong>
            <span>Stored synthetic records only</span>
          </div>
        </article>
        <article>
          <Icon name="shield" />
          <div>
            <strong>Investigation posture</strong>
            <span>Advisory only · no containment</span>
          </div>
        </article>
        <article>
          <Icon name="twin" />
          <div>
            <strong>Process boundary</strong>
            <span>Read-only visualization · no control</span>
          </div>
        </article>
      </section>
      <p className="settings-boundary">
        No password hash, secret, Docker administration, scanner, PLC connectivity, external
        integration, or infrastructure control is exposed.
      </p>
    </div>
  );
}
