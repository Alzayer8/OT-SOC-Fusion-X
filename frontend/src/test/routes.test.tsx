import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { navigationItems } from "../routes/navigation";
import { renderRouterAt } from "./renderRouter";

const requiredRoutes = [
  ["/", "Overview"],
  ["/incidents", "Incidents"],
  ["/protocol-analysis", "Protocol Analysis"],
  ["/digital-twin", "Digital Twin"],
  ["/assets", "Asset Inventory"],
  ["/replay", "Replay"],
  ["/playbooks", "Playbooks"],
  ["/reports", "Reports"],
  ["/settings", "Settings"],
] as const;

describe("application routes", () => {
  it.each(requiredRoutes)("renders %s with the %s heading", async (path, heading) => {
    renderRouterAt(path);

    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument();
  });

  it("marks the active navigation item without relying on color", async () => {
    renderRouterAt("/replay");

    await screen.findByRole("heading", { level: 1, name: "Replay" });
    expect(screen.getByRole("link", { name: "Replay" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("keeps exactly the frozen nine navigation items in order", async () => {
    renderRouterAt("/");

    await screen.findByRole("heading", { level: 1, name: "Overview" });
    const links = screen
      .getByRole("navigation", { name: "Primary navigation" })
      .querySelectorAll("a");
    expect(links).toHaveLength(9);
    navigationItems.forEach((item, index) => {
      expect(links[index]).toHaveAccessibleName(item.label);
    });
  });

  it("supports keyboard navigation through the shared shell", async () => {
    const user = userEvent.setup();
    renderRouterAt("/");

    await screen.findByRole("heading", { level: 1, name: "Overview" });
    await user.tab();
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "Overview" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "Incidents" })).toHaveFocus();
  });

  it("navigates using each shared navigation link", async () => {
    const user = userEvent.setup();
    const { router } = renderRouterAt("/");

    await screen.findByRole("heading", { level: 1, name: "Overview" });
    for (const item of navigationItems.slice(1)) {
      await user.click(screen.getByRole("link", { name: item.label }));
      await waitFor(() => expect(router.state.location.pathname).toBe(item.to));
    }
  });

  it("renders the controlled not-found page", async () => {
    renderRouterAt("/unknown-foundation-route");

    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Return to Overview" })).toBeInTheDocument();
  });

  it("contains no fake operational dashboard content", async () => {
    const { container } = renderRouterAt("/");
    await screen.findByRole("heading", { level: 1, name: "Overview" });
    const text = container.textContent ?? "";

    expect(text).not.toMatch(/critical incidents|CVE-|compliance posture|all systems operational/i);
    expect(text).not.toMatch(/Arjun|Mehta|192\.168\.50/i);
    expect(text).toMatch(/synthetic Oil & Gas transfer/i);
    expect(text).not.toMatch(/cooling|nuclear/i);
  });
});
