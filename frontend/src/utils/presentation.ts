export function formatTimestamp(value: string, local = false): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: local ? undefined : "UTC",
  }).format(date);
}

export function shortId(value: string): string {
  return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;
}

export function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {};
}

export function numeric(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && /^-?(?:\d+\.?\d*|\.\d+)$/.test(value)) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function textual(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export function displayValue(value: unknown, fallback = "Unavailable"): string {
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean"
    ? String(value)
    : fallback;
}

export function formatMetric(value: unknown, suffix: string, digits = 1): string {
  const number = numeric(value);
  return number === null ? "Unavailable" : `${number.toFixed(digits)} ${suffix}`;
}
