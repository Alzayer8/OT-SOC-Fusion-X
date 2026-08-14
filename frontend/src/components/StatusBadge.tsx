import type { ReactNode } from "react";

type StatusTone = "neutral" | "info" | "success" | "warning" | "high" | "critical";

interface StatusBadgeProps {
  tone?: StatusTone;
  children: ReactNode;
}

export function StatusBadge({ tone = "neutral", children }: StatusBadgeProps) {
  return (
    <span className={`status-badge status-badge--${tone}`}>
      <span className="status-badge__marker" aria-hidden="true" />
      {children}
    </span>
  );
}
