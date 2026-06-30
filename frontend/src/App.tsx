import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AlertBanner } from "./components/AlertBanner";
import { AppDataProvider, useAppData } from "./app/AppDataContext";
import { AppShell } from "./app/AppShell";
import { ThemeProvider } from "./app/ThemeContext";
import { AdminLayout } from "./features/admin/AdminLayout";
import { AdminOverviewPage } from "./features/admin/pages/AdminOverviewPage";
import { AdminBlueprintPage } from "./features/admin/pages/AdminBlueprintPages";
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
          <Route path="knowledge-bases" element={<AdminBlueprintPage page="knowledge-bases" />} />
          <Route path="documents" element={<AdminBlueprintPage page="documents" />} />
          <Route path="documents/detail" element={<AdminBlueprintPage page="document-detail" />} />
          <Route path="documents/:documentId" element={<AdminBlueprintPage page="document-detail" />} />
          <Route path="pipeline" element={<AdminBlueprintPage page="pipeline" />} />
          <Route path="chunks" element={<AdminBlueprintPage page="chunks" />} />
          <Route path="vector-indexes" element={<AdminBlueprintPage page="vector-indexes" />} />
          <Route path="retrieval-profiles" element={<AdminBlueprintPage page="retrieval-profiles" />} />
          <Route path="playground" element={<AdminBlueprintPage page="playground" />} />
          <Route path="models-prompts" element={<AdminBlueprintPage page="models-prompts" />} />
          <Route path="traces" element={<AdminBlueprintPage page="traces" />} />
          <Route path="evaluations" element={<AdminBlueprintPage page="evaluations" />} />
          <Route path="feedback" element={<AdminBlueprintPage page="feedback" />} />
          <Route path="firewall" element={<AdminBlueprintPage page="firewall" />} />
          <Route path="connectors" element={<AdminBlueprintPage page="connectors" />} />
          <Route path="usage-cost" element={<AdminBlueprintPage page="usage-cost" />} />
          <Route path="jobs-workers" element={<AdminBlueprintPage page="jobs-workers" />} />
          <Route path="audit-access" element={<AdminBlueprintPage page="audit-access" />} />
          <Route path="settings" element={<AdminBlueprintPage page="settings" />} />
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
          <Route path="ops" element={<Navigate to="/admin/jobs-workers" replace />} />
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
