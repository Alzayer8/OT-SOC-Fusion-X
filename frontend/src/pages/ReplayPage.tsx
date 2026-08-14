import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  getIncidents,
  getReplayForIncident,
  type ReplayEvent,
  type WorkflowIncidentRecord,
} from "../api/client";
import { Icon } from "../components/Icons";
import {
  EvidenceCard,
  ExactStatusBadge,
  LoadingSkeleton,
  ProductEmpty,
  ProductError,
  SafetyBanner,
} from "../components/ProductComponents";
import { ProcessSchematic } from "../components/ProcessSchematic";
import { useApiResource } from "../hooks/useApiResource";
import { useLab } from "../context/LabContext";
import { recordAtOrBefore, valveCommandAtOrBefore } from "../utils/evidence";
import { asRecord, formatTimestamp, numeric } from "../utils/presentation";
import {
  MiniStat,
  TrendChart,
  VisualizationPanel,
  type TrendSeries,
} from "../components/Visualizations";

export function ReplayPage() {
  const lab = useLab();
  const [params] = useSearchParams();
  const incidentId = params.get("incident");
  const state = useApiResource(
    `replay:${incidentId ?? "selector"}:${lab.activeRun?.run_id}`,
    async (signal) => {
      if (incidentId) {
        return { bundle: await getReplayForIncident(incidentId, signal), current: [], history: [] };
      }
      const [current, history] = await Promise.all([
        getIncidents({ scope: "CURRENT", runId: lab.activeRun?.run_id, limit: 10 }, signal),
        getIncidents({ scope: "HISTORY", limit: 50 }, signal),
      ]);
      const currentIds = new Set(current.items.map((item) => item.incident_id));
      return {
        bundle: null,
        current: current.items,
        history: history.items.filter((item) => !currentIds.has(item.incident_id)),
      };
    },
  );
  return (
    <div className="page-stack">
      <header className="product-page-header">
        <div>
          <p className="page-header__eyebrow">Immutable stored-evidence reconstruction</p>
          <h1>Replay</h1>
          <p>Observed-time chronology with client-only visualization controls.</p>
        </div>
        <div className="page-header__context">
          <Icon name="replay" />
          <span>Visualization-only chronology</span>
        </div>
      </header>
      <SafetyBanner />
      {state.status === "loading" ? <LoadingSkeleton label="Loading replay bundle" /> : null}
      {state.status === "error" ? <ProductError {...state} /> : null}
      {state.status === "success" && !state.data.bundle ? (
        <ReplaySelector current={state.data.current} history={state.data.history} />
      ) : null}
      {state.status === "success" && state.data.bundle ? (
        <ReplayWorkspace bundle={state.data.bundle} />
      ) : null}
    </div>
  );
}

function ReplaySelector({
  current,
  history,
}: {
  current: WorkflowIncidentRecord[];
  history: WorkflowIncidentRecord[];
}) {
  return (
    <div className="replay-selector-grid">
      <ReplayIncidentList
        title="Available Current-Run Incidents"
        items={current}
        empty="No current incidents exist in the selected run."
      />
      <ReplayIncidentList
        title="Recent Historical Incidents"
        items={history}
        empty="No historical incident replay is available."
      />
      <p className="safety-copy">
        Replay loads one bounded immutable incident bundle. Selecting a replay does not rerun a
        scenario or mutate evidence.
      </p>
    </div>
  );
}

