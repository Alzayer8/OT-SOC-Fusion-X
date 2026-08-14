import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getAssetCatalog } from "../api/client";
import { AssetTopology } from "../components/AssetTopology";
import { Icon } from "../components/Icons";
import {
  DataTable,
  ExactStatusBadge,
  LoadingSkeleton,
  ProductError,
  ProductEmpty,
  SeverityBadge,
} from "../components/ProductComponents";
import { useApiResource } from "../hooks/useApiResource";
import { useLab } from "../context/LabContext";
import { BarChart, DonutChart, VisualizationPanel } from "../components/Visualizations";

export function AssetInventoryPage() {
  const lab = useLab();
  const state = useApiResource("assets", getAssetCatalog);
  const [kind, setKind] = useState("");
  const [zone, setZone] = useState("");
  const [params, setParams] = useSearchParams();
  const selected = params.get("asset");
  const catalog = state.status === "success" ? state.data : null;
  const assets = useMemo(
    () =>
      (catalog?.assets ?? []).filter(
        (item) =>
          (!kind || item.definition.asset_kind === kind) &&
          (!zone || item.definition.zone_id === zone),
      ),
    [catalog, kind, zone],
  );
  const selectedAsset = catalog?.assets.find((item) => item.definition.asset_key === selected);

  return (
    <div className="page-stack">
      <header className="product-page-header">
        <div>
          <p className="page-header__eyebrow">Approved static context</p>
          <h1>Asset Inventory</h1>
          <p>Exact fictional assets, zones, roles, and relationships. No discovery or scanning.</p>
        </div>
        <div className="page-header__context">
          <Icon name="assets" />
          <span>Approved static profile</span>
        </div>
      </header>
      {state.status === "loading" ? <LoadingSkeleton label="Loading asset catalog" /> : null}
      {state.status === "error" ? <ProductError {...state} /> : null}
      {catalog ? (
        <>
          <AssetSummary catalog={catalog} />
          <section className="filter-bar" aria-label="Asset filters">
            <label>
              Asset kind
              <select value={kind} onChange={(event) => setKind(event.target.value)}>
                <option value="">All kinds</option>
                <option value="CYBER">Cyber Asset</option>
                <option value="PROCESS">Process Asset</option>
              </select>
            </label>
            <label>
              Zone
              <select value={zone} onChange={(event) => setZone(event.target.value)}>
                <option value="">All zones</option>
                {catalog.zones.map((item) => (
                  <option key={item.zone_id} value={item.zone_id}>
                    {item.zone_id}
                  </option>
                ))}
              </select>
            </label>
            <span>
              {assets.length} of {catalog.assets.length} approved assets
            </span>
          </section>
          {assets.length === 0 ? (
            <ProductEmpty title="No assets match" message="Change the selected catalog filters." />
          ) : (
            <DataTable label="Synthetic asset inventory">
              <thead>
                <tr>
                  <th>Identity</th>
                  <th>Kind</th>
                  <th>Type / Role</th>
                  <th>Zone</th>
                  <th>Criticality</th>
                  <th>Enabled</th>
                </tr>
              </thead>
              <tbody>
                {assets.map((item) => (
                  <tr key={item.asset_id}>
                    <td>
                      <button
                        className="table-link"
                        onClick={() => setParams({ asset: item.definition.asset_key })}
                      >
                        <strong>{item.definition.asset_key}</strong>
                        <span>{item.definition.display_name}</span>
                      </button>
                    </td>
                    <td>
                      {item.definition.asset_kind === "CYBER" ? "Cyber Asset" : "Process Asset"}
                    </td>
                    <td>
                      {item.definition.asset_type}
                      <small>{item.definition.asset_role}</small>
                    </td>
                    <td>{item.definition.zone_id}</td>
                    <td>
                      <SeverityBadge
                        severity={
                          item.definition.criticality === "CRITICAL"
                            ? "HIGH"
                            : item.definition.criticality
                        }
                      />
                    </td>
                    <td>
                      <ExactStatusBadge value={item.definition.enabled ? "ENABLED" : "DISABLED"} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
          <VisualizationPanel
            title="Approved Relationship Topology"
            eyebrow="Read-only · exact catalog edges"
          >
            <AssetTopology catalog={catalog} />
          </VisualizationPanel>
          {selectedAsset ? (
            <section className="panel asset-detail">
              <div className="panel__header">
                <h2>
                  {selectedAsset.definition.asset_key} · {selectedAsset.definition.display_name}
                </h2>
              </div>
              <div className="panel__content">
                <dl className="detail-grid">
                  <div>
                    <dt>Asset ID</dt>
                    <dd className="mono">{selectedAsset.asset_id}</dd>
                  </div>
                  <div>
                    <dt>Kind</dt>
                    <dd>{selectedAsset.definition.asset_kind}</dd>
                  </div>
                  <div>
                    <dt>Zone</dt>
                    <dd>{selectedAsset.definition.zone_id}</dd>
                  </div>
                  <div>
                    <dt>Protocol capabilities</dt>
                    <dd>{selectedAsset.definition.protocol_capabilities.join(", ") || "None"}</dd>
                  </div>
                  <div>
                    <dt>Process points</dt>
                    <dd>{selectedAsset.process_point_ids.join(", ") || "None"}</dd>
                  </div>
                  <div>
                    <dt>Profile</dt>
                    <dd>{catalog.profile_version}</dd>
                  </div>
                </dl>
                <h3>Approved relationships</h3>
                <ul className="relationship-list">
                  {catalog.relationships
                    .filter(
                      (item) =>
                        item.source_asset_key === selectedAsset.definition.asset_key ||
                        item.target_ref === selectedAsset.definition.asset_key,
                    )
                    .map((item) => (
                      <li
                        key={`${item.relationship_type}:${item.source_asset_key}:${item.target_ref}`}
                      >
                        <strong>{item.source_asset_key}</strong>{" "}
                        {item.relationship_type.replaceAll("_", " ")}{" "}
                        <strong>{item.target_ref}</strong>
                      </li>
                    ))}
                </ul>
                <div className="action-links">
                  <Link
                    to={`/incidents?scope=CURRENT&run=${encodeURIComponent(lab.activeRun?.run_id ?? "")}&asset=${selectedAsset.asset_id}`}
                  >
                    Current-run incidents
                  </Link>
                  <Link to={`/incidents?scope=HISTORY&asset=${selectedAsset.asset_id}`}>
                    All-history incidents
                  </Link>
                  {selectedAsset.definition.asset_kind === "PROCESS" ? (
                    <Link to={`/digital-twin?asset=${selectedAsset.definition.asset_key}`}>
                      View in Digital Twin
                    </Link>
                  ) : null}
                </div>
              </div>
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function AssetSummary({ catalog }: { catalog: Awaited<ReturnType<typeof getAssetCatalog>> }) {
  const cyber = catalog.assets.filter((item) => item.definition.asset_kind === "CYBER").length;
  const process = catalog.assets.filter((item) => item.definition.asset_kind === "PROCESS").length;
  const enabled = catalog.assets.filter((item) => item.definition.enabled).length;
  const disabled = catalog.assets.length - enabled;
  const zoneData = catalog.zones.map((zone, index) => ({
    label: zone.zone_id.replaceAll("_", " "),
    value: catalog.assets.filter((item) => item.definition.zone_id === zone.zone_id).length,
    tone: (["slate", "blue", "cyan", "purple", "green"] as const)[index],
  }));
  return (
    <section className="asset-summary-grid" aria-label="Approved asset catalog summary">
      <VisualizationPanel title="Cyber vs Process" eyebrow="Exact inventory profile">
        <DonutChart
          title="Cyber versus process asset distribution"
          centerLabel="assets"
          data={[
            { label: "Cyber", value: cyber, tone: "blue" },
            { label: "Process", value: process, tone: "cyan" },
          ]}
        />
      </VisualizationPanel>
      <VisualizationPanel title="Enabled State" eyebrow="Exact inventory profile">
        <DonutChart
          title="Asset enabled-state distribution"
          centerLabel="assets"
          data={[
            { label: "Enabled", value: enabled, tone: "green" },
            { label: "Disabled", value: disabled, tone: "slate" },
          ]}
        />
      </VisualizationPanel>
      <VisualizationPanel
        title="Zone Distribution"
        eyebrow={`${catalog.zones.length} approved zones`}
        className="visual-panel--wide"
      >
        <BarChart title="Assets by approved zone" data={zoneData} />
      </VisualizationPanel>
    </section>
  );
}
