import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getLabContext,
  getLabRuns,
  getScenarioCatalog,
  resetSyntheticLab,
  returnLabToBaseline,
  startLabScenario,
  type LabRun,
  type ScenarioDefinition,
  type ScenarioId,
} from "../api/client";

const APPROVED_SCENARIOS: ScenarioId[] = ["BASELINE", "S1", "S2", "S3", "S4"];

type LabStatus = "loading" | "ready" | "error";

interface LabContextValue {
  status: LabStatus;
  activeRun: LabRun | null;
  catalog: ScenarioDefinition[];
  history: LabRun[];
  error: string | null;
  busy: boolean;
  refresh: () => Promise<void>;
  startScenario: (scenarioId: ScenarioId) => Promise<LabRun>;
  returnToBaseline: () => Promise<void>;
  resetLab: () => Promise<void>;
}

const LabContext = createContext<LabContextValue | null>(null);

function validateCatalog(items: ScenarioDefinition[]): ScenarioDefinition[] {
  const ids = items.map((item) => item.scenario_id);
  if (
    ids.length !== APPROVED_SCENARIOS.length ||
    !APPROVED_SCENARIOS.every((id) => ids.includes(id)) ||
    ids.some((id) => !APPROVED_SCENARIOS.includes(id))
  ) {
    throw new Error(
      "The synthetic scenario catalog does not match the approved BASELINE/S1–S4 set.",
    );
  }
  return APPROVED_SCENARIOS.map((id) => items.find((item) => item.scenario_id === id)!);
}

export function LabProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<LabStatus>("loading");
  const [activeRun, setActiveRun] = useState<LabRun | null>(null);
  const [catalog, setCatalog] = useState<ScenarioDefinition[]>([]);
  const [history, setHistory] = useState<LabRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [context, catalogResponse, runs] = await Promise.all([
        getLabContext(),
        getScenarioCatalog(),
        getLabRuns(),
      ]);
      setActiveRun(context.active_run);
      setCatalog(validateCatalog(catalogResponse.items));
      setHistory(runs.items);
      setStatus("ready");
    } catch (loadError) {
      setStatus("error");
      setError(
        loadError instanceof Error ? loadError.message : "Synthetic Lab context is unavailable.",
      );
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  const startScenario = useCallback(async (scenarioId: ScenarioId) => {
    if (!APPROVED_SCENARIOS.includes(scenarioId) || scenarioId === "BASELINE") {
      throw new Error("Only approved S1–S4 synthetic scenarios may be started.");
    }
    setBusy(true);
    setError(null);
    try {
      const result = await startLabScenario(scenarioId);
      setActiveRun(result.active_run);
      setHistory((items) => [
        result.run,
        ...items.filter((item) => item.run_id !== result.run.run_id),
      ]);
      setStatus("ready");
      return result.run;
    } catch (startError) {
      const message = startError instanceof Error ? startError.message : "Scenario start failed.";
      setError(message);
      throw startError;
    } finally {
      setBusy(false);
    }
  }, []);

  const returnToBaseline = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await returnLabToBaseline();
      setActiveRun(result.active_run);
      setStatus("ready");
      const runs = await getLabRuns();
      setHistory(runs.items);
    } catch (baselineError) {
      setError(
        baselineError instanceof Error ? baselineError.message : "Baseline selection failed.",
      );
      throw baselineError;
    } finally {
      setBusy(false);
    }
  }, []);

  const resetLab = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await resetSyntheticLab();
      setActiveRun(result.active_run);
      setStatus("ready");
      const runs = await getLabRuns();
      setHistory(runs.items);
    } catch (resetError) {
      setError(resetError instanceof Error ? resetError.message : "Synthetic Lab reset failed.");
      throw resetError;
    } finally {
      setBusy(false);
    }
  }, []);

  const value = useMemo<LabContextValue>(
    () => ({
      status,
      activeRun,
      catalog,
      history,
      error,
      busy,
      refresh,
      startScenario,
      returnToBaseline,
      resetLab,
    }),
    [
      activeRun,
      busy,
      catalog,
      error,
      history,
      refresh,
      resetLab,
      returnToBaseline,
      startScenario,
      status,
    ],
  );

  if (status === "loading") {
    return (
      <main className="app-boot-state" aria-busy="true">
        <strong>Loading Baseline synthetic lab context…</strong>
        <span>No historical scenario is shown as current while context is unresolved.</span>
      </main>
    );
  }
  if (status === "error" || !activeRun) {
    return (
      <main className="app-boot-state" role="alert">
        <strong>Synthetic Lab context is unavailable</strong>
        <span>{error ?? "An active Baseline context was not returned."}</span>
        <button className="button" type="button" onClick={() => void refresh()}>
          Retry context
        </button>
      </main>
    );
  }
  return <LabContext.Provider value={value}>{children}</LabContext.Provider>;
}

// The provider and its hook intentionally share one module so their private context cannot leak.
// eslint-disable-next-line react-refresh/only-export-components
export function useLab(): LabContextValue {
  const value = useContext(LabContext);
  if (!value) throw new Error("useLab must be used within LabProvider.");
  return value;
}
