import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { getLiveness } from "../api/client";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { LoadingState } from "../components/LoadingState";

function ThrowingComponent(): never {
  throw new Error("test-only failure");
}

describe("foundation components", () => {
  it("renders an accessible loading boundary", () => {
    render(<LoadingState label="Loading route" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading route");
  });

  it("renders a safe error-boundary fallback", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("This view could not be displayed");
    expect(screen.getByText(/No operational action was taken/i)).toBeInTheDocument();
  });

  it("uses the generated API contract for liveness", async () => {
    const result = await getLiveness();

    await waitFor(() => expect(result.status).toBe("ok"));
    expect(result.service).toBe("OT-SOC Fusion X");
  });
});
