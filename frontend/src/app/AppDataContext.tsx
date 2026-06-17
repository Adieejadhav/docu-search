import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { messageFromError } from "../lib/format";
import { getDocuments, getHealth } from "../services/api";
import type { DocumentListResponse, HealthResponse } from "../services/types";

type LoadingKey = "boot" | "refresh";

interface AppDataContextValue {
  health: HealthResponse | null;
  documents: DocumentListResponse | null;
  error: string | null;
  isRefreshing: boolean;
  setError: (message: string | null) => void;
  refreshOverview: (key?: LoadingKey) => Promise<void>;
}

const AppDataContext = createContext<AppDataContextValue | null>(null);

export function AppDataProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [documents, setDocuments] = useState<DocumentListResponse | null>(null);
  const [loading, setLoading] = useState<Set<LoadingKey>>(new Set(["boot"]));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshOverview("boot");
  }, []);

  async function refreshOverview(key: LoadingKey = "refresh") {
    setLoadingKey(key, true);
    setError(null);
    try {
      const [healthPayload, documentsPayload] = await Promise.all([
        getHealth(),
        getDocuments(),
      ]);
      setHealth(healthPayload);
      setDocuments(documentsPayload);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setLoadingKey(key, false);
    }
  }

  function setLoadingKey(key: LoadingKey, value: boolean) {
    setLoading((current) => {
      const next = new Set(current);
      if (value) next.add(key);
      else next.delete(key);
      return next;
    });
  }

  const value = useMemo<AppDataContextValue>(
    () => ({
      health,
      documents,
      error,
      isRefreshing: loading.has("boot") || loading.has("refresh"),
      setError,
      refreshOverview,
    }),
    [documents, error, health, loading],
  );

  return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

export function useAppData() {
  const value = useContext(AppDataContext);
  if (!value) {
    throw new Error("useAppData must be used inside AppDataProvider");
  }
  return value;
}
