import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AlertBanner } from "./components/AlertBanner";
import { AppDataProvider, useAppData } from "./app/AppDataContext";
import { AppShell } from "./app/AppShell";
import { ThemeProvider } from "./app/ThemeContext";
import { AdminLayout } from "./features/admin/AdminLayout";
import { AdminEvaluationPage } from "./features/admin/pages/AdminEvaluationPage";
import { AdminIndexPage } from "./features/admin/pages/AdminIndexPage";
import { AdminOverviewPage } from "./features/admin/pages/AdminOverviewPage";
import { AdminPipelinePage } from "./features/admin/pages/AdminPipelinePage";
import { AdminPlaygroundPage } from "./features/admin/pages/AdminPlaygroundPage";
import { AdminTracesPage } from "./features/admin/pages/AdminTracesPage";
import { AdminVectorIndexPage } from "./features/admin/pages/AdminVectorIndexPage";
import { AdminWorkbenchProvider } from "./features/admin/AdminWorkbenchContext";
import { ChatPanel } from "./features/chat/ChatPanel";

const AdminTestBenchPage = lazy(() =>
  import("./features/admin/pages/AdminTestBenchPage").then((module) => ({
    default: module.AdminTestBenchPage,
  })),
);

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AppDataProvider>
          <AppRoutes />
        </AppDataProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

function AppRoutes() {
  const { error, isRefreshing, refreshOverview, setError } = useAppData();
  const location = useLocation();
  const isChatRoute = location.pathname.startsWith("/chat");

  return (
    <AppShell
      onRefresh={() => void refreshOverview()}
      refreshDisabled={isRefreshing}
    >
      {error && !isChatRoute && <AlertBanner message={error} />}
      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPanel error={error} onError={setError} />} />
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
          <Route path="documents" element={<AdminIndexPage />} />
          <Route path="documents/detail" element={<Navigate to="/admin/documents" replace />} />
          <Route path="documents/:documentId" element={<Navigate to="/admin/documents" replace />} />
          <Route path="pipeline" element={<AdminPipelinePage />} />
          <Route path="vector-indexes" element={<AdminVectorIndexPage />} />
          <Route path="playground" element={<AdminPlaygroundPage />} />
          <Route path="traces" element={<AdminTracesPage />} />
          <Route path="evaluations" element={<AdminEvaluationPage />} />
          <Route
            path="test-bench"
            element={
              <Suspense fallback={<PipelineLabFallback />}>
                <AdminTestBenchPage />
              </Suspense>
            }
          />
          <Route path="evaluation" element={<Navigate to="/admin/evaluations" replace />} />
          <Route path="index" element={<Navigate to="/admin/vector-indexes" replace />} />
          <Route path="ingestion" element={<Navigate to="/admin/pipeline" replace />} />
          <Route path="ops" element={<Navigate to="/admin/pipeline" replace />} />
          <Route path="jobs-workers" element={<Navigate to="/admin/pipeline" replace />} />
          <Route path="*" element={<Navigate to="/admin/overview" replace />} />
        </Route>
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </AppShell>
  );
}

function PipelineLabFallback() {
  return (
    <div className="grid min-h-80 place-items-center rounded-lg border border-slate-200 bg-white text-sm text-slate-500 shadow-sm">
      Loading pipeline workspace...
    </div>
  );
}
