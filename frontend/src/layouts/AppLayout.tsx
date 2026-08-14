import { Suspense } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { LoadingState } from "../components/LoadingState";
import { Icon, type IconName } from "../components/Icons";
import { navigationItems } from "../routes/navigation";
import { TopHeader } from "./TopHeader";

export function AppLayout() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside className="side-rail">
        <div className="brand" aria-label="OT-SOC Fusion X">
          <span className="brand__mark" aria-hidden="true">
            <Icon name="shield" />
          </span>
          <span className="brand__text">
            <strong>OT-SOC</strong>
            <span>Fusion X</span>
          </span>
        </div>
        <nav className="primary-nav" aria-label="Primary navigation">
          {navigationItems.map((item) => (
            <NavLink
              className={({ isActive }) => `nav-link${isActive ? " nav-link--active" : ""}`}
              end={"end" in item ? item.end : false}
              key={item.to}
              to={item.to}
            >
              <span className="nav-link__marker" aria-hidden="true">
                <Icon name={item.icon as IconName} />
              </span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side-rail__notice">
          <span className="side-rail__notice-icon" aria-hidden="true">
            <Icon name="database" />
          </span>
          <div>
            <strong>Synthetic lab</strong>
            <span>Offline stored evidence</span>
            <span>No live OT connections or control</span>
          </div>
        </div>
      </aside>
      <div className="app-shell__workspace">
        <TopHeader />
        <main className="main-content" id="main-content" tabIndex={-1}>
          <Suspense fallback={<LoadingState />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
