export const navigationItems = [
  { to: "/", label: "Overview", icon: "overview", end: true },
  { to: "/incidents", label: "Incidents", icon: "incidents" },
  { to: "/protocol-analysis", label: "Protocol Analysis", icon: "protocol" },
  { to: "/digital-twin", label: "Digital Twin", icon: "twin" },
  { to: "/assets", label: "Asset Inventory", icon: "assets" },
  { to: "/replay", label: "Replay", icon: "replay" },
  { to: "/playbooks", label: "Playbooks", icon: "playbooks" },
  { to: "/reports", label: "Reports", icon: "reports" },
  { to: "/settings", label: "Settings", icon: "settings" },
] as const;
