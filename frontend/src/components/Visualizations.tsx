import type { ReactNode } from "react";

export type ChartTone = "blue" | "cyan" | "green" | "amber" | "red" | "purple" | "slate";

export interface ChartDatum {
  label: string;
  value: number;
  tone?: ChartTone;
}

export interface TrendPoint {
  x: number;
  label: string;
  value: number;
}

export interface TrendSeries {
  label: string;
  tone: ChartTone;
  unit: string;
  points: TrendPoint[];
}

export function VisualizationPanel({
  title,
  eyebrow,
  children,
  className = "",
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`visual-panel ${className}`.trim()}>
      <header className="visual-panel__header">
        <div>
          {eyebrow ? <span>{eyebrow}</span> : null}
          <h2>{title}</h2>
        </div>
      </header>
      <div className="visual-panel__body">{children}</div>
    </section>
  );
}

export function EmptyVisualization({ message }: { message: string }) {
  return (
    <div className="empty-visualization" role="status">
      <span aria-hidden="true">—</span>
      <p>{message}</p>
    </div>
  );
}

export function DonutChart({
  title,
  data,
  centerLabel = "total",
}: {
  title: string;
  data: ChartDatum[];
  centerLabel?: string;
}) {
  const clean = data.filter((item) => item.value >= 0 && Number.isFinite(item.value));
  const total = clean.reduce((sum, item) => sum + item.value, 0);
  if (total === 0) return <EmptyVisualization message={`${title}: no sourced records.`} />;
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const segments = clean.map((item, index) => {
    const length = (item.value / total) * circumference;
    const consumed = clean
      .slice(0, index)
      .reduce((sum, previous) => sum + (previous.value / total) * circumference, 0);
    return { item, index, length, offset: -consumed };
  });
  const summary = clean.map((item) => `${item.label} ${item.value}`).join(", ");
  return (
    <figure className="donut-chart">
      <svg role="img" aria-label={`${title}. ${summary}. Total ${total}.`} viewBox="0 0 120 120">
        <circle className="donut-chart__track" cx="60" cy="60" r={radius} />
        {segments.map(({ item, index, length, offset }) => {
          return (
            <circle
              className={`chart-stroke chart-stroke--${item.tone ?? "blue"}`}
              cx="60"
              cy="60"
              key={`${item.label}:${index}`}
              r={radius}
              strokeDasharray={`${length} ${circumference - length}`}
              strokeDashoffset={offset}
            />
          );
        })}
        <text className="donut-chart__value" x="60" y="58" textAnchor="middle">
          {total}
        </text>
        <text className="donut-chart__label" x="60" y="72" textAnchor="middle">
          {centerLabel}
        </text>
      </svg>
      <figcaption className="chart-legend">
        {clean.map((item, index) => (
          <span key={`${item.label}:${index}`}>
            <i className={`chart-swatch chart-fill--${item.tone ?? "blue"}`} aria-hidden="true" />
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

export function BarChart({ title, data }: { title: string; data: ChartDatum[] }) {
  const clean = data.filter((item) => item.value >= 0 && Number.isFinite(item.value));
  const maximum = Math.max(0, ...clean.map((item) => item.value));
  if (maximum === 0) return <EmptyVisualization message={`${title}: no sourced records.`} />;
  return (
    <figure className="bar-chart" aria-label={title}>
      {clean.map((item, index) => {
        const width = (item.value / maximum) * 100;
        return (
          <div className="bar-chart__row" key={`${item.label}:${index}`}>
            <div>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
            <div
              className="bar-chart__track"
              role="img"
              aria-label={`${item.label}: ${item.value}`}
            >
              <span
                className={`chart-fill--${item.tone ?? "blue"}`}
                style={{ width: `${width}%` }}
              />
            </div>
          </div>
        );
      })}
      <figcaption className="sr-only">
        {clean.map((item) => `${item.label}: ${item.value}`).join("; ")}
      </figcaption>
    </figure>
  );
}

function pointsFor(series: TrendSeries, min: number, max: number, xMin: number, xMax: number) {
  const span = max - min || 1;
  const xSpan = xMax - xMin || 1;
  return series.points.map((point) => ({
    ...point,
    svgX: 34 + ((point.x - xMin) / xSpan) * 432,
    svgY: 152 - ((point.value - min) / span) * 124,
  }));
}

export function TrendChart({
  title,
  series,
  cursorX,
}: {
  title: string;
  series: TrendSeries[];
  cursorX?: number;
}) {
  const visible = series.filter((item) => item.points.length >= 2);
  const all = visible.flatMap((item) => item.points);
  if (!all.length)
    return <EmptyVisualization message={`${title}: compatible stored history unavailable.`} />;
  const min = Math.min(...all.map((item) => item.value));
  const max = Math.max(...all.map((item) => item.value));
  const xMin = Math.min(...all.map((item) => item.x));
  const xMax = Math.max(...all.map((item) => item.x));
  const cursorSvg =
    cursorX === undefined
      ? null
      : 34 + ((Math.min(Math.max(cursorX, xMin), xMax) - xMin) / (xMax - xMin || 1)) * 432;
  const summary = visible
    .map((item) => `${item.label}: ${item.points.length} stored points in ${item.unit}`)
    .join("; ");
  return (
    <figure className="trend-chart">
      <svg
        role="img"
        aria-label={`${title}. ${summary}.`}
        viewBox="0 0 480 180"
        preserveAspectRatio="none"
      >
        <g className="trend-chart__grid" aria-hidden="true">
          {[28, 59, 90, 121, 152].map((y) => (
            <line key={y} x1="34" x2="466" y1={y} y2={y} />
          ))}
        </g>
        {visible.map((item) => {
          const rendered = pointsFor(item, min, max, xMin, xMax);
          return (
            <g className={`trend-chart__series chart-stroke--${item.tone}`} key={item.label}>
              <polyline points={rendered.map((point) => `${point.svgX},${point.svgY}`).join(" ")} />
              {rendered.map((point, index) => (
                <circle key={`${point.label}:${index}`} cx={point.svgX} cy={point.svgY} r="2.5">
                  <title>{`${item.label}: ${point.value} ${item.unit} at ${point.label}`}</title>
                </circle>
              ))}
            </g>
          );
        })}
        {cursorSvg !== null ? (
          <line className="trend-chart__cursor" x1={cursorSvg} x2={cursorSvg} y1="22" y2="158" />
        ) : null}
        <text className="trend-chart__axis" x="34" y="174">
          {min.toFixed(1)}
        </text>
        <text className="trend-chart__axis" x="466" y="174" textAnchor="end">
          {max.toFixed(1)}
        </text>
      </svg>
      <figcaption className="chart-legend chart-legend--inline">
        {visible.map((item) => (
          <span key={item.label}>
            <i className={`chart-swatch chart-fill--${item.tone}`} aria-hidden="true" />
            <span>{item.label}</span>
            <small>
              {item.points.length} stored points · {item.unit}
            </small>
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

export function MiniStat({
  label,
  value,
  note,
  tone = "blue",
}: {
  label: string;
  value: string | number;
  note?: string;
  tone?: ChartTone;
}) {
  return (
    <div className={`mini-stat mini-stat--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {note ? <small>{note}</small> : null}
    </div>
  );
}
