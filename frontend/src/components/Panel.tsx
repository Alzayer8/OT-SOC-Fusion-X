import type { ReactNode } from "react";

interface PanelProps {
  title: string;
  children: ReactNode;
  ariaLabel?: string;
}

export function Panel({ title, children, ariaLabel }: PanelProps) {
  return (
    <section className="panel" aria-label={ariaLabel ?? title}>
      <div className="panel__header">
        <h2>{title}</h2>
      </div>
      <div className="panel__content">{children}</div>
    </section>
  );
}
