import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { router } from "./routes/router";
import "./styles/tokens.css";
import "./styles/global.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Application root is missing");
}

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ErrorBoundary>
  </StrictMode>,
);
