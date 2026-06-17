import { FormEvent, useEffect, useMemo, useState } from "react";
import { Bot, FileSearch, Send, User } from "lucide-react";
import { MarkdownAnswer } from "../../components/MarkdownAnswer";
import { Badge } from "../../components/ui/Badge";
import { Skeleton } from "../../components/ui/Skeleton";
import { askDocuments } from "../../services/api";
import { elapsedMs, messageFromError, scorePercent } from "../../lib/format";
import type { ChatMessage } from "./types";

const DEFAULT_QUESTION = "Which policy mentions the 14-day satellite-mode exception?";
const SUGGESTIONS = [
  "Which team owns model-assisted triage?",
  "What evidence is required for policy verification?",
  "How long are hourly aggregated metrics retained?",
];

export function ChatPanel({ onError }: { onError: (message: string | null) => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState(DEFAULT_QUESTION);
  const [isAsking, setIsAsking] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);

  const hasConversation = messages.length > 0;
  const latestAssistant = useMemo(
    () => [...messages].reverse().find((message) => message.sources?.length),
    [messages],
  );
  const latestSources = latestAssistant?.sources ?? [];
  const selectedSource =
    latestSources.find((source) => source.child_chunk_id === selectedSourceId) ??
    latestSources[0];

  useEffect(() => {
    if (!latestSources.length) {
      setSelectedSourceId(null);
      return;
    }
    setSelectedSourceId((current) =>
      latestSources.some((source) => source.child_chunk_id === current)
        ? current
        : latestSources[0].child_chunk_id,
    );
  }, [latestSources]);

  async function submitQuestion(event: FormEvent) {
    event.preventDefault();
    const question = draft.trim();
    if (!question || isAsking) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
    };
    setMessages((current) => [...current, userMessage]);
    setDraft("");
    setIsAsking(true);
    onError(null);

    const start = performance.now();
    try {
      const answer = await askDocuments({ query: question, top_k: 5 });
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: answer.answer,
        sources: answer.retrieval.results,
        latencyMs: elapsedMs(start),
        model: answer.llm_model,
      };
      setMessages((current) => [...current, assistantMessage]);
    } catch (error) {
      onError(messageFromError(error));
      setDraft(question);
    } finally {
      setIsAsking(false);
    }
  }

  return (
    <section className="chat-screen">
      <div className="chat-thread">
        {!hasConversation && (
          <section className="chat-welcome">
            <div className="welcome-icon">
              <FileSearch size={26} />
            </div>
            <h2>Ask your indexed documents</h2>
            <p>Answers are grounded in retrieved chunks and cite the source context.</p>
            <div className="suggestion-grid">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  type="button"
                  key={suggestion}
                  onClick={() => setDraft(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </section>
        )}

        <div className="message-list" aria-live="polite">
          {messages.map((message) => (
            <article className={`chat-message ${message.role}`} key={message.id}>
              <div className="message-avatar">
                {message.role === "user" ? <User size={17} /> : <Bot size={17} />}
              </div>
              <div className="message-body">
                {message.role === "assistant" ? (
                  <MarkdownAnswer text={message.content} />
                ) : (
                  <p>{message.content}</p>
                )}
                {message.role === "assistant" && (
                  <footer>
                    <span>{message.model}</span>
                    {message.latencyMs !== undefined && <span>{message.latencyMs}ms</span>}
                  </footer>
                )}
                {!!message.sources?.length && (
                  <div className="citation-strip">
                    {message.sources.map((source) => (
                      <button
                        className={
                          source.child_chunk_id === selectedSourceId ? "active" : ""
                        }
                        key={source.child_chunk_id}
                        onClick={() => setSelectedSourceId(source.child_chunk_id)}
                        type="button"
                      >
                        [{source.rank}] {source.file_name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </article>
          ))}
          {isAsking && (
            <article className="chat-message assistant loading">
              <div className="message-avatar">
                <Bot size={17} />
              </div>
              <div className="message-body">
                <Skeleton compact count={3} />
              </div>
            </article>
          )}
        </div>

        <form className="chat-composer" onSubmit={(event) => void submitQuestion(event)}>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            rows={2}
            placeholder="Ask a question about the indexed documents"
          />
          <button className="send-button" type="submit" disabled={!draft.trim() || isAsking}>
            <Send size={18} />
          </button>
        </form>
      </div>

      <aside className="chat-sources">
        <header>
          <p className="eyebrow">Sources</p>
          <h2>{latestSources.length ? `${latestSources.length} retrieved` : "No sources yet"}</h2>
        </header>
        {selectedSource && (
          <article className="source-detail">
            <header>
              <Badge tone="ok">[{selectedSource.rank}]</Badge>
              <strong>{selectedSource.file_name}</strong>
              <span>{scorePercent(selectedSource.score)}</span>
            </header>
            <p>{selectedSource.parent_path.join(" > ") || "root"}</p>
            <small>{selectedSource.source_refs.join(", ") || "no source ref"}</small>
          </article>
        )}
        <div className="source-list">
          {latestSources.map((source) => (
            <button
              className={
                source.child_chunk_id === selectedSource?.child_chunk_id
                  ? "source-row active"
                  : "source-row"
              }
              key={source.child_chunk_id}
              onClick={() => setSelectedSourceId(source.child_chunk_id)}
              type="button"
            >
              <span className="source-row-header">
                <strong>#{source.rank}</strong>
                <span>{source.file_name}</span>
              </span>
              <span className="source-row-text">{source.child_text}</span>
              <span className="source-row-footer">{source.source_refs.join(", ")}</span>
            </button>
          ))}
          {!latestSources.length && (
            <div className="source-empty">Ask a question to see retrieved context.</div>
          )}
        </div>
      </aside>
    </section>
  );
}
