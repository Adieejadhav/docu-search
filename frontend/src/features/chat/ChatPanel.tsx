import { FormEvent, useEffect, useMemo, useState } from "react";
import { Bot, FileSearch, MessageSquarePlus, Send, User } from "lucide-react";
import { MarkdownAnswer } from "../../components/MarkdownAnswer";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Skeleton } from "../../components/ui/Skeleton";
import { askChatStream, getChatSession, listChatSessions } from "../../services/api";
import { formatDateTime, messageFromError, scorePercent } from "../../lib/format";
import type { ChatMessage } from "./types";
import type { ChatMessageResponse, ChatSessionSummary } from "../../services/types";

const DEFAULT_QUESTION = "Which policy mentions the 14-day satellite-mode exception?";
const SUGGESTIONS = [
  "Which team owns model-assisted triage?",
  "What evidence is required for policy verification?",
  "How long are hourly aggregated metrics retained?",
];

export function ChatPanel({ onError }: { onError: (message: string | null) => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState(DEFAULT_QUESTION);
  const [isLoadingSessions, setLoadingSessions] = useState(false);
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
    void refreshSessions();
  }, []);

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

  async function refreshSessions(autoSelect = true) {
    setLoadingSessions(true);
    try {
      const payload = await listChatSessions();
      setSessions(payload.sessions);
      if (autoSelect && !activeSessionId && payload.sessions.length && !messages.length) {
        await loadSession(payload.sessions[0].id);
      }
    } catch (error) {
      onError(messageFromError(error));
    } finally {
      setLoadingSessions(false);
    }
  }

  async function loadSession(sessionId: string) {
    setActiveSessionId(sessionId);
    onError(null);
    try {
      const session = await getChatSession(sessionId);
      setMessages(session.messages.map(chatMessageFromResponse));
    } catch (error) {
      onError(messageFromError(error));
    }
  }

  function startNewChat() {
    setActiveSessionId(null);
    setMessages([]);
    setDraft(DEFAULT_QUESTION);
    setSelectedSourceId(null);
  }

  async function submitQuestion(event: FormEvent) {
    event.preventDefault();
    const question = draft.trim();
    if (!question || isAsking) return;

    setDraft("");
    setIsAsking(true);
    onError(null);

    try {
      const streamAssistantId = crypto.randomUUID();
      await askChatStream(
        {
          query: question,
          top_k: 5,
          ...(activeSessionId ? { session_id: activeSessionId } : {}),
        },
        {
          onSession: (payload) => {
            setActiveSessionId(payload.session.id);
            setMessages((current) => [
              ...current,
              chatMessageFromResponse(payload.user_message),
              {
                id: streamAssistantId,
                role: "assistant",
                content: "",
                sources: [],
                model: "streaming",
              },
            ]);
          },
          onRetrieval: (payload) => {
            setMessages((current) =>
              current.map((message) =>
                message.id === streamAssistantId
                  ? { ...message, sources: payload.results }
                  : message,
              ),
            );
          },
          onDelta: (text) => {
            setMessages((current) =>
              current.map((message) =>
                message.id === streamAssistantId
                  ? { ...message, content: `${message.content}${text}` }
                  : message,
              ),
            );
          },
          onComplete: (payload) => {
            setActiveSessionId(payload.session.id);
            setMessages((current) =>
              current.map((message) =>
                message.id === streamAssistantId
                  ? chatMessageFromResponse(payload.assistant_message)
                  : message,
              ),
            );
          },
          onError: (streamError) => {
            throw streamError;
          },
        },
      );
      await refreshSessions(false);
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
        <section className="chat-history-panel">
          <header>
            <p className="eyebrow">Conversations</p>
            <Button icon={<MessageSquarePlus size={16} />} onClick={startNewChat} size="small">
              New
            </Button>
          </header>
          <div className="chat-session-list">
            {isLoadingSessions && <Skeleton compact count={2} />}
            {!isLoadingSessions &&
              sessions.map((session) => (
                <button
                  className={
                    session.id === activeSessionId ? "chat-session active" : "chat-session"
                  }
                  key={session.id}
                  onClick={() => void loadSession(session.id)}
                  type="button"
                >
                  <strong>{session.title}</strong>
                  <span>
                    {session.message_count} messages · {formatDateTime(session.updated_at)}
                  </span>
                </button>
              ))}
            {!isLoadingSessions && !sessions.length && (
              <div className="source-empty">No saved chats yet.</div>
            )}
          </div>
        </section>

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

function chatMessageFromResponse(message: ChatMessageResponse): ChatMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    sources: message.sources,
    latencyMs: message.latency_ms ?? undefined,
    model: message.llm_model ?? undefined,
    traceId: message.trace_id ?? undefined,
  };
}
