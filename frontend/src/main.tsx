import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { Layout } from "./Layout";
import { AirlineSettingsPage, ReturnFlightsPage } from "./pages/Admin";
import { DashboardPage } from "./pages/Dashboard";
import { StagePage } from "./pages/Stage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 15_000, retry: 1, refetchOnWindowFocus: true } },
});

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <DashboardPage /> },
      { path: "/flights/:airline/:fltNbr/:actdate/:status", element: <StagePage /> },
      { path: "/admin/return-flights", element: <ReturnFlightsPage /> },
      { path: "/admin/airline-settings", element: <AirlineSettingsPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
