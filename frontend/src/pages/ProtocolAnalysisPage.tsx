import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getEvidence, getEvidenceList, type EvidenceRecord } from "../api/client";
import { Icon } from "../components/Icons";
import {
  DataTable,
  EvidenceCard,
  ExactStatusBadge,
  LoadingSkeleton,
  ProductEmpty,
  ProductError,
} from "../components/ProductComponents";
import { useApiResource } from "../hooks/useApiResource";
import { useLab } from "../context/LabContext";
import { BarChart, MiniStat, VisualizationPanel } from "../components/Visualizations";
import {
  asRecord,
  displayValue,
  formatMetric,
  formatTimestamp,
  shortId,
  textual,
} from "../utils/presentation";

const TYPES = [
  "synthetic_protocol_event",
  "protocol_semantic_event",
  "asset_context_event",
  "communication_policy_finding",
  "correlation_finding",
];

export function ProtocolAnalysisPage() {
  const lab = useLab();
  const [params, setParams] = useSearchParams();
  const selectedId = params.get("evidence");
  const requestedType = params.get("type");
  const [type, setType] = useState(
    TYPES.includes(requestedType ?? "") ? (requestedType ?? TYPES[0]) : TYPES[0],
  );
  const state = useApiResource(
    `protocol:${lab.activeRun?.run_id}:${type}:${selectedId ?? "list"}`,
    async (signal) => {
      if (selectedId) {
        const selected = await getEvidence(selectedId, signal);
        const payload = asRecord(selected.payload);
        const parentId =
          selected.evidence_type === "protocol_semantic_event"
            ? textual(payload.source_evidence_id)
            : null;
        const parent = parentId ? await getEvidence(parentId, signal) : null;
        return { list: null, selected, parent };
      }
      return {
        list: await getEvidenceList({ evidenceType: type, limit: 50 }, signal),
        selected: null,
        parent: null,
      };
    },
  );
  const chooseType = (next: string) => {
    setType(next);
    setParams({ type: next });
  };
  return (
    <div className="page-stack">
      <header className="product-page-header">
        <div>
          <p className="page-header__eyebrow">Stored protocol evidence</p>
          <h1>Protocol Analysis</h1>
          <p>Offline synthetic Modbus records and separate derived semantic interpretation.</p>
        </div>
        <div className="page-header__context page-header__context--purple">
          <Icon name="protocol" />
          <span>{lab.activeRun?.scenario_id} · RAW → SEMANTIC → CONTEXT</span>
        </div>
      </header>
      <div className="mode-tabs" role="tablist" aria-label="Evidence type">
        {TYPES.map((item) => (
          <button
            key={item}
            role="tab"
            aria-selected={type === item}
            onClick={() => chooseType(item)}
          >
            {item.replaceAll("_", " ")}
          </button>
        ))}
      </div>
      {state.status === "loading" ? <LoadingSkeleton label="Loading protocol evidence" /> : null}
      {state.status === "error" ? <ProductError {...state} /> : null}
      {state.status === "success" ? (
        <ProtocolContent
          {...state.data}
          baseline={lab.activeRun?.scenario_id === "BASELINE"}
          onSelect={(id) => setParams({ evidence: id })}
        />
      ) : null}
      <p className="safety-copy">
        Read-only investigation. There is no Modbus send, write, execute, transmit, capture, scan,
        or PLC connection control.
      </p>
    </div>
  );
}

