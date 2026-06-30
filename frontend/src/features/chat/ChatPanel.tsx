import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type MouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import {
  ArrowDown,
  ArrowUpRight,
  Check,
  Copy,
  FileSearch,
  LogIn,
  LoaderCircle,
  Menu,
  MessageSquare,
  MessageSquarePlus,
  PanelLeftClose,
  Search,
  SendHorizontal,
  Settings,
  Sparkles,
  Trash2,
  UserCircle,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link } from "react-router-dom";
import { useAppData } from "../../app/AppDataContext";
import {
  API_BASE_URL,
  askChatStream,
  deleteChatSession,
  getChatSession,
  listChatSessions,
} from "../../services/api";
import { formatDateTime, messageFromError, scorePercent, summarizeDocuments } from "../../lib/format";
import type { ChatMessage } from "./types";
import type {
  ChatMessageResponse,
  ChatSessionSummary,
  RetrievedChunkResponse,
} from "../../services/types";

const SIDEBAR_MIN_WIDTH = 248;
const SIDEBAR_MAX_WIDTH = 420;
const SIDEBAR_DEFAULT_WIDTH = 304;
const COMPOSER_MIN_HEIGHT = 40;
const COMPOSER_MAX_HEIGHT = 200;

type StreamPhase = "searching" | "answering" | null;

const SUGGESTIONS = [
  "Which policy mentions the 14-day satellite-mode exception?",
  "Which team owns model-assisted triage?",
  "What evidence is required for policy verification?",
  "How long are hourly aggregated metrics retained?",
];

