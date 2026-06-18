import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, ClipboardCheck, Play, RefreshCw, XCircle } from "lucide-react";
import { MetricCard } from "../../../components/MetricCard";
import { Button } from "../../../components/ui/Button";
import { EmptyState } from "../../../components/ui/EmptyState";
import { Panel } from "../../../components/ui/Panel";
import { Skeleton } from "../../../components/ui/Skeleton";
import { formatDateTime, messageFromError, scorePercent } from "../../../lib/format";
import { listEvaluationCases, listEvaluationRuns, runEvaluation } from "../../../services/api";
import type {
  EvaluationCase,
  EvaluationCaseResult,
  EvaluationRunRecordSummary,
  EvaluationRunResponse,
} from "../../../services/types";

export function AdminEvaluationPage() {
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [result, setResult] = useState<EvaluationRunResponse | null>(null);
  const [history, setHistory] = useState<EvaluationRunRecordSummary[]>([]);
  const [topK, setTopK] = useState(5);
  const [includeAnswers, setIncludeAnswers] = useState(true);
  const [isLoadingCases, setLoadingCases] = useState(true);
  const [isRunning, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedCount = selectedCaseIds.length || cases.length;
  const selectedSet = useMemo(() => new Set(selectedCaseIds), [selectedCaseIds]);

  useEffect(() => {
    void refreshCases();
    void refreshHistory();
  }, []);

  async function refreshCases() {
    setLoadingCases(true);
    setError(null);
    try {
      const payload = await listEvaluationCases();
      setCases(payload);
      setSelectedCaseIds(payload.map((item) => item.id));
    } catch (caughtError) {
      setError(messageFromError(caughtError));
    } finally {
      setLoadingCases(false);
    }
  }

  async function startEvaluation() {
    setRunning(true);
    setError(null);
    try {
      const payload = await runEvaluation({
        top_k: topK,
        include_answers: includeAnswers,
        case_ids: selectedCaseIds.length ? selectedCaseIds : undefined,
      });
      setResult(payload);
      await refreshHistory();
    } catch (caughtError) {
      setError(messageFromError(caughtError));
    } finally {
      setRunning(false);
    }
  }

  async function refreshHistory() {
    try {
      const payload = await listEvaluationRuns();
      setHistory(payload.runs);
    } catch {
      // History is secondary to running the active evaluation suite.
    }
  }

  function toggleCase(caseId: string) {
    setSelectedCaseIds((current) =>
      current.includes(caseId)
        ? current.filter((item) => item !== caseId)
        : [...current, caseId],
    );
  }

  return (
    <section className="evaluation-layout">
      <Panel className="evaluation-control-panel" eyebrow="Evaluation Suite" icon={<ClipboardCheck size={20} />} title="Quality Checks">
        <div className="evaluation-controls">
          <label>
            <span>Top K</span>
            <input
              min={1}
              max={20}
              onChange={(event) => setTopK(Number(event.target.value))}
              type="number"
              value={topK}
            />
          </label>
          <label className="toggle-row">
            <input
              checked={includeAnswers}
              onChange={(event) => setIncludeAnswers(event.target.checked)}
              type="checkbox"
            />
            <span>Generate and score answers</span>
          </label>
          <div className="button-row">
            <Button
              disabled={isRunning || !selectedCount}
              icon={<Play size={16} />}
              onClick={() => void startEvaluation()}
              variant="primary"
            >
              {isRunning ? "Running" : `Run ${selectedCount} case(s)`}
            </Button>
            <Button
              disabled={isLoadingCases || isRunning}
              icon={<RefreshCw size={16} />}
              onClick={() => void refreshCases()}
            >
              Refresh
            </Button>
          </div>
          {error && <div className="selection-error">{error}</div>}
        </div>
      </Panel>

      <Panel className="evaluation-cases-panel" eyebrow="Dataset" title={`${cases.length} Built-In Cases`}>
        {isLoadingCases ? (
          <Skeleton count={5} />
        ) : cases.length ? (
          <div className="evaluation-case-list">
            {cases.map((item) => (
              <label className="evaluation-case-row" key={item.id}>
                <input
                  checked={selectedSet.has(item.id)}
                  onChange={() => toggleCase(item.id)}
                  type="checkbox"
                />
                <span>
                  <strong>{item.question}</strong>
                  <small>{item.tags.join(" / ")}</small>
                </span>
              </label>
            ))}
          </div>
        ) : (
          <EmptyState>No evaluation cases configured.</EmptyState>
        )}
      </Panel>

      <Panel className="evaluation-history-panel" eyebrow="History" title="Recent Runs">
        {history.length ? (
          <div className="evaluation-history-list">
            {history.slice(0, 8).map((run) => (
              <article className="evaluation-history-row" key={run.id}>
                <strong>
                  {run.passed_cases}/{run.total_cases} passed
                </strong>
                <span>
                  {formatDateTime(run.created_at)} · source {scorePercent(run.source_hit_rate)}
                  {run.answer_term_pass_rate !== null
                    ? ` · answer ${scorePercent(run.answer_term_pass_rate)}`
                    : ""}
                </span>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState>No saved evaluation runs yet.</EmptyState>
        )}
      </Panel>

      {result && (
        <section className="evaluation-summary-grid">
          <MetricCard
            icon={<ClipboardCheck size={20} />}
            label="Passed"
            value={`${result.summary.passed_cases}/${result.summary.total_cases}`}
            tone={result.summary.failed_cases ? "degraded" : "ok"}
          />
          <MetricCard
            icon={<CheckCircle2 size={20} />}
            label="Source Hit Rate"
            value={scorePercent(result.summary.source_hit_rate)}
          />
          <MetricCard
            icon={<CheckCircle2 size={20} />}
            label="Answer Terms"
            value={
              result.summary.answer_term_pass_rate === null
                ? "-"
                : scorePercent(result.summary.answer_term_pass_rate)
            }
          />
          <MetricCard
            icon={<RefreshCw size={20} />}
            label="Mean Runtime"
            value={`${result.summary.mean_total_ms.toFixed(1)}ms`}
            detail={`retrieval ${result.summary.mean_retrieval_ms.toFixed(1)}ms`}
          />
        </section>
      )}

      <Panel className="evaluation-results-panel" eyebrow="Results" title={result ? `${result.results.length} Case Results` : "No Run Yet"}>
        {isRunning && <Skeleton count={6} />}
        {!isRunning && result && (
          <div className="evaluation-results-list">
            {result.results.map((item) => (
              <EvaluationResultCard key={item.case_id} result={item} />
            ))}
          </div>
        )}
        {!isRunning && !result && (
          <EmptyState icon={<ClipboardCheck size={22} />}>Run the suite to inspect retrieval and answer quality.</EmptyState>
        )}
      </Panel>
    </section>
  );
}

function EvaluationResultCard({ result }: { result: EvaluationCaseResult }) {
  const passed = result.status === "passed";

  return (
    <article className={passed ? "evaluation-result-card passed" : "evaluation-result-card failed"}>
      <header>
        <div>
          <strong>{result.question}</strong>
          <small>
            retrieval {result.retrieval_ms.toFixed(1)}ms
            {result.answer_ms !== null ? ` / answer ${result.answer_ms.toFixed(1)}ms` : ""}
          </small>
        </div>
        <span className={passed ? "status-pill completed" : "status-pill failed"}>
          {passed ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
          {result.status}
        </span>
      </header>

      <div className="evaluation-checks">
        <CheckBadge label="retrieval" passed={result.retrieval_passed} />
        <CheckBadge label="answer" passed={result.answer_passed} />
        <span>source rank: <strong>{result.source_rank ?? "-"}</strong></span>
      </div>

      {!!result.answer && (
        <p className="evaluation-answer">{result.answer}</p>
      )}

      <MissingTerms label="Missing context terms" terms={result.missing_context_terms} />
      <MissingTerms label="Missing answer terms" terms={result.missing_answer_terms} />

      <div className="evaluation-context-list">
        {result.contexts.slice(0, 3).map((context) => (
          <div className="evaluation-context-row" key={`${result.case_id}-${context.rank}`}>
            <strong>
              [{context.rank}] {context.file_name ?? "unknown"} · {scorePercent(context.score)}
            </strong>
            <small>{context.parent_path.join(" > ") || context.source_refs.join(", ")}</small>
            <p>{context.text_excerpt}</p>
          </div>
        ))}
      </div>
    </article>
  );
}

function CheckBadge({ label, passed }: { label: string; passed: boolean | null }) {
  return (
    <span className={passed === false ? "check-badge failed" : "check-badge passed"}>
      {label}: <strong>{passed === null ? "-" : passed ? "pass" : "fail"}</strong>
    </span>
  );
}

function MissingTerms({ label, terms }: { label: string; terms: string[] }) {
  if (!terms.length) return null;

  return (
    <div className="missing-terms">
      <span>{label}</span>
      <div>
        {terms.map((term) => (
          <strong key={term}>{term}</strong>
        ))}
      </div>
    </div>
  );
}
