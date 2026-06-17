import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AlertBanner } from "./components/AlertBanner";
import { AppDataProvider, useAppData } from "./app/AppDataContext";
import { AppShell } from "./app/AppShell";
import { AdminLayout } from "./features/admin/AdminLayout";
import { AdminIndexPage } from "./features/admin/pages/AdminIndexPage";
import { AdminOpsPage } from "./features/admin/pages/AdminOpsPage";
import { AdminOverviewPage } from "./features/admin/pages/AdminOverviewPage";
import { AdminTestBenchPage } from "./features/admin/pages/AdminTestBenchPage";
import { AdminWorkbenchProvider } from "./features/admin/AdminWorkbenchContext";
import { ChatPanel } from "./features/chat/ChatPanel";

export default function App() {
  return (
    <BrowserRouter>
      <AppDataProvider>
        <AppRoutes />
      </AppDataProvider>
    </BrowserRouter>
  );
}

function AppRoutes() {
  const { error, isRefreshing, refreshOverview, setError } = useAppData();

  return (
    <AppShell
      onRefresh={() => void refreshOverview()}
      refreshDisabled={isRefreshing}
    >
      {error && <AlertBanner message={error} />}
      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPanel onError={setError} />} />
        <Route
          path="/admin"
          element={
            <AdminWorkbenchProvider>
              <AdminLayout />
            </AdminWorkbenchProvider>
          }
        >
          <Route index element={<Navigate to="/admin/overview" replace />} />
          <Route path="overview" element={<AdminOverviewPage />} />
          <Route path="test-bench" element={<AdminTestBenchPage />} />
          <Route path="index" element={<AdminIndexPage />} />
          <Route path="ops" element={<AdminOpsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </AppShell>
  );
}
