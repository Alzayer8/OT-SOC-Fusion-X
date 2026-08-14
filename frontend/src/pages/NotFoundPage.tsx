import { Link } from "react-router-dom";

import { ErrorState } from "../components/ErrorState";

export function NotFoundPage() {
  return (
    <div className="page-stack">
      <ErrorState
        title="Page not found"
        description="The requested foundation route does not exist. No application data was changed."
      />
      <Link className="button button--link" to="/">
        Return to Overview
      </Link>
    </div>
  );
}
