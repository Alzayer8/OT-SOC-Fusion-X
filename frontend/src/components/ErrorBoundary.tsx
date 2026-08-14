import { Component, type ReactNode } from "react";

import { ErrorState } from "./ErrorState";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(): void {
    // Phase 1 deliberately avoids external telemetry. The safe fallback is rendered locally.
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="standalone-state" id="main-content">
          <ErrorState />
        </main>
      );
    }
    return this.props.children;
  }
}
