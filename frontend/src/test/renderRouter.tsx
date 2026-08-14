import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { AuthProvider } from "../auth/AuthContext";
import { appRoutes } from "../routes/router";

export function renderRouterAt(path: string) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  return {
    router,
    ...render(
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>,
    ),
  };
}
