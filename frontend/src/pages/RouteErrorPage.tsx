import { isRouteErrorResponse, useRouteError } from "react-router-dom";

import { ErrorState } from "../components/ErrorState";

export function RouteErrorPage() {
  const error = useRouteError();
  const description = isRouteErrorResponse(error)
    ? `The route returned status ${error.status}. No operational action was taken.`
    : "The route returned a safe error. No operational action was taken.";

  return (
    <main className="standalone-state" id="main-content">
      <ErrorState title="Route unavailable" description={description} />
    </main>
  );
}
