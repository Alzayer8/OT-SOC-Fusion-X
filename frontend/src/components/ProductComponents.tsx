import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { EvidenceRecord } from "../api/client";
import { asRecord, formatTimestamp, shortId } from "../utils/presentation";
import { Icon, type IconName } from "./Icons";
import { Panel } from "./Panel";

export function LoadingSkeleton({ label = "Loading product data" }: { label?: string }) {
  return (
    <div className="loading-grid" aria-busy="true" aria-label={label}>
      <span className="skeleton" />
      <span className="skeleton" />
      <span className="skeleton skeleton--wide" />
    </div>
  );
}

export function ProductError({
  message,
  statusCode,
  requestId,
}: {
  message: string;
  statusCode?: number;
  requestId?: string;
}) {
  const title =
    statusCode === 403
      ? "Access unavailable"
      : statusCode === 404
        ? "Not found"
        : "Data unavailable";
  return (
    <div className="state state--error" role="alert">
      <span className="state__symbol" aria-hidden="true">
        !
      </span>
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
        {requestId ? <p className="mono">Request {requestId}</p> : null}
      </div>
    </div>
  );
}

export function ProductEmpty({ title, message }: { title: string; message: string }) {
  return (
    <div className="state">
      <span className="state__symbol" aria-hidden="true">
        —
      </span>
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
    </div>
  );
}

export function KpiCard({
  label,
  value,
  note,
  tone = "info",
  to,
  icon,
}: {
  label: string;
  value: string | number;
  note: string;
  tone?: "info" | "success" | "warning" | "high" | "critical";
  to?: string;
  icon?: IconName;
}) {
  const body = (
    <div className={`kpi-card kpi-card--${tone}`}>
      <span className="kpi-card__icon" aria-hidden="true">
        <Icon name={icon ?? "activity"} />
      </span>
      <span className="kpi-card__label">{label}</span>
      <strong>{value}</strong>
      <span>{note}</span>
    </div>
  );
  return to ? (
    <Link className="kpi-link" to={to}>
      {body}
    </Link>
  ) : (
    body
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tone = severity === "HIGH" ? "critical" : severity === "MEDIUM" ? "warning" : "success";
  const symbol = severity === "HIGH" ? "▲" : severity === "MEDIUM" ? "◆" : "●";
  return (
    <span className={`severity severity--${tone}`}>
      <span aria-hidden="true">{symbol}</span>
      {severity}
    </span>
  );
}

export function ExactStatusBadge({ value }: { value: string }) {
  const tone = ["OPEN", "DENIED", "CORRELATED", "UNAVAILABLE"].includes(value)
    ? "warning"
    : ["RESOLVED", "APPROVED", "COMPLETE", "READY"].includes(value)
      ? "success"
      : "info";
  return (
    <span className={`exact-status exact-status--${tone}`}>
      <span aria-hidden="true">●</span>
      {value}
    </span>
  );
}

export function DataTable({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className="table-scroll" role="region" aria-label={label} tabIndex={0}>
      <table className="data-table">{children}</table>
    </div>
  );
}

export function EvidenceCard({ record, title }: { record: EvidenceRecord; title?: string }) {
  const payload = asRecord(record.payload);
  const semantic =
    typeof payload.semantic_statement === "string"
      ? payload.semantic_statement
      : typeof payload.analyst_readable_statement === "string"
        ? payload.analyst_readable_statement
        : typeof payload.analyst_readable_explanation === "string"
          ? payload.analyst_readable_explanation
          : null;
  return (
    <Panel title={title ?? record.evidence_type.replaceAll("_", " ").toUpperCase()}>
      <dl className="detail-grid">
        <div>
          <dt>Evidence ID</dt>
          <dd className="mono" title={record.evidence_id}>
            {shortId(record.evidence_id)}
          </dd>
        </div>
        <div>
          <dt>Schema</dt>
          <dd>
            {record.payload_schema} {record.payload_schema_version}
          </dd>
        </div>
        <div>
          <dt>Observed</dt>
          <dd>{formatTimestamp(record.observed_at)}</dd>
        </div>
        <div>
          <dt>Integrity SHA-256</dt>
          <dd className="mono" title={record.integrity_sha256}>
            {shortId(record.integrity_sha256)}
          </dd>
        </div>
      </dl>
      {semantic ? <p className="evidence-statement">{semantic}</p> : null}
      <details>
        <summary>Typed payload and provenance</summary>
        <pre className="json-view">
          {JSON.stringify({ payload: record.payload, provenance: record.provenance }, null, 2)}
        </pre>
      </details>
    </Panel>
  );
}

export function SafetyBanner() {
  return (
    <div className="safety-banner">
      <strong>Synthetic / Offline</strong>
      <span>Stored evidence only · advisory investigation · no live OT connection or control</span>
    </div>
  );
}
