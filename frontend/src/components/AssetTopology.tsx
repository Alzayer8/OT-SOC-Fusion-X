import type { AssetCatalog } from "../api/client";

const positions: Record<string, [number, number]> = {
  "IT-WS-01": [55, 48],
  "ENG-WS-01": [200, 48],
  "HMI-01": [340, 48],
  "MON-01": [55, 155],
  "PLC-01": [270, 155],
  "SOC-01": [485, 155],
  "TK-101": [80, 270],
  "P-101": [205, 270],
  "PL-101": [330, 270],
  "CV-101": [455, 270],
  "TK-102": [580, 270],
  "OTSOC-MB-UNIT-01": [270, 360],
};

export function AssetTopology({ catalog }: { catalog: AssetCatalog }) {
  const assetMap = new Map(catalog.assets.map((item) => [item.definition.asset_key, item]));
  return (
    <figure className="asset-topology">
      <svg
        viewBox="0 0 660 410"
        role="img"
        aria-label={`Approved asset relationship topology: ${catalog.assets.length} assets and ${catalog.relationships.length} relationships.`}
      >
        <defs>
          <marker
            id="topology-arrow"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" />
          </marker>
        </defs>
        <rect
          className="topology-zone topology-zone--cyber"
          x="20"
          y="18"
          width="620"
          height="205"
          rx="12"
        />
        <text className="topology-zone-label" x="34" y="40">
          CYBER / OBSERVATION CONTEXT
        </text>
        <rect
          className="topology-zone topology-zone--process"
          x="20"
          y="235"
          width="620"
          height="90"
          rx="12"
        />
        <text className="topology-zone-label" x="34" y="257">
          PROCESS CONTEXT
        </text>
        {catalog.relationships.map((relation, index) => {
          const source = positions[relation.source_asset_key];
          const target = positions[relation.target_ref];
          if (!source || !target) return null;
          return (
            <line
              className={`topology-edge topology-edge--${relation.relationship_type.toLowerCase()}`}
              key={`${relation.relationship_type}:${relation.source_asset_key}:${relation.target_ref}:${index}`}
              markerEnd="url(#topology-arrow)"
              x1={source[0]}
              y1={source[1] + 16}
              x2={target[0]}
              y2={target[1] - 16}
            >
              <title>{`${relation.source_asset_key} ${relation.relationship_type.replaceAll("_", " ")} ${relation.target_ref}`}</title>
            </line>
          );
        })}
        {[...catalog.assets.map((item) => item.definition.asset_key), "OTSOC-MB-UNIT-01"].map(
          (key) => {
            const position = positions[key];
            if (!position) return null;
            const asset = assetMap.get(key);
            const kind = asset?.definition.asset_kind ?? "ENDPOINT";
            return (
              <g
                className={`topology-node topology-node--${kind.toLowerCase()}`}
                key={key}
                transform={`translate(${position[0]}, ${position[1]})`}
              >
                <rect x="-45" y="-17" width="90" height="34" rx="6" />
                <text textAnchor="middle" y="4">
                  {key}
                </text>
                <title>
                  {asset
                    ? `${key}, ${asset.definition.display_name}, ${kind}`
                    : `${key}, approved synthetic endpoint`}
                </title>
              </g>
            );
          },
        )}
      </svg>
      <figcaption>
        <span>
          <i className="topology-key topology-key--cyber" />
          Cyber asset
        </span>
        <span>
          <i className="topology-key topology-key--process" />
          Process asset
        </span>
        <span>
          <i className="topology-key topology-key--endpoint" />
          Synthetic endpoint
        </span>
        <strong>{catalog.relationships.length} approved relationships only</strong>
      </figcaption>
    </figure>
  );
}