function ReplayIncidentList({
  title,
  items,
  empty,
}: {
  title: string;
  items: WorkflowIncidentRecord[];
  empty: string;
}) {
  return (
    <section className="panel">
      <div className="panel__header">
        <h2>{title}</h2>
      </div>
      <div className="panel__content">
        {items.length ? (
          <ul className="replay-selection-list">
            {items.map((item) => (
              <li key={item.incident_id}>
                <div>
                  <strong>{item.title}</strong>
                  <span>
                    {item.severity} · {item.status} · {item.disposition ?? "UNREVIEWED"}
                  </span>
                </div>
                <Link
                  className="button button--link compact"
                  to={`/replay?incident=${item.incident_id}`}
                >
                  Open Replay
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <ProductEmpty title="No eligible replay" message={empty} />
        )}
      </div>
    </section>
  );
}

function ReplayWorkspace({ bundle }: { bundle: Awaited<ReturnType<typeof getReplayForIncident>> }) {
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  useEffect(() => {
    if (!playing || !bundle.events.length) return;
    const timer = window.setInterval(
      () =>
        setCursor((current) => {
          if (current >= bundle.events.length - 1) {
            setPlaying(false);
            return current;
          }
          return current + 1;
        }),
      Math.max(150, 750 / speed),
    );
    return () => window.clearInterval(timer);
  }, [playing, speed, bundle.events.length]);
  const selected = bundle.events[cursor];
  const telemetry = useMemo(
    () => recordAtOrBefore(bundle.events, cursor, "simulator_telemetry"),
    [bundle.events, cursor],
  );
  const command = useMemo(
    () => valveCommandAtOrBefore(bundle.events, cursor),
    [bundle.events, cursor],
  );
  if (!selected)
    return (
      <ProductEmpty
        title="Replay bundle is empty"
        message="No verified stored event exists in this bounded reconstruction."
      />
    );
  return (
    <>
      <div className="status-row">
        <ExactStatusBadge value={bundle.completeness} />
        <ExactStatusBadge value="HISTORICAL STORED EVIDENCE" />
        <span>{bundle.events.length} verified events</span>
      </div>
      <section className="replay-summary-grid" aria-label="Replay bundle summary">
        <MiniStat
          label="Verified Events"
          value={bundle.events.length}
          note="Bounded stored bundle"
          tone="blue"
        />
        <MiniStat
          label="Completeness"
          value={bundle.completeness}
          note={`${bundle.gaps.length} explicit gaps`}
          tone={bundle.completeness === "COMPLETE" ? "green" : "amber"}
        />
        <MiniStat
          label="Cursor"
          value={`${cursor + 1} / ${bundle.events.length}`}
          note={selected.event_class.replaceAll("_", " ")}
          tone="purple"
        />
        <MiniStat
          label="Playback"
          value={`${speed}×`}
          note="Browser-local visualization"
          tone="cyan"
        />
      </section>
      {bundle.gaps.length ? <div className="partial-banner">{bundle.gaps.join(" ")}</div> : null}
      <section className="panel replay-player">
        <div className="panel__header">
          <div>
            <h2>Observed-time player</h2>
            <p>
              {formatTimestamp(selected.observed_at)} · event {cursor + 1} of {bundle.events.length}
            </p>
          </div>
        </div>
        <div className="replay-track">
          <div className="replay-track__visual" aria-hidden="true">
            <span
              style={{
                width: `${bundle.events.length <= 1 ? 0 : (cursor / (bundle.events.length - 1)) * 100}%`,
              }}
            />
            {bundle.events.map((item, index) => (
              <i
                className={`replay-marker replay-marker--${item.event_class.toLowerCase()}`}
                key={item.event_id}
                style={{
                  left: `${bundle.events.length <= 1 ? 0 : (index / (bundle.events.length - 1)) * 100}%`,
                }}
              />
            ))}
          </div>
          <input
            aria-label="Replay timeline scrub"
            type="range"
            min={0}
            max={Math.max(0, bundle.events.length - 1)}
            value={cursor}
            onChange={(event) => {
              setPlaying(false);
              setCursor(Number(event.target.value));
            }}
          />
        </div>
        <div className="replay-controls" aria-label="Replay visualization controls">
          <button
            aria-label="Step back"
            disabled={cursor === 0}
            onClick={() => {
              setPlaying(false);
              setCursor((value) => Math.max(0, value - 1));
            }}
          >
            ◀ Step Back
          </button>
          <button
            aria-label={playing ? "Pause replay" : "Play replay"}
            onClick={() => setPlaying((value) => !value)}
          >
            {playing ? "Pause" : "Play"}
          </button>
          <button
            aria-label="Step forward"
            disabled={cursor === bundle.events.length - 1}
            onClick={() => {
              setPlaying(false);
              setCursor((value) => Math.min(bundle.events.length - 1, value + 1));
            }}
          >
            Step Forward ▶
          </button>
          <label>
            Visualization speed
            <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
              <option value={0.5}>0.5×</option>
              <option value={1}>1×</option>
              <option value={2}>2×</option>
              <option value={4}>4×</option>
            </select>
          </label>
        </div>
        <ol className="replay-event-strip">
          {bundle.events.map((item, index) => (
            <li key={item.event_id}>
              <button
                className={index === cursor ? "selected" : ""}
                onClick={() => {
                  setPlaying(false);
                  setCursor(index);
                }}
              >
                <time>{new Date(item.observed_at).toISOString().slice(11, 19)}</time>
                <span>{item.event_class.replaceAll("_", " ")}</span>
              </button>
            </li>
          ))}
        </ol>
      </section>
      <ReplayTrends events={bundle.events} cursor={cursor} />
      <ProcessSchematic
        telemetry={telemetry}
        valveCommand={command}
        incidentSeverity={bundle.incident?.severity}
        historical
      />
      {selected.evidence ? (
        <EvidenceCard
          record={selected.evidence}
          title={`Selected event · ${selected.event_class.replaceAll("_", " ")}`}
        />
      ) : (
        <section className="panel">
          <div className="panel__header">
            <h2>Selected incident event</h2>
          </div>
          <div className="panel__content">
            <p>{selected.summary}</p>
            <p>{selected.incident_event?.entry_type}</p>
          </div>
        </section>
      )}
      <section className="panel">
        <div className="panel__header">
          <h2>Replay context</h2>
        </div>
        <div className="panel__content">
          <dl className="detail-grid">
            <div>
              <dt>Simulation run</dt>
              <dd>{bundle.simulation_id ?? "No process scope"}</dd>
            </div>
            <div>
              <dt>Configuration</dt>
              <dd className="mono">{bundle.configuration_hash ?? "No process scope"}</dd>
            </div>
            <div>
              <dt>Time authority</dt>
              <dd>observed_at → class rank → UUID</dd>
            </div>
            <div>
              <dt>Backend mutation</dt>
              <dd>None — controls are client-only</dd>
            </div>
          </dl>
          {bundle.incident ? (
            <div className="action-links">
              <Link to={`/incidents/${bundle.incident.incident_id}`}>Incident workspace</Link>
              <Link to={`/digital-twin?incident=${bundle.incident.incident_id}`}>Digital Twin</Link>
            </div>
          ) : null}
        </div>
      </section>
    </>
  );
}

function ReplayTrends({ events, cursor }: { events: ReplayEvent[]; cursor: number }) {
  const telemetry = events.flatMap((event, eventIndex) => {
    if (event.evidence?.evidence_type !== "simulator_telemetry") return [];
    return [{ event, eventIndex, payload: asRecord(event.evidence.payload) }];
  });
  const build = (
    label: string,
    field: string,
    tone: TrendSeries["tone"],
    unit: string,
  ): TrendSeries => ({
    label,
    tone,
    unit,
    points: telemetry.flatMap(({ event, eventIndex, payload }) => {
      const value = numeric(payload[field]);
      return value === null
        ? []
        : [{ x: eventIndex, label: formatTimestamp(event.observed_at), value }];
    }),
  });
  return (
    <section className="replay-trend-grid" aria-label="Cursor-synchronized stored telemetry">
      <VisualizationPanel title="Flow & Pressure" eyebrow="Cursor-synchronized history">
        <TrendChart
          title="Replay flow and pressure trend"
          cursorX={cursor}
          series={[
            build("Pipeline flow", "pipeline_flow_rate_m3h", "cyan", "synthetic m³/h"),
            build("Pipeline pressure", "pipeline_pressure_bar", "purple", "synthetic bar"),
          ]}
        />
      </VisualizationPanel>
      <VisualizationPanel title="Tank & Valve Position" eyebrow="Cursor-synchronized history">
        <TrendChart
          title="Replay tank and valve position trend"
          cursorX={cursor}
          series={[
            build("TK-101 level", "source_tank_level_percent", "blue", "%"),
            build("TK-102 level", "receiving_tank_level_percent", "green", "%"),
            build("CV-101 observed", "control_valve_position_percent", "amber", "% open"),
          ]}
        />
      </VisualizationPanel>
    </section>
  );
}
