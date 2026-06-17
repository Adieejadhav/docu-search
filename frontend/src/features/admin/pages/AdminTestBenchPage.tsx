import { FormEvent } from "react";
import { Search, Send } from "lucide-react";
import { MarkdownAnswer } from "../../../components/MarkdownAnswer";
import { ResultItem } from "../../../components/ResultItem";
import { Button } from "../../../components/ui/Button";
import { EmptyState } from "../../../components/ui/EmptyState";
import { Panel } from "../../../components/ui/Panel";
import { Skeleton } from "../../../components/ui/Skeleton";
import { useAdminWorkbench } from "../AdminWorkbenchContext";

export function AdminTestBenchPage() {
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
    topK,
  } = useAdminWorkbench();

  async function submitSearch(event: FormEvent) {
    event.preventDefault();
    await runSearch();
  }

  return (
    <section className="test-bench">
      <Panel className="query-panel" eyebrow="RAG Test Bench" title="Retrieval & Answer Testing">
        <form onSubmit={(event) => void submitSearch(event)} className="query-form">
          <label>
            <span>Question</span>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              rows={3}
            />
          </label>
          <div className="form-row">
            <label>
              <span>Top K</span>
              <input
                type="number"
                min={1}
                max={50}
                value={topK}
                onChange={(event) => setTopK(Number(event.target.value))}
              />
            </label>
            <label>
              <span>File type</span>
              <input
                value={fileType}
                onChange={(event) => setFileType(event.target.value)}
                placeholder="md, pdf, json"
              />
            </label>
            <label>
              <span>File name</span>
              <input
                value={fileName}
                onChange={(event) => setFileName(event.target.value)}
                placeholder="optional exact match"
              />
            </label>
          </div>
          <div className="button-row">
            <Button
              disabled={!query.trim() || isLoading("search")}
              icon={<Search size={17} />}
              type="submit"
              variant="primary"
            >
              {isLoading("search") ? "Searching" : "Search"}
            </Button>
            <Button
              disabled={!query.trim() || isLoading("ask")}
              icon={<Send size={17} />}
              onClick={() => void runAsk()}
            >
              {isLoading("ask") ? "Asking" : "Ask"}
            </Button>
          </div>
        </form>
      </Panel>

      {askResult && (
        <Panel className="answer-panel" eyebrow="Generated Answer" title={askResult.llm_model}>
          <MarkdownAnswer text={askResult.answer} />
        </Panel>
      )}

      <Panel
        eyebrow="Retrieval Results"
        title={searchResult ? `${searchResult.results.length} matches` : "No query run"}
      >
        {searchResult && <p className="panel-caption">{searchResult.embedding_model}</p>}
        <div className="results-list">
          {(isLoading("search") || isLoading("ask")) && <Skeleton count={3} />}
          {!isLoading("search") &&
            !isLoading("ask") &&
            (searchResult?.results ?? []).map((result) => (
              <ResultItem key={result.child_chunk_id} result={result} />
            ))}
          {!searchResult && !isLoading("search") && !isLoading("ask") && (
            <EmptyState icon={<Search size={24} />}>Run a search or ask test.</EmptyState>
          )}
        </div>
      </Panel>
    </section>
  );
}