function ProtocolContent({
  list,
  selected,
  parent,
  baseline,
  onSelect,
}: {
  list: Awaited<ReturnType<typeof getEvidenceList>> | null;
  selected: EvidenceRecord | null;
  parent: EvidenceRecord | null;
  baseline: boolean;
  onSelect: (id: string) => void;
}) {
  if (list) {
    if (!list.items.length)
      return (
        <ProductEmpty
          title={baseline ? "Baseline protocol context" : "No evidence matches"}
          message={
            baseline
              ? "Baseline synthetic evidence is available. No denied communication is present in this run."
              : "No stored evidence matches this exact type and active-run selection. Missing evidence does not imply safety."
          }
        />
      );
    return (
      <>
        <ProtocolListInsights list={list} />
        <DataTable label="Stored evidence records">
          <thead>
            <tr>
              <th>Type</th>
              <th>Observed</th>
              <th>Schema</th>
              <th>Evidence ID</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {list.items.map((item) => (
              <tr key={item.evidence_id}>
                <td>
                  <button className="table-link" onClick={() => onSelect(item.evidence_id)}>
                    {item.evidence_type.replaceAll("_", " ")}
                  </button>
                </td>
                <td>{formatTimestamp(item.observed_at)}</td>
                <td>
                  {item.payload_schema}
                  <small>{item.payload_schema_version}</small>
                </td>
                <td className="mono" title={item.evidence_id}>
                  {shortId(item.evidence_id)}
                </td>
                <td>{item.source_key}</td>
              </tr>
            ))}
          </tbody>
        </DataTable>
        {list.next_cursor ? (
          <p>More bounded results are available through the deterministic cursor.</p>
        ) : null}
      </>
    );
  }
  if (!selected) return null;
  if (selected.evidence_type === "protocol_semantic_event")
    return <RawSemanticView raw={parent} semantic={selected} />;
  if (selected.evidence_type === "synthetic_protocol_event")
    return <RawSemanticView raw={selected} semantic={null} />;
  return (
    <div className="page-stack">
      <EvidenceCard record={selected} />
      <ContextSummary record={selected} />
    </div>
  );
}

function ProtocolListInsights({ list }: { list: Awaited<ReturnType<typeof getEvidenceList>> }) {
  const sourceCounts = new Map<string, number>();
  for (const item of list.items)
    sourceCounts.set(item.source_key, (sourceCounts.get(item.source_key) ?? 0) + 1);
  const sourceData = [...sourceCounts.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([label, value], index) => ({
      label,
      value,
      tone: (["cyan", "purple", "blue", "green"] as const)[index % 4],
    }));
  const schemas = new Set(
    list.items.map((item) => `${item.payload_schema}@${item.payload_schema_version}`),
  );
  return (
    <section className="protocol-browser-summary" aria-label="Current bounded evidence selection">
      <div className="mini-stat-grid mini-stat-grid--compact">
        <MiniStat
          label="Visible Evidence"
          value={list.items.length}
          note="Current bounded selection"
          tone="cyan"
        />
        <MiniStat
          label="Source Keys"
          value={sourceCounts.size}
          note="Derived from returned records"
          tone="purple"
        />
        <MiniStat
          label="Typed Schemas"
          value={schemas.size}
          note="Schema + version pairs"
          tone="blue"
        />
        <MiniStat
          label="More Results"
          value={list.next_cursor ? "YES" : "NO"}
          note="Opaque cursor status"
          tone="green"
        />
      </div>
      <VisualizationPanel title="Evidence Sources" eyebrow="Current bounded selection">
        <BarChart title="Evidence records by source key" data={sourceData} />
      </VisualizationPanel>
    </section>
  );
}