export function ChatPanel({
  error,
  onError,
}: {
  error?: string | null;
  onError: (message: string | null) => void;
}) {
  const { documents, health } = useAppData();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [historyQuery, setHistoryQuery] = useState("");
  const [isLoadingSessions, setLoadingSessions] = useState(false);
  const [isLoadingSession, setLoadingSession] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [streamPhase, setStreamPhase] = useState<StreamPhase>(null);
  const [isNearBottom, setNearBottom] = useState(true);
  const [isSidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT_WIDTH);
  const [isResizingSidebar, setResizingSidebar] = useState(false);
  const messageListRef = useRef<HTMLDivElement>(null);
  const draftInputRef = useRef<HTMLTextAreaElement>(null);
  const isNearBottomRef = useRef(true);

  const hasConversation = messages.length > 0;
  const documentStats = useMemo(
    () => summarizeDocuments(documents?.documents ?? []),
    [documents],
  );
  const documentCount = documents?.total ?? 0;
  const chunkCount = documentStats.childChunks;
  const isKnowledgeReady = !!documentCount && health?.status === "ok";
  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId),
    [activeSessionId, sessions],
  );
  const filteredSessions = useMemo(() => {
    const query = historyQuery.trim().toLocaleLowerCase();
    if (!query) return sessions;
    return sessions.filter((session) =>
      session.title.toLocaleLowerCase().includes(query),
    );
  }, [historyQuery, sessions]);

  useEffect(() => {
    void refreshSessions();
  }, []);

  useEffect(() => {
    const messageList = messageListRef.current;
    if (!messageList || !isNearBottomRef.current) return;

    messageList.scrollTo({
      top: messageList.scrollHeight,
      behavior: isAsking ? "auto" : "smooth",
    });
  }, [messages, isAsking]);

  useLayoutEffect(() => {
    const input = draftInputRef.current;
    if (!input) return;

    input.style.height = "auto";
    const nextHeight = Math.min(
      Math.max(input.scrollHeight, COMPOSER_MIN_HEIGHT),
      COMPOSER_MAX_HEIGHT,
    );
    input.style.height = `${nextHeight}px`;
    input.style.overflowY =
      input.scrollHeight > COMPOSER_MAX_HEIGHT ? "auto" : "hidden";
  }, [draft]);

  useEffect(() => {
    if (!isResizingSidebar) return;

    function resize(event: PointerEvent) {
      setSidebarWidth(clamp(event.clientX, SIDEBAR_MIN_WIDTH, SIDEBAR_MAX_WIDTH));
    }

    function stopResize() {
      setResizingSidebar(false);
    }

    window.addEventListener("pointermove", resize);
    window.addEventListener("pointerup", stopResize);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    return () => {
      window.removeEventListener("pointermove", resize);
      window.removeEventListener("pointerup", stopResize);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isResizingSidebar]);

  async function refreshSessions() {
    setLoadingSessions(true);
    try {
      const payload = await listChatSessions();
      setSessions(payload.sessions);
    } catch (caught) {
      onError(messageFromError(caught));
    } finally {
      setLoadingSessions(false);
    }
  }

  async function loadSession(sessionId: string) {
    setLoadingSession(true);
    setActiveSessionId(sessionId);
    markConversationAtBottom();
    onError(null);
    try {
      const session = await getChatSession(sessionId);
      setMessages(session.messages.map(chatMessageFromResponse));
      closeSidebarOnNarrowViewport(setSidebarOpen);
    } catch (caught) {
      onError(messageFromError(caught));
    } finally {
      setLoadingSession(false);
    }
  }

  function startNewChat() {
    setActiveSessionId(null);
    setMessages([]);
    setDraft("");
    setStreamPhase(null);
    markConversationAtBottom();
    onError(null);
    closeSidebarOnNarrowViewport(setSidebarOpen);
    window.requestAnimationFrame(() => draftInputRef.current?.focus());
  }

  function selectSuggestion(value: string) {
    setDraft(value);
    window.requestAnimationFrame(() => draftInputRef.current?.focus());
  }

  async function removeSession(
    event: MouseEvent<HTMLButtonElement>,
    session: ChatSessionSummary,
  ) {
    event.stopPropagation();
    onError(null);
    try {
      await deleteChatSession(session.id);
      setSessions((current) => current.filter((item) => item.id !== session.id));
      if (activeSessionId === session.id) {
        startNewChat();
      }
    } catch (caught) {
      onError(messageFromError(caught));
    }
  }

  async function submitQuestion(event: FormEvent) {
    event.preventDefault();
    const question = draft.trim();
    if (!question || isAsking) return;

    setDraft("");
    setIsAsking(true);
    setStreamPhase("searching");
    markConversationAtBottom();
    onError(null);

    const streamAssistantId = crypto.randomUUID();
    try {
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
          onRetrieval: () => {
            setStreamPhase("answering");
          },
          onDelta: (text) => {
            setStreamPhase("answering");
            setMessages((current) =>
              current.map((message) =>
                message.id === streamAssistantId
                  ? { ...message, content: `${message.content}${text}` }
                  : message,
              ),
            );
          },
          onComplete: (payload) => {
            setStreamPhase(null);
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
      await refreshSessions();
    } catch (caught) {
      setStreamPhase(null);
      onError(messageFromError(caught));
      setDraft(question);
      setMessages((current) =>
        current.map((message) =>
          message.id === streamAssistantId && !message.content
            ? {
                ...message,
                content:
                  "The answer stream stopped before a response was completed. Your question is back in the composer so you can retry.",
              }
            : message,
        ),
      );
    } finally {
      setIsAsking(false);
      setStreamPhase(null);
    }
  }

  function handleMessageScroll() {
    const messageList = messageListRef.current;
    if (!messageList) return;

    const distanceFromBottom =
      messageList.scrollHeight - messageList.scrollTop - messageList.clientHeight;
    const nearBottom = distanceFromBottom < 96;
    isNearBottomRef.current = nearBottom;
    setNearBottom(nearBottom);
  }

  function markConversationAtBottom() {
    isNearBottomRef.current = true;
    setNearBottom(true);
  }

  function scrollToLatest() {
    markConversationAtBottom();
    messageListRef.current?.scrollTo({
      top: messageListRef.current.scrollHeight,
      behavior: "smooth",
    });
  }

  function startSidebarResize(event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    setResizingSidebar(true);
  }

  return (
    <section className="rag-chat-shell">
      {isSidebarOpen && (
        <button
          aria-label="Close chat history"
          className="rag-chat-overlay"
          onClick={() => setSidebarOpen(false)}
          type="button"
        />
      )}

      <aside
        className={[
          "rag-chat-sidebar",
          isSidebarOpen ? "open" : "closed",
        ].join(" ")}
        style={{ width: isSidebarOpen ? sidebarWidth : 0 }}
      >
        <div className="rag-chat-sidebar-inner">
          <div className="rag-chat-brand">
            <div className="rag-chat-logo">
              <Sparkles size={21} />
            </div>
            <div>
              <h2>Docu Search</h2>
              <p>Knowledge workspace</p>
            </div>
            <button
              aria-label="Close sidebar"
              className="rag-chat-icon-button mobile-only"
              onClick={() => setSidebarOpen(false)}
              type="button"
            >
              <X size={17} />
            </button>
          </div>

          <div className="rag-chat-sidebar-pad">
            <button className="rag-chat-new-button" onClick={startNewChat} type="button">
              <MessageSquarePlus size={18} />
              New chat
            </button>

            <div className="rag-chat-search">
              <Search size={16} />
              <input
                aria-label="Search chat history"
                onChange={(event) => setHistoryQuery(event.target.value)}
                placeholder="Search chats"
                type="text"
                value={historyQuery}
              />
              {historyQuery && (
                <button
                  aria-label="Clear history search"
                  onClick={() => setHistoryQuery("")}
                  type="button"
                >
                  <X size={13} />
                </button>
              )}
            </div>

            <div className="rag-chat-section-label">
              <span>Recent chats</span>
              <span>{filteredSessions.length}</span>
            </div>
          </div>

          <div className="rag-chat-history">
            {isLoadingSessions && <HistorySkeleton />}
            {!isLoadingSessions &&
              filteredSessions.map((session) => (
                <article
                  className={[
                    "rag-chat-history-row",
                    session.id === activeSessionId ? "active" : "",
                  ].join(" ")}
                  key={session.id}
                >
                  <button onClick={() => void loadSession(session.id)} type="button">
                    <MessageSquare size={16} />
                    <span>
                      <strong>{session.title}</strong>
                      <small>
                        {session.message_count} messages · {formatDateTime(session.updated_at)}
                      </small>
                    </span>
                  </button>
                  <button
                    aria-label={`Delete ${session.title}`}
                    className="delete"
                    onClick={(event) => void removeSession(event, session)}
                    type="button"
                  >
                    <Trash2 size={14} />
                  </button>
                </article>
              ))}
            {!isLoadingSessions && !filteredSessions.length && (
              <div className="rag-chat-empty-history">
                {historyQuery ? "No matching chats." : "No saved chats yet."}
              </div>
            )}
          </div>

          <KnowledgeBaseCard
            chunkCount={chunkCount}
            documentCount={documentCount}
            isReady={isKnowledgeReady}
          />

          <footer className="rag-chat-profile">
            <div className="rag-chat-avatar">
              <UserCircle size={21} />
            </div>
            <div>
              <strong>Guest workspace</strong>
              <small>Local profile</small>
            </div>
            <Link aria-label="Admin panel" title="Admin panel" to="/admin/overview">
              <Settings size={16} />
            </Link>
            <button aria-label="Sign in" title="Sign in" type="button">
              <LogIn size={16} />
            </button>
          </footer>
        </div>

        <div
          aria-hidden="true"
          className="rag-chat-resize"
          onPointerDown={startSidebarResize}
        />
      </aside>

      <section className="rag-chat-main">
        <header className="rag-chat-topbar">
          <div className="rag-chat-top-left">
            <button
              aria-label={isSidebarOpen ? "Hide chat history" : "Show chat history"}
              className="rag-chat-icon-button"
              onClick={() => setSidebarOpen((current) => !current)}
              type="button"
            >
              {isSidebarOpen ? <PanelLeftClose size={18} /> : <Menu size={18} />}
            </button>
            <div className="rag-chat-title-wrap">
              <h1>{activeSession?.title || "New chat"}</h1>
              <p>
                {hasConversation
                  ? "Company Docs · grounded answer with sources"
                  : "Ask across indexed company documents"}
              </p>
            </div>
          </div>
          <div className="rag-chat-top-actions">
            <div className={["rag-chat-pill", isKnowledgeReady ? "ready" : "warn"].join(" ")}>
              <span className="rag-chat-pulse" />
              Company Docs · {formatCompactNumber(documentCount)} docs · {isKnowledgeReady ? "Ready" : "Index pending"}
            </div>
            <Link className="rag-chat-top-button" to="/admin/overview">
              Admin
            </Link>
          </div>
        </header>

        <section className="rag-chat-content">
          <div
            className="rag-chat-scroll"
            onScroll={handleMessageScroll}
            ref={messageListRef}
          >
            {!hasConversation && !isLoadingSession && (
              <WelcomePanel
                chunkCount={chunkCount}
                documentCount={documentCount}
                isReady={isKnowledgeReady}
                onSelectSuggestion={selectSuggestion}
              />
            )}

            <div className="rag-chat-conversation">
              {error && (
                <div className="rag-chat-error">
                  <span>{error}</span>
                  <button aria-label="Dismiss error" onClick={() => onError(null)} type="button">
                    <X size={15} />
                  </button>
                </div>
              )}

              {isLoadingSession && <ConversationSkeleton />}

              {messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  streamPhase={message.model === "streaming" ? streamPhase : null}
                />
              ))}

              {isAsking && !messages.some((message) => message.model === "streaming") && (
                <div className="rag-chat-stream-row">
                  <StreamStatus phase={streamPhase ?? "searching"} />
                </div>
              )}
            </div>

            {hasConversation && (
              <div className="rag-chat-admin-hint">
                <b>Admin-only:</b> Trace, chunk scores, latency, token cost, and model metadata stay in the admin console.
              </div>
            )}
          </div>

          {!isNearBottom && hasConversation && (
            <button
              aria-label="Scroll to latest message"
              className="rag-chat-scroll-latest"
              onClick={scrollToLatest}
              title="Scroll to latest"
              type="button"
            >
              <ArrowDown size={17} />
            </button>
          )}

          <form
            className="rag-chat-composer"
            onSubmit={(event) => void submitQuestion(event)}
          >
            <button
              aria-label="New chat"
              className="rag-chat-composer-action"
              onClick={startNewChat}
              type="button"
            >
              +
            </button>
            <textarea
              aria-label="Message Docu Search"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder={isAsking ? "Generating response..." : hasConversation ? "Ask a follow-up question" : "Message Docu Search"}
              ref={draftInputRef}
              rows={1}
              value={draft}
            />
            <button
              className="rag-chat-kb-button"
              title={`${formatCompactNumber(documentCount)} documents, ${formatCompactNumber(chunkCount)} chunks`}
              type="button"
            >
              KB
            </button>
            <button
              aria-label="Send message"
              className="rag-chat-send"
              disabled={!draft.trim() || isAsking}
              type="submit"
            >
              {isAsking ? <LoaderCircle className="animate-spin" size={18} /> : <SendHorizontal size={18} />}
            </button>
          </form>
        </section>
      </section>
    </section>
  );
}

