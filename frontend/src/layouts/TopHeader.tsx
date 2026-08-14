import { useEffect, useState } from "react";

import { getLiveness, getMetadata, getReadiness } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icons";
import { ScenarioLabPanel } from "../components/ScenarioLabPanel";
import { StatusBadge } from "../components/StatusBadge";
import { useLab } from "../context/LabContext";
import { shortId } from "../utils/presentation";

type ApiState = "checking" | "available" | "partial" | "unavailable";

export function TopHeader() {
  const auth = useAuth();
  const lab = useLab();
  const [apiState, setApiState] = useState<ApiState>("checking");

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      getLiveness(controller.signal),
      getReadiness(controller.signal),
      getMetadata(controller.signal),
    ])
      .then(([, readiness]) => setApiState(readiness.status === "ready" ? "available" : "partial"))
      .catch(() => setApiState("unavailable"));
    return () => controller.abort();
  }, []);

  const apiLabel =
    apiState === "checking"
      ? "Health check pending"
      : apiState === "available"
        ? "Backend + database available"
        : apiState === "partial"
          ? "Database unavailable"
          : "Backend unavailable";

  return (
    <header className="top-header">
      <div className="top-header__context" aria-label="Laboratory context">
        <span className="top-header__lab">
          <Icon name="activity" />
          Synthetic Oil &amp; Gas Transfer Lab
        </span>
        <span className="top-header__separator" aria-hidden="true" />
        <span>Offline Evidence Mode</span>
        <span className="top-header__release">SOC workflow v1.1.1</span>
        {lab.activeRun ? (
          <span className="top-header__run">
            <strong>Active Scenario: {lab.activeRun.scenario_id}</strong>
            <span>{lab.activeRun.scenario_title}</span>
            <code>{shortId(lab.activeRun.run_id)}</code>
            <span>{lab.activeRun.status}</span>
          </span>
        ) : null}
      </div>
      <div className="top-header__status" aria-label="Foundation status">
        <StatusBadge
          tone={
            apiState === "available" ? "success" : apiState === "partial" ? "warning" : "neutral"
          }
        >
          {apiLabel}
        </StatusBadge>
        <StatusBadge tone="info">Synthetic · advisory only</StatusBadge>
        <ScenarioLabPanel />
        {auth.user ? (
          <div className="account-menu" aria-label="Authenticated analyst">
            <span className="account-menu__avatar" aria-hidden="true">
              {initials(auth.user.display_name)}
            </span>
            <span>
              <strong>{auth.user.display_name}</strong>
              <small>{auth.user.role.replaceAll("_", " ")}</small>
            </span>
            <button type="button" onClick={() => void auth.logout()}>
              Logout
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}

function initials(displayName: string): string {
  return (
    displayName
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part.slice(0, 1).toUpperCase())
      .join("") || "U"
  );
}
