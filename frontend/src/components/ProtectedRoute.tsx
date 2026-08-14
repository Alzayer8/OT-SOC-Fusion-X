import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { LoadingState } from "./LoadingState";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const location = useLocation();

  if (auth.status === "checking") return <LoadingState />;
  if (auth.status !== "authenticated") {
    return (
      <Navigate replace state={{ from: `${location.pathname}${location.search}` }} to="/login" />
    );
  }
  return children;
}