function RawSemanticView({
  raw,
  semantic,
}: {
  raw: EvidenceRecord | null;
  semantic: EvidenceRecord | null;
}) {
  const rawPayload = raw ? asRecord(raw.payload) : {};
  const semanticPayload = semantic ? asRecord(semantic.payload) : {};
  const verified = Boolean(
    raw &&
    semantic &&
    textual(semanticPayload.source_evidence_id) === raw.evidence_id &&
    textual(semanticPayload.source_evidence_integrity_sha256) === raw.integrity_sha256,
  );
  return (
    <div className="raw-semantic">
      <section className="evidence-stage evidence-stage--raw">
        <header>
          <span>
            <Icon name="database" /> RAW EVIDENCE
          </span>
          <h2>Offline synthetic Modbus evidence</h2>
        </header>
        {raw ? (
          <>
            <dl className="detail-grid">
              <div>
                <dt>Function code</dt>
                <dd>{displayValue(rawPayload.function_code)}</dd>
              </div>
              <div>
                <dt>Unit ID</dt>
                <dd>{displayValue(rawPayload.unit_id)}</dd>
              </div>
              <div>
                <dt>Table</dt>
                <dd>{displayValue(rawPayload.table_type)}</dd>
              </div>
              <div>
                <dt>Zero-based offset</dt>
                <dd>{displayValue(rawPayload.address_offset)}</dd>
              </div>
              <div>
                <dt>Raw value</dt>
                <dd>{displayValue(rawPayload.raw_value)}</dd>
              </div>
              <div>
                <dt>Observed</dt>
                <dd>{formatTimestamp(raw.observed_at)}</dd>
              </div>
              <div>
                <dt>Evidence ID</dt>
                <dd className="mono" title={raw.evidence_id}>
                  {shortId(raw.evidence_id)}
                </dd>
              </div>
              <div>
                <dt>Integrity SHA</dt>
                <dd className="mono" title={raw.integrity_sha256}>
                  {shortId(raw.integrity_sha256)}
                </dd>
              </div>
            </dl>
          </>
        ) : (
          <ProductEmpty
            title="Raw parent unavailable"
            message="The semantic source record could not be verified."
          />
        )}
      </section>
      <div className="derivation-arrow" aria-label="Derived from raw evidence">
        →<span>DERIVED FROM</span>
      </div>
      <section className="evidence-stage evidence-stage--semantic">
        <header>
          <span>
            <Icon name="protocol" /> SEMANTIC TRANSLATION
          </span>
          <h2>Derived typed interpretation</h2>
        </header>
        {semantic ? (
          <>
            <div className="status-row">
              <ExactStatusBadge
                value={displayValue(semanticPayload.interpretation_status, "UNAVAILABLE")}
              />
              {verified ? (
                <ExactStatusBadge value="VERIFIED LINEAGE" />
              ) : (
                <ExactStatusBadge value="PARTIAL LINEAGE" />
              )}
            </div>
            <dl className="detail-grid">
              <div>
                <dt>Operation</dt>
                <dd>{displayValue(semanticPayload.operation_category)}</dd>
              </div>
              <div>
                <dt>Mapped point</dt>
                <dd>{displayValue(semanticPayload.point_id)}</dd>
              </div>
              <div>
                <dt>Scaled value</dt>
                <dd>
                  {formatMetric(
                    semanticPayload.decoded_value,
                    displayValue(semanticPayload.unit, ""),
                  )}
                </dd>
              </div>
              <div>
                <dt>Mapping result</dt>
                <dd>{displayValue(semanticPayload.reason_code)}</dd>
              </div>
              <div>
                <dt>Profile</dt>
                <dd>
                  {displayValue(semanticPayload.profile_id)}{" "}
                  {displayValue(semanticPayload.profile_version, "")}
                </dd>
              </div>
              <div>
                <dt>Source evidence</dt>
                <dd className="mono">
                  {shortId(displayValue(semanticPayload.source_evidence_id))}
                </dd>
              </div>
            </dl>
            <p className="evidence-statement">
              {displayValue(semanticPayload.semantic_statement, "Semantic meaning unavailable.")}
            </p>
            <div className="semantic-provenance">
              <span>Decoder</span>
              <strong>{displayValue(semanticPayload.decoder_name)}</strong>
              <span>Version</span>
              <strong>{displayValue(semanticPayload.decoder_version)}</strong>
            </div>
          </>
        ) : (
          <ProductEmpty
            title="Semantic derivative unavailable"
            message="No verified semantic derivative is selected for this raw record."
          />
        )}
      </section>
    </div>
  );
}

function ContextSummary({ record }: { record: EvidenceRecord }) {
  const payload = asRecord(record.payload);
  const status = displayValue(
    payload.policy_status ?? payload.correlation_status,
    "STORED EVIDENCE",
  );
  const isCorrelation = record.evidence_type === "correlation_finding";
  return (
    <section className="panel">
      <div className="panel__header">
        <h2>{isCorrelation ? "Cyber-physical correlation context" : "Evidence context"}</h2>
      </div>
      <div className="panel__content">
        <ExactStatusBadge value={status} />
        <p>
          {isCorrelation && status === "CORRELATED"
            ? "Temporally Correlated under the selected synthetic rule. This does not establish cause or malicious intent."
            : record.evidence_type === "communication_policy_finding" && status === "DENIED"
              ? "Not approved by the selected synthetic policy. This does not establish maliciousness."
              : "Exact stored evidence context."}
        </p>
        {isCorrelation && textual(payload.simulation_id) ? (
          <Link to={`/digital-twin?correlation=${record.evidence_id}`}>
            Open read-only Digital Twin
          </Link>
        ) : null}
      </div>
    </section>
  );
}
