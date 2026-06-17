import {
  createContext,
  type ReactNode,
  useContext,
  useMemo,
  useState,
} from "react";
import { useAppData } from "../../app/AppDataContext";
import { elapsedMs, messageFromError } from "../../lib/format";
import { askDocuments, clearIndex, searchDocuments } from "../../services/api";
import type { AskResponse, SearchResponse } from "../../services/types";

type LoadingAction = "search" | "ask" | "clear";

const EXAMPLE_QUERY = "Which policy mentions the 14-day satellite-mode exception?";

interface AdminWorkbenchContextValue {
  askResult: AskResponse | null;
  fileName: string;
  fileType: string;
  isLoading: (action: LoadingAction) => boolean;
  query: string;
  runAsk: () => Promise<void>;
  runClearIndex: () => Promise<void>;
  runSearch: () => Promise<void>;
  searchResult: SearchResponse | null;
  setFileName: (value: string) => void;
  setFileType: (value: string) => void;
  setQuery: (value: string) => void;
  setTopK: (value: number) => void;
  timings: Record<string, number>;
  topK: number;
}

const AdminWorkbenchContext = createContext<AdminWorkbenchContextValue | null>(null);

export function AdminWorkbenchProvider({ children }: { children: ReactNode }) {
  const { refreshOverview, setError } = useAppData();
  const [query, setQuery] = useState(EXAMPLE_QUERY);
  const [topK, setTopKState] = useState(5);
  const [fileName, setFileName] = useState("");
  const [fileType, setFileType] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [askResult, setAskResult] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState<Set<LoadingAction>>(new Set());
  const [timings, setTimings] = useState<Record<string, number>>({});

  async function runSearch() {
    setLoadingKey("search", true);
    setError(null);
    const start = performance.now();
    try {
      const result = await searchDocuments({
        query,
        top_k: topK,
        file_name: fileName || undefined,
        file_type: fileType || undefined,
      });
      setSearchResult(result);
      setTimings((current) => ({ ...current, search: elapsedMs(start) }));
    } catch (error) {
      setError(messageFromError(error));
    } finally {
      setLoadingKey("search", false);
    }
  }

  async function runAsk() {
    setLoadingKey("ask", true);
    setError(null);
    const start = performance.now();
    try {
      const result = await askDocuments({
        query,
        top_k: topK,
        file_name: fileName || undefined,
        file_type: fileType || undefined,
      });
      setAskResult(result);
      setSearchResult(result.retrieval);
      setTimings((current) => ({ ...current, ask: elapsedMs(start) }));
    } catch (error) {
      setError(messageFromError(error));
    } finally {
      setLoadingKey("ask", false);
    }
  }

  async function runClearIndex() {
    setLoadingKey("clear", true);
    setError(null);
    const start = performance.now();
    try {
      await clearIndex();
      setSearchResult(null);
      setAskResult(null);
      setTimings((current) => ({ ...current, clear: elapsedMs(start) }));
      await refreshOverview("refresh");
    } catch (error) {
      setError(messageFromError(error));
    } finally {
      setLoadingKey("clear", false);
    }
  }

  function setTopK(value: number) {
    setTopKState(Math.max(1, Math.min(50, value || 1)));
  }

  function setLoadingKey(key: LoadingAction, value: boolean) {
    setLoading((current) => {
      const next = new Set(current);
      if (value) next.add(key);
      else next.delete(key);
      return next;
    });
  }

  const value = useMemo<AdminWorkbenchContextValue>(
    () => ({
      askResult,
      fileName,
      fileType,
      isLoading: (action) => loading.has(action),
      query,
      runAsk,
      runClearIndex,
      runSearch,
      searchResult,
      setFileName,
      setFileType,
      setQuery,
      setTopK,
      timings,
      topK,
    }),
    [askResult, fileName, fileType, loading, query, searchResult, timings, topK],
  );

  return (
    <AdminWorkbenchContext.Provider value={value}>
      {children}
    </AdminWorkbenchContext.Provider>
  );
}

export function useAdminWorkbench() {
  const value = useContext(AdminWorkbenchContext);
  if (!value) {
    throw new Error("useAdminWorkbench must be used inside AdminWorkbenchProvider");
  }
  return value;
}
