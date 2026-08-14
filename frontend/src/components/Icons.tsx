import type { SVGProps } from "react";

export type IconName =
  | "overview"
  | "incidents"
  | "protocol"
  | "twin"
  | "assets"
  | "replay"
  | "playbooks"
  | "reports"
  | "settings"
  | "shield"
  | "activity"
  | "database"
  | "link"
  | "evidence"
  | "clock";

const paths: Record<IconName, React.ReactNode> = {
  overview: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="4" rx="1" />
      <rect x="14" y="11" width="7" height="10" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
    </>
  ),
  incidents: (
    <>
      <path d="M12 3 2.8 20h18.4L12 3Z" />
      <path d="M12 9v5" />
      <path d="M12 17.5h.01" />
    </>
  ),
  protocol: (
    <>
      <path d="M7 4h10v5H7zM4 15h6v5H4zM14 15h6v5h-6z" />
      <path d="M12 9v3M7 12h10M7 12v3M17 12v3" />
    </>
  ),
  twin: (
    <>
      <path d="M5 7.5 12 3l7 4.5v9L12 21l-7-4.5v-9Z" />
      <path d="m5 7.5 7 4.5 7-4.5M12 12v9" />
    </>
  ),
  assets: (
    <>
      <rect x="3" y="4" width="7" height="7" rx="1" />
      <rect x="14" y="4" width="7" height="7" rx="1" />
      <rect x="8.5" y="15" width="7" height="6" rx="1" />
      <path d="M6.5 11v2h11v-2M12 13v2" />
    </>
  ),
  replay: (
    <>
      <path d="M5 8V4l-3 3 3 3V8a8 8 0 1 1-1 8" />
      <path d="M10 9v6l5-3-5-3Z" />
    </>
  ),
  playbooks: (
    <>
      <path d="M5 3h11a3 3 0 0 1 3 3v15H8a3 3 0 0 1-3-3V3Z" />
      <path d="M8 21V7a3 3 0 0 0-3-3M10 9h5M10 13h5" />
    </>
  ),
  reports: (
    <>
      <path d="M5 3h10l4 4v14H5V3Z" />
      <path d="M15 3v5h4M9 17v-4M12 17V9M15 17v-6" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.08A1.7 1.7 0 0 0 9 19.37a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.63 15 1.7 1.7 0 0 0 3.08 14H3v-4h.08A1.7 1.7 0 0 0 4.63 9a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.63 1.7 1.7 0 0 0 10 3.08V3h4v.08A1.7 1.7 0 0 0 15 4.63a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.37 9 1.7 1.7 0 0 0 20.92 10H21v4h-.08A1.7 1.7 0 0 0 19.4 15Z" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3 4.5 6v5.5c0 4.3 3.1 7.6 7.5 9.5 4.4-1.9 7.5-5.2 7.5-9.5V6L12 3Z" />
      <path d="m9 12 2 2 4-5" />
    </>
  ),
  activity: <path d="M3 12h4l2.2-6 4.2 12 2.1-6H21" />,
  database: (
    <>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
    </>
  ),
  link: (
    <>
      <path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.1 1.1" />
      <path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.1-1.1" />
    </>
  ),
  evidence: (
    <>
      <path d="M6 3h9l4 4v14H6V3Z" />
      <path d="M15 3v5h4M9 12h7M9 16h5" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
};

export function Icon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      aria-hidden="true"
      className={`icon icon--${name}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
