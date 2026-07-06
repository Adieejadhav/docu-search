import { Bot, Search, SlidersHorizontal } from "lucide-react";
import { MarkdownAnswer } from "../../../components/MarkdownAnswer";
import { ResultItem } from "../../../components/ResultItem";
import { Button } from "../../../components/ui/Button";
import { EmptyState } from "../../../components/ui/EmptyState";
import { Skeleton } from "../../../components/ui/Skeleton";
import { useAdminWorkbench } from "../AdminWorkbenchContext";
import { BlueprintPage, BlueprintPanel } from "../AdminBlueprintPrimitives";
import { PerfMetric, StatusRow } from "../AdminPrimitives";

export function AdminPlaygroundPage() {
  const {
    askResult,
    fileName,
    fileType,
    isLoading,
    query,
    runAsk,
    runSearch,
    searchResult,
    setFileName,
    setFileType,
    setQuery,
    setTopK,
    timings,
    topK,
  } = useAdminWorkbench();

  const isSearching = isLoading("search");
  const isAsking = isLoading("ask");
  const results = searchResult?.results ?? [];

  return (
    <BlueprintPage>
      <section className="playground">
        <BlueprintPanel
          description="Run live retrieval and answer generation against the current index"
          title="Search & Answer"
        >
        <div className="query-form">
          <label>
            <span>Query</span>
            <textarea
              onChange={(event) => setQuery(event.target.value)}
              value={query}
            />
          </label>
          <div className="form-row">
            <label>
              <span>Top K</span>
              <input
                min={1}
                max={50}
                onChange={(event) => setTopK(Number(event.target.value))}
                type="number"
                value={topK}
              />
            </label>
            <label>
              <span>File type</span>
              <input
                onChange={(event) => setFileType(event.target.value)}
                placeholder="pdf"
                value={fileType}
              />
            </label>
            <label>
              <span>File name</span>
              <input
                onChange={(event) => setFileName(event.target.value)}
                placeholder="optional filter"
                value={fileName}
              />
            </label>
          </div>
          <div className="button-row">
            <Button
              disabled={!query.trim() || isSearching || isAsking}
              icon={<Search size={16} />}
              onClick={() => void runSearch()}
              variant="primary"
            >
              {isSearching ? "Searching" : "Run Search"}
            </Button>
            <Button
              disabled={!query.trim() || isAsking || isSearching}
              icon={<Bot size={16} />}
              onClick={() => void runAsk()}
            >
              {isAsking ? "Answering" : "Ask"}
            </Button>
          </div>
        </div>
        </BlueprintPanel>

      <div className="admin-grid">
        <BlueprintPanel description="Browser-observed timings and backend metadata" title="Latest Request">
          <div className="perf-grid">
            <PerfMetric label="Search" value={timings.search} />
            <PerfMetric label="Answer" value={timings.ask} />
          </div>
          <div className="status-list">
            <StatusRow label="Results" value={String(results.length)} />
            <StatusRow label="Embedding model" value={searchResult?.embedding_model ?? "-"} />
            <StatusRow label="Trace id" value={askResult?.trace_id ?? "-"} />
          </div>
        </BlueprintPanel>

        <BlueprintPanel title={askResult ? askResult.llm_model : "No Answer Yet"}>
          {isAsking && <Skeleton count={4} />}
          {!isAsking && askResult && <MarkdownAnswer text={askResult.answer} />}
          {!isAsking && !askResult && (
            <EmptyState icon={<Bot size={22} />}>Ask a query to generate an answer with citations.</EmptyState>
          )}
        </BlueprintPanel>

        <BlueprintPanel
          className="wide-panel"
          description="Ranked chunks returned by the retrieval pipeline"
          title={searchResult ? `${results.length} Result(s)` : "No Search Yet"}
        >
          {(isSearching || isAsking) && <Skeleton count={5} />}
          {!isSearching && !isAsking && results.length > 0 && (
            <div className="results-list">
              {results.map((result) => (
                <ResultItem key={result.child_chunk_id} result={result} />
              ))}
            </div>
          )}
          {!isSearching && !isAsking && results.length === 0 && (
            <EmptyState icon={<Search size={22} />}>Run search or ask to inspect retrieved chunks.</EmptyState>
          )}
        </BlueprintPanel>
      </div>
    </section>
    </BlueprintPage>
  );
}
