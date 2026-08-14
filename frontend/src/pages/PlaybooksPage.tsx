import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ExactStatusBadge, SafetyBanner } from "../components/ProductComponents";
import { Icon } from "../components/Icons";
import { MiniStat } from "../components/Visualizations";
import { useAuth } from "../auth/AuthContext";

const PLAYBOOKS = [
  {
    id: "S1",
    title: "Unknown OT Asset Review",
    category: "ASSET_IDENTITY_ANOMALY",
    purpose: "Review an unresolved or conflicting synthetic identity claim.",
    evidence: [
      "Raw and semantic linkage",
      "Asset-context resolution",
      "Inventory profile and digest",
    ],
    checks: [
      "Verify exact typed identity claims.",
      "Distinguish UNKNOWN from CONFLICT.",
      "Document missing context without inferring safety.",
    ],
  },
  {
    id: "S2",
    title: "Unexpected IT-to-PLC Communication Review",
    category: "COMMUNICATION_POLICY_VIOLATION",
    purpose: "Review stored communication not approved by the selected synthetic policy.",
    evidence: [
      "Source and destination resolution",
      "Zone and authorization dimensions",
      "Matched policy rule and reason",
    ],
    checks: [
      "Confirm both identities and zones.",
      "Review operation, point, and access class.",
      "State DENIED as not approved, never malicious.",
    ],
  },
  {
    id: "S3",
    title: "Control Command Investigation",
    category: "CONTROL_COMMAND_INVESTIGATION",
    purpose: "Inspect a stored CV-101 command and independent process observations.",
    evidence: [
      "Raw FC06 and semantic command",
      "Policy and asset context",
      "Correlation and telemetry parents",
    ],
    checks: [
      "Verify CV-101 command 25.0% when present.",
      "Keep command, observed position, and process effect separate.",
      "Use temporally correlated wording only.",
    ],
  },
  {
    id: "S4",
    title: "Pump / Flow Process Inconsistency Review",
    category: "PROCESS_INCONSISTENCY",
    purpose: "Inspect configured P-101/PL-101 process inconsistency without inventing cyber cause.",
    evidence: [
      "Pump running state",
      "Flow and pressure observations",
      "Tank-level stagnation and correlation reason",
    ],
    checks: [
      "Confirm one simulation and configuration.",
      "Review sample completeness and gaps.",
      "Do not add a cyber event or causal claim.",
    ],
  },
] as const;

export function PlaybooksPage() {
  const auth = useAuth();
  const [params, setParams] = useSearchParams();
  const incidentId = params.get("incident");
  const [selectedId, setSelectedId] = useState(params.get("type") ?? "S1");
  const [reviewed, setReviewed] = useState<Record<string, boolean>>({});
  const canReview = auth.hasRole("ADMIN", "SOC_ANALYST");
  const playbook = useMemo(
    () => PLAYBOOKS.find((item) => item.id === selectedId) ?? PLAYBOOKS[0],
    [selectedId],
  );
  const select = (id: string) => {
    setSelectedId(id);
    const next = new URLSearchParams(params);
    next.set("type", id);
    setParams(next);
  };
  return (
    <div className="page-stack">
      <header className="product-page-header">
        <div>
          <p className="page-header__eyebrow">Advisory investigation guidance</p>
          <h1>Playbooks</h1>
          <p>Four static S1–S4 review guides. No action has been executed.</p>
        </div>
        <div className="page-header__context">
          <Icon name="playbooks" />
          <span>Review · inspect · verify · document</span>
        </div>
      </header>
      <SafetyBanner />
      {incidentId ? (
        <div className="playbook-incident-link">
          <span>
            Linked incident <code>{incidentId}</code>
          </span>
          <Link to={`/incidents/${incidentId}?tab=investigation`}>Return to Incident</Link>
        </div>
      ) : null}
      <section className="playbook-scope-strip" aria-label="Advisory playbook scope">
        <MiniStat
          label="Approved Guides"
          value={PLAYBOOKS.length}
          note="Exactly S1–S4"
          tone="blue"
        />
        <MiniStat label="Execution" value="NONE" note="Advisory guidance only" tone="green" />
        <MiniStat
          label="Persistence"
          value="NONE"
          note="Selection is browser-local"
          tone="purple"
        />
        <MiniStat label="Process Control" value="NONE" note="No OT actions" tone="cyan" />
      </section>
      <div className="split-workspace">
        <section className="panel">
          <div className="panel__header">
            <h2>Approved advisory guides</h2>
          </div>
          <div className="playbook-list">
            {PLAYBOOKS.map((item) => (
              <button
                key={item.id}
                className={item.id === playbook.id ? "selected" : ""}
                onClick={() => select(item.id)}
              >
                <span>{item.id}</span>
                <div>
                  <strong>{item.title}</strong>
                  <small>{item.category}</small>
                  <p>Review guide · advisory only</p>
                </div>
              </button>
            ))}
          </div>
        </section>
        <section className="panel playbook-detail">
          <div className="panel__header">
            <h2>{playbook.title}</h2>
            <ExactStatusBadge value="ADVISORY ONLY" />
          </div>
          <div className="panel__content">
            <p>{playbook.purpose}</p>
            <h3>Evidence to inspect</h3>
            <ul className="playbook-evidence-list">
              {playbook.evidence.map((item) => (
                <li key={item}>
                  <Icon name="evidence" />
                  {item}
                </li>
              ))}
            </ul>
            <h3>Recommended analyst checks</h3>
            <ol
              className="playbook-checklist"
              aria-label={`${playbook.id} analyst review checklist`}
            >
              {playbook.checks.map((item, index) => (
                <li key={item}>
                  <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                  <label>
                    <input
                      checked={Boolean(reviewed[`${playbook.id}:${index}`])}
                      disabled={!canReview}
                      type="checkbox"
                      onChange={(event) =>
                        setReviewed((current) => ({
                          ...current,
                          [`${playbook.id}:${index}`]: event.target.checked,
                        }))
                      }
                    />
                    <span>{item}</span>
                  </label>
                </li>
              ))}
            </ol>
            <p className="safety-copy">
              Checklist state is browser-memory review state only. It does not execute or complete
              remediation.
              {!canReview
                ? " Your authenticated role may read this guidance but cannot mark review state."
                : ""}
            </p>
            <div className="advisory-note">
              <strong>Documentation guidance</strong>
              <p>
                Record exact evidence IDs, profile versions, observed timestamps, and uncertainty.
                Use analyst notes or approved lifecycle status only.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
