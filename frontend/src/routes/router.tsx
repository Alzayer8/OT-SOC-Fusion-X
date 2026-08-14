import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { ProtectedRoute } from "../components/ProtectedRoute";
import { LabProvider } from "../context/LabContext";
import { AppLayout } from "../layouts/AppLayout";
import { AssetInventoryPage } from "../pages/AssetInventoryPage";
import { DigitalTwinPage } from "../pages/DigitalTwinPage";
import { IncidentsPage } from "../pages/IncidentsPage";
import { LoginPage } from "../pages/LoginPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { OverviewPage } from "../pages/OverviewPage";
import { PlaybooksPage } from "../pages/PlaybooksPage";
import { ProtocolAnalysisPage } from "../pages/ProtocolAnalysisPage";
import { ReplayPage } from "../pages/ReplayPage";
import { ReportsPage } from "../pages/ReportsPage";
import { RouteErrorPage } from "../pages/RouteErrorPage";
import { SettingsPage } from "../pages/SettingsPage";

export const appRoutes: RouteObject[] = [
  {
    path: "/login",
    element: <LoginPage />,
    errorElement: <RouteErrorPage />,
  },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <LabProvider>
          <AppLayout />
        </LabProvider>
      </ProtectedRoute>
    ),
    errorElement: <RouteErrorPage />,
    children: [
      {
        index: true,
        element: <OverviewPage />,
      },
      {
        path: "incidents",
        element: <IncidentsPage />,
      },
      { path: "incidents/:incidentId", element: <IncidentsPage /> },
      {
        path: "protocol-analysis",
        element: <ProtocolAnalysisPage />,
      },
      {
        path: "digital-twin",
        element: <DigitalTwinPage />,
      },
      {
        path: "assets",
        element: <AssetInventoryPage />,
      },
      {
        path: "replay",
        element: <ReplayPage />,
      },
      {
        path: "playbooks",
        element: <PlaybooksPage />,
      },
      {
        path: "reports",
        element: <ReportsPage />,
      },
      {
        path: "settings",
        element: <SettingsPage />,
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(appRoutes);