function WelcomePanel({
  chunkCount,
  documentCount,
  isReady,
  onSelectSuggestion,
}: {
  chunkCount: number;
  documentCount: number;
  isReady: boolean;
  onSelectSuggestion: (value: string) => void;
}) {
  return (
    <section className="rag-chat-welcome">
      <div className="rag-chat-hero">
        <div className="rag-chat-hero-icon">
          <FileSearch size={23} />
        </div>
        <h1>What should we look up?</h1>
        <p>Ask questions across your indexed company documents and get answers with sources.</p>
        <div className={["rag-chat-readiness", isReady ? "ready" : "warn"].join(" ")}>
          <span className="rag-chat-pulse" />
          <b>Company Docs</b>
          <span>{formatCompactNumber(documentCount)} documents</span>
          <span>{formatCompactNumber(chunkCount)} chunks</span>
          <span>{isReady ? "Ready" : "Index pending"}</span>
        </div>

        <div className="rag-chat-suggestions">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => onSelectSuggestion(suggestion)}
              type="button"
            >
              <span>{suggestion}</span>
              <ArrowUpRight size={16} />
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function KnowledgeBaseCard({
  chunkCount,
  documentCount,
  isReady,
}: {
  chunkCount: number;
  documentCount: number;
  isReady: boolean;
}) {
  return (
    <section className="rag-chat-kb-card" aria-label="Knowledge base status">
      <div className="top">
        <h3>Knowledge base</h3>
        <span className={["status", isReady ? "ready" : "warn"].join(" ")}>
          <i className="rag-chat-pulse" />
          {isReady ? "Ready" : "Pending"}
        </span>
      </div>
      <strong>Company Docs</strong>
      <div className="rag-chat-kb-grid">
        <article>
          <b>{formatCompactNumber(documentCount)}</b>
          <span>indexed docs</span>
        </article>
        <article>
          <b>{formatCompactNumber(chunkCount)}</b>
          <span>search chunks</span>
        </article>
      </div>
    </section>
  );
}

function MessageBubble({
  message,
  streamPhase,
}: {
  message: ChatMessage;
  streamPhase: StreamPhase;
}) {
  const [isCopied, setCopied] = useState(false);
  const [showSourceDetails, setShowSourceDetails] = useState(false);

  async function copyMessage() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  if (message.role === "user") {
    return (
      <article className="rag-chat-message user">
        <div>{message.content}</div>
      </article>
    );
  }

  const isStreaming = message.model === "streaming";
  const isWaitingForFirstToken = isStreaming && !message.content;

  return (
    <article className="rag-chat-message assistant">
      <div className="rag-chat-answer-card">
        <header className="rag-chat-answer-head">
          <div className="rag-chat-assistant-label">
            <span><Sparkles size={16} /></span>
            <strong>Docu Search</strong>
          </div>
          {!!message.sources?.length && (
            <em>Answer grounded in {uniqueDocumentSources(message.sources).length} sources</em>
          )}
        </header>

        <div className="rag-chat-answer-text">
          {isWaitingForFirstToken ? (
            <StreamStatus phase={streamPhase ?? "answering"} />
          ) : (
            <ChatMarkdown text={message.content} sources={message.sources ?? []} />
          )}
        </div>

        {!isStreaming && !!message.sources?.length && (
          <SourcesPanel
            isOpen={showSourceDetails}
            onToggle={() => setShowSourceDetails((current) => !current)}
            sources={message.sources}
          />
        )}

        {!isStreaming && message.content && (
          <footer className="rag-chat-answer-actions">
            <button
              aria-label={isCopied ? "Response copied" : "Copy response"}
              onClick={() => void copyMessage()}
              title={isCopied ? "Copied" : "Copy response"}
              type="button"
            >
              {isCopied ? <Check size={15} /> : <Copy size={15} />}
              {isCopied ? "Copied" : "Copy"}
            </button>
            <div>
              <span>Was this helpful?</span>
              <button aria-label="Helpful" type="button">👍</button>
              <button aria-label="Not helpful" type="button">👎</button>
            </div>
          </footer>
        )}
      </div>
    </article>
  );
}

function ChatMarkdown({
  text,
  sources,
}: {
  text: string;
  sources: RetrievedChunkResponse[];
}) {
  return (
    <ReactMarkdown
      components={{
        a: ({ children, ...props }) => (
          <a
            {...props}
            className="rag-md-link"
            rel="noreferrer"
            target="_blank"
          >
            {children}
          </a>
        ),
        blockquote: ({ children }) => (
          <blockquote className="rag-md-blockquote">
            {children}
          </blockquote>
        ),
        code: ({ children }) => (
          <code className="rag-md-code">
            {children}
          </code>
        ),
        h1: ({ children }) => (
          <h1 className="rag-md-h1">
            {children}
          </h1>
        ),
        h2: ({ children }) => (
          <h2 className="rag-md-h2">
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="rag-md-h3">
            {children}
          </h3>
        ),
        hr: () => <hr className="rag-md-hr" />,
        li: ({ children }) => <li className="rag-md-li">{children}</li>,
        ol: ({ children }) => (
          <ol className="rag-md-ol">
            {children}
          </ol>
        ),
        p: ({ children }) => <p className="rag-md-p">{children}</p>,
        pre: ({ children }) => (
          <pre className="rag-md-pre">
            {children}
          </pre>
        ),
        strong: ({ children }) => (
          <strong className="rag-md-strong">{children}</strong>
        ),
        table: ({ children }) => (
          <div className="rag-md-table-wrap">
            <table>{children}</table>
          </div>
        ),
        td: ({ children }) => (
          <td className="rag-md-td">
            {children}
          </td>
        ),
        th: ({ children }) => (
          <th className="rag-md-th">
            {children}
          </th>
        ),
        ul: ({ children }) => (
          <ul className="rag-md-ul">
            {children}
          </ul>
        ),
      }}
      remarkPlugins={[remarkGfm]}
    >
      {linkCitationMarkers(text, sources)}
    </ReactMarkdown>
  );
}

function SourcesPanel({
  isOpen,
  onToggle,
  sources,
}: {
  isOpen: boolean;
  onToggle: () => void;
  sources: RetrievedChunkResponse[];
}) {
  const uniqueSources = uniqueDocumentSources(sources);

  return (
    <section className="rag-chat-sources" aria-label="Source documents">
      <h3>Sources</h3>
      <div className="rag-chat-source-chips">
        {uniqueSources.map((source) => {
          const href = sourceDocumentUrl(source);
          const fileName = source.file_name ?? "Source document";

          const label = `${source.rank}. ${fileName}`;
          return href ? (
            <a
              href={href}
              id={`source-${source.rank}`}
              key={source.child_chunk_id}
              rel="noreferrer"
              target="_blank"
              title={`Open source - relevance ${scorePercent(source.score)}`}
            >
              {label}
            </a>
          ) : (
            <span
              id={`source-${source.rank}`}
              key={source.child_chunk_id}
              title="This saved source does not include a document id yet."
            >
              {label}
            </span>
          );
        })}
      </div>
      <button className="rag-chat-source-toggle" onClick={onToggle} type="button">
        {isOpen ? "Hide source details" : "View source details"}
      </button>
      {isOpen && (
        <div className="rag-chat-source-details">
          <header>
            <span>Source details</span>
            <small>Expanded only when requested</small>
          </header>
          <div>
            {sources.slice(0, 4).map((source) => (
              <article key={source.child_chunk_id}>
                <strong>{source.file_name ?? "Source document"}</strong>
                <p>{source.child_text || source.parent_text}</p>
                <footer>
                  <span>Rank {source.rank}</span>
                  <span>{scorePercent(source.score)} relevance</span>
                </footer>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function HistorySkeleton() {
  return (
    <div className="rag-chat-history-skeleton">
      {[0, 1, 2].map((item) => (
        <article key={item}>
          <span />
          <small />
        </article>
      ))}
    </div>
  );
}

function ConversationSkeleton() {
  return (
    <div className="rag-chat-conversation-skeleton">
      <span />
      <span />
      <span />
    </div>
  );
}

function StreamStatus({ phase }: { phase: Exclude<StreamPhase, null> }) {
  return (
    <div
      aria-live="polite"
      className="rag-chat-stream-status"
    >
      <LoadingDots />
      <span>{phase === "searching" ? "Searching documents" : "Writing answer"}</span>
    </div>
  );
}

function LoadingDots() {
  return (
    <div className="rag-chat-loading-dots" aria-hidden="true">
      {[0, 1, 2].map((item) => (
        <span
          key={item}
          style={{ animationDelay: `${item * 120}ms` }}
        />
      ))}
    </div>
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

function uniqueDocumentSources(
  sources: RetrievedChunkResponse[],
): RetrievedChunkResponse[] {
  const seenDocuments = new Set<string>();

  return sources.filter((source) => {
    const key = source.document_id
      ? `document:${source.document_id}`
      : `file:${source.file_name ?? source.child_chunk_id}`;

    if (seenDocuments.has(key)) return false;
    seenDocuments.add(key);
    return true;
  });
}

function linkCitationMarkers(
  text: string,
  sources: RetrievedChunkResponse[],
): string {
  const urlsByRank = new Map(
    sources.flatMap((source) => {
      const url = sourceDocumentUrl(source);
      return url ? [[source.rank, url] as const] : [];
    }),
  );

  if (!urlsByRank.size) return text;

  return text
    .split(/(```[\s\S]*?```|`[^`\n]+`)/g)
    .map((segment) => {
      if (segment.startsWith("`")) return segment;

      return segment
        .replace(/\[(\d+)\](?!\()/g, (marker, rankText: string) => {
          const url = urlsByRank.get(Number(rankText));
          return url ? `[${rankText}](${url})` : marker;
        })
        .replace(
          /\u3010(\d+)(?:\u2020[^\u3011]*)?\u3011/g,
          (marker, rankText: string) => {
            const url = urlsByRank.get(Number(rankText));
            return url ? `[${rankText}](${url})` : marker;
          },
        );
    })
    .join("");
}

function sourceDocumentUrl(source: RetrievedChunkResponse): string | undefined {
  if (!source.document_id) return undefined;
  return `${API_BASE_URL}/documents/${encodeURIComponent(source.document_id)}/source`;
}

function formatCompactNumber(value: number | null | undefined): string {
  if (typeof value !== "number") return "0";
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 1,
    notation: value >= 1000 ? "compact" : "standard",
  }).format(value);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function closeSidebarOnNarrowViewport(setSidebarOpen: (value: boolean) => void) {
  if (typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches) {
    setSidebarOpen(false);
  }
}
