import { useState } from "react";
import { Link } from "react-router-dom";

import type { ScenarioId } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useLab } from "../context/LabContext";
import { formatTimestamp, shortId } from "../utils/presentation";
import { ExactStatusBadge } from "./ProductComponents";

export function ScenarioLabPanel() {
  const auth = useAuth();
  const lab = useLab();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const canRun = auth.hasRole("ADMIN");
  const canReset = auth.hasRole("ADMIN");

  const run = async (scenarioId: ScenarioId) => {
    setMessage(null);
    try {
      const result = await lab.startScenario(scenarioId);
      setMessage(
        `${result.scenario_id} completed with ${result.incident_count} resulting incident(s).`,
      );
    } catch {
      setMessage("The approved synthetic scenario could not be started.");
    }
  };

  return (
    <div className="scenario-lab">
      <button
        aria-expanded={open}
        className="scenario-lab__trigger"
        type="button"
        onClick={() => setOpen((value) => !value)}
      >
        Scenario Lab
      </button>
      {open ? (
        <section className="scenario-lab__panel" aria-label="Synthetic Scenario Lab">
          <header>
            <div>
              <span className="section-kicker">Approved synthetic runs only</span>
              <h2>Scenario Lab</h2>
            </div>
            <button aria-label="Close Scenario Lab" type="button" onClick={() => setOpen(false)}>
              ×
            </button>
          </header>
          {lab.activeRun ? (
            <div className="scenario-lab__active">
              <div>
                <small>Current run</small>
                <strong>{lab.activeRun.scenario_title}</strong>
                <code>{shortId(lab.activeRun.run_id)}</code>
              </div>
              <ExactStatusBadge value={lab.activeRun.status} />
            </div>
          ) : null}
          {lab.error ? (
            <p className="form-error" role="alert">
              {lab.error}
            </p>
          ) : null}
          <div className="scenario-catalog" aria-label="Approved scenario catalog">
            {lab.catalog.map((scenario) => (
              <article key={scenario.scenario_id}>
                <span>{scenario.scenario_id}</span>
                <div>
                  <strong>{scenario.title}</strong>
                  <p>{scenario.description}</p>
                  <ExactStatusBadge value={scenario.state} />
                </div>
                {scenario.scenario_id === "BASELINE" ? (
                  <button
                    disabled={lab.busy || lab.activeRun?.scenario_id === "BASELINE" || !canRun}
                    type="button"
                    onClick={() => void lab.returnToBaseline()}
                  >
                    Return to Baseline
                  </button>
                ) : (
                  <button
                    disabled={lab.busy || !canRun}
                    type="button"
                    onClick={() => void run(scenario.scenario_id)}
                  >
                    Start Synthetic Scenario
                  </button>
                )}
              </article>
            ))}
          </div>
          {!canRun ? (
            <p className="safety-copy">
              Your authenticated role may inspect runs but cannot start them.
            </p>
          ) : null}
          {message ? <p role="status">{message}</p> : null}
          <section className="scenario-history">
            <h3>Bounded run history</h3>
            {lab.history.length ? (
              <ol>
                {lab.history.map((runItem) => (
                  <li key={runItem.run_id}>
                    <div>
                      <strong>{runItem.scenario_id}</strong>
                      <code>{shortId(runItem.run_id)}</code>
                      <small>
                        Started by {runItem.started_by_display_name ?? "System"} ·{" "}
                        {runItem.started_at ? formatTimestamp(runItem.started_at) : "Not started"}
                      </small>
                      <small>
                        Completed{" "}
                        {runItem.completed_at ? formatTimestamp(runItem.completed_at) : "—"}
                      </small>
                    </div>
                    <span>{runItem.status}</span>
                    <span>{runItem.incident_count} incident(s)</span>
                    {runItem.incident_count ? (
                      <Link
                        to={`/incidents?scope=HISTORY&run=${encodeURIComponent(runItem.run_id)}`}
                      >
                        View result
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ol>
            ) : (
              <p>No historical synthetic runs are stored.</p>
            )}
          </section>
          {canReset ? (
            <button
              className="button button--danger-outline"
              disabled={lab.busy}
              type="button"
              onClick={() => void lab.resetLab()}
            >
              Reset Synthetic Lab
            </button>
          ) : null}
          <p className="safety-copy">
            Scenario execution is allowlisted and local. No target, packet, register, credential, or
            external endpoint can be supplied.
          </p>
        </section>
      ) : null}
    </div>
  );
}
