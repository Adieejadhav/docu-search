import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type MouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import {
  ArrowDown,
  Check,
  Copy,
  LayoutDashboard,
  LogIn,
  LoaderCircle,
  MessageSquarePlus,
  Moon,
  Plus,
  Search,
  SendHorizontal,
  Settings,
  Sun,
  Trash2,
  UserCircle,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link } from "react-router-dom";
import {
  WorkspaceSidebar,
  WorkspaceSidebarItem,
} from "../../app/WorkspaceSidebar";
import { useTheme } from "../../app/ThemeContext";
import {
  API_BASE_URL,
  askChatStream,
  deleteChatSession,
  getChatSession,
  listChatSessions,
} from "../../services/api";
import { messageFromError } from "../../lib/format";
import type { ChatMessage } from "./types";
import type {
  ChatMessageResponse,
  ChatSessionSummary,
  RetrievedChunkResponse,
} from "../../services/types";

const SIDEBAR_MIN_WIDTH = 224;
const SIDEBAR_MAX_WIDTH = 320;
const SIDEBAR_DEFAULT_WIDTH = 252;

type StreamPhase = "searching" | "answering" | null;

export function ChatPanel({
  error,
  onError,
}: {
  error?: string | null;
  onError: (message: string | null) => void;
}) {
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
  const [isSettingsOpen, setSettingsOpen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT_WIDTH);
  const [isResizingSidebar, setResizingSidebar] = useState(false);
  const messageListRef = useRef<HTMLDivElement>(null);
  const draftInputRef = useRef<HTMLTextAreaElement>(null);
  const isNearBottomRef = useRef(true);

  const hasConversation = messages.length > 0;
  const { theme, toggleTheme } = useTheme();
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

      <WorkspaceSidebar
        after={
          <div
            aria-hidden="true"
            className="rag-chat-resize"
            onPointerDown={startSidebarResize}
          />
        }
        className={[
          "rag-chat-sidebar",
          isSidebarOpen ? "open" : "closed",
        ].join(" ")}
        footer={
          <div className="rag-chat-profile">
            <div className="rag-chat-avatar">
              <UserCircle size={21} />
            </div>
            <div>
              <strong>Guest workspace</strong>
              <small>Local profile</small>
            </div>
            <div className="rag-chat-settings">
              <button
                aria-expanded={isSettingsOpen}
                aria-label="Open settings"
                onClick={() => setSettingsOpen((current) => !current)}
                title="Settings"
                type="button"
              >
                <Settings size={16} />
              </button>
              {isSettingsOpen && (
                <div className="rag-chat-settings-menu">
                  <Link onClick={() => setSettingsOpen(false)} to="/admin/overview">
                    <LayoutDashboard size={16} />
                    <span>Admin panel</span>
                  </Link>
                  <button
                    onClick={() => {
                      toggleTheme();
                      setSettingsOpen(false);
                    }}
                    type="button"
                  >
                    {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
                    <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
                  </button>
                </div>
              )}
            </div>
            <button aria-label="Sign in" title="Sign in" type="button">
              <LogIn size={16} />
            </button>
          </div>
        }
        isOpen={isSidebarOpen}
        onToggle={() => setSidebarOpen((current) => !current)}
        style={{ width: isSidebarOpen ? sidebarWidth : 64 }}
        subtitle="Knowledge workspace"
      >
        <div className="workspace-sidebar-tools">
            <WorkspaceSidebarItem
              icon={<MessageSquarePlus size={17} />}
              label="New chat"
              onClick={startNewChat}
            />

            <div className="workspace-sidebar-search">
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

            <div className="workspace-sidebar-label">
              <span>Recent chats</span>
              <span>{filteredSessions.length}</span>
            </div>
        </div>

        <div className="workspace-sidebar-list">
            {isLoadingSessions && <HistorySkeleton />}
            {!isLoadingSessions &&
              filteredSessions.map((session) => (
                <WorkspaceSidebarItem
                  active={session.id === activeSessionId}
                  key={session.id}
                  label={session.title}
                  onClick={() => void loadSession(session.id)}
                  trailing={
                    <button
                      aria-label={`Delete ${session.title}`}
                      className="workspace-sidebar-delete"
                      onClick={(event) => void removeSession(event, session)}
                      type="button"
                    >
                      <Trash2 size={14} />
                    </button>
                  }
                />
              ))}
            {!isLoadingSessions && !filteredSessions.length && (
              <div className="workspace-sidebar-empty">
                {historyQuery ? "No matching chats." : "No saved chats yet."}
              </div>
            )}
        </div>
      </WorkspaceSidebar>

      <section className="rag-chat-main">
        <section className="rag-chat-content">
          <div
            className="rag-chat-scroll"
            onScroll={handleMessageScroll}
            ref={messageListRef}
          >
            {!hasConversation && !isLoadingSession && (
              <WelcomePanel />
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
            className={`rag-chat-composer ${hasConversation ? "" : "empty"}`.trim()}
            onSubmit={(event) => void submitQuestion(event)}
          >
            <button
              aria-label="New chat"
              className="rag-chat-composer-action"
              onClick={startNewChat}
              type="button"
            >
              <Plus aria-hidden="true" size={20} strokeWidth={1.8} />
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

function WelcomePanel() {
  return (
    <section className="rag-chat-welcome">
      <div className="rag-chat-hero">
        <h1>How can I help?</h1>
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
        <div className="rag-chat-answer-text">
          {isWaitingForFirstToken ? (
            <StreamStatus phase={streamPhase ?? "answering"} />
          ) : (
            <ChatMarkdown text={message.content} />
          )}
        </div>

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
          </footer>
        )}

        {!isStreaming && !!message.sources?.length && (
          <SourcesPanel sources={message.sources} />
        )}
      </div>
    </article>
  );
}

function ChatMarkdown({ text }: { text: string }) {
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
      {stripCitationMarkers(text)}
    </ReactMarkdown>
  );
}

function SourcesPanel({ sources }: { sources: RetrievedChunkResponse[] }) {
  const linkedSources = uniqueDocumentSources(sources).filter(sourceDocumentUrl);

  if (!linkedSources.length) return null;

  return (
    <section className="rag-chat-sources" aria-label="Source documents">
      <h3>References</h3>
      <div className="rag-chat-source-list">
        {linkedSources.map((source) => {
          const href = sourceDocumentUrl(source)!;
          const fileName = source.file_name ?? "Source document";
          return (
            <a
              href={href}
              id={`source-${source.rank}`}
              key={source.child_chunk_id}
              rel="noreferrer"
              target="_blank"
            >
              {fileName}
            </a>
          );
        })}
      </div>
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

function stripCitationMarkers(text: string): string {
  return text
    .split(/(```[\s\S]*?```|`[^`\n]+`)/g)
    .map((segment) => {
      if (segment.startsWith("`")) return segment;

      return segment
        .replace(/\s*\[\d+(?:\s*,\s*\d+)*\](?:\([^)\n]+\))?/g, "")
        .replace(/\s*\u3010\d+(?:\u2020[^\u3011]*)?\u3011/g, "");
    })
    .join("");
}

function sourceDocumentUrl(source: RetrievedChunkResponse): string | undefined {
  if (!source.document_id) return undefined;
  return `${API_BASE_URL}/documents/${encodeURIComponent(source.document_id)}/source`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function closeSidebarOnNarrowViewport(setSidebarOpen: (value: boolean) => void) {
  if (typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches) {
    setSidebarOpen(false);
  }
}
