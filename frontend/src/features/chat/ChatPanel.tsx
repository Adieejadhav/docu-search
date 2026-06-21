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
import {
  API_BASE_URL,
  askChatStream,
  deleteChatSession,
  getChatSession,
  listChatSessions,
} from "../../services/api";
import { formatDateTime, messageFromError, scorePercent } from "../../lib/format";
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

  async function refreshSessions(autoSelect = true) {
    setLoadingSessions(true);
    try {
      const payload = await listChatSessions();
      setSessions(payload.sessions);
      if (autoSelect && !activeSessionId && payload.sessions.length && !messages.length) {
        await loadSession(payload.sessions[0].id);
      }
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
      await refreshSessions(false);
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
    <section className="flex h-screen overflow-hidden bg-slate-50 text-slate-800">
      {isSidebarOpen && (
        <button
          aria-label="Close chat history"
          className="fixed inset-0 z-20 bg-slate-950/20 md:hidden"
          onClick={() => setSidebarOpen(false)}
          type="button"
        />
      )}

      <aside
        className={[
          "fixed inset-y-0 left-0 z-30 flex h-screen w-[min(86vw,320px)] flex-col overflow-hidden border-r border-slate-200 bg-[#f4f5f7] shadow-2xl shadow-slate-950/10 transition-transform md:static md:z-auto md:w-auto md:translate-x-0 md:shadow-none",
          isSidebarOpen ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
        style={{ width: isSidebarOpen ? sidebarWidth : 0 }}
      >
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex items-center gap-2.5 px-3 pb-3 pt-3.5">
            <div className="grid size-9 place-items-center rounded-lg bg-slate-900 text-white shadow-[0_3px_10px_rgba(15,23,42,0.18)]">
              <Sparkles size={18} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-900">Docu Search</p>
              <p className="truncate text-xs text-slate-500">Knowledge workspace</p>
            </div>
            <button
              aria-label="Close sidebar"
              className="grid size-8 place-items-center rounded-lg text-slate-500 hover:bg-white hover:text-slate-900 md:hidden"
              onClick={() => setSidebarOpen(false)}
              type="button"
            >
              <X size={17} />
            </button>
          </div>

          <div className="px-3 pb-3 pt-1">
            <button
              className="group flex h-11 w-full items-center justify-start gap-2.5 rounded-lg border border-slate-900 bg-slate-900 px-2.5 text-sm font-normal text-white shadow-[0_4px_14px_rgba(15,23,42,0.16)] transition hover:border-slate-700 hover:bg-slate-800 hover:shadow-[0_6px_18px_rgba(15,23,42,0.20)]"
              onClick={startNewChat}
              type="button"
            >
              <span className="grid size-7 place-items-center rounded-md bg-white/10 transition group-hover:bg-white/15">
                <MessageSquarePlus size={16} />
              </span>
              New chat
            </button>
          </div>

          <div className="px-3 pb-3">
            <div className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white/80 px-2.5 text-slate-500 shadow-sm transition focus-within:border-slate-300 focus-within:bg-white">
              <Search className="shrink-0" size={15} />
              <input
                aria-label="Search chat history"
                className="!h-auto min-w-0 flex-1 !border-0 !bg-transparent !p-0 text-sm text-slate-700 !shadow-none !outline-none placeholder:text-slate-400 focus:!border-transparent focus:!shadow-none"
                onChange={(event) => setHistoryQuery(event.target.value)}
                placeholder="Search chats"
                type="text"
                value={historyQuery}
              />
              {historyQuery && (
                <button
                  aria-label="Clear history search"
                  className="grid size-6 shrink-0 place-items-center rounded-md text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                  onClick={() => setHistoryQuery("")}
                  type="button"
                >
                  <X size={13} />
                </button>
              )}
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
            <div className="flex items-center justify-between px-2 pb-2.5 pt-1 text-xs text-slate-400">
              <span className="font-normal text-slate-500">Recent chats</span>
              <span>{filteredSessions.length}</span>
            </div>
            {isLoadingSessions && <HistorySkeleton />}
            {!isLoadingSessions &&
              filteredSessions.map((session) => (
                <div
                  className={[
                    "group relative mb-1 flex w-full items-center gap-2 rounded-lg px-2.5 py-2.5 text-left text-sm transition",
                    session.id === activeSessionId
                      ? "bg-white text-slate-950 shadow-[0_2px_8px_rgba(15,23,42,0.07)] ring-1 ring-slate-200"
                      : "text-slate-600 hover:bg-white/80 hover:text-slate-900",
                  ].join(" ")}
                  key={session.id}
                >
                  {session.id === activeSessionId && (
                    <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-sky-600" />
                  )}
                  <button
                    className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
                    onClick={() => void loadSession(session.id)}
                    type="button"
                  >
                    <MessageSquare
                      className={
                        session.id === activeSessionId
                          ? "shrink-0 text-sky-600"
                          : "shrink-0 text-slate-400"
                      }
                      size={16}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-normal">{session.title}</span>
                      <span className="mt-0.5 block truncate text-xs text-slate-400">
                        {session.message_count} messages - {formatDateTime(session.updated_at)}
                      </span>
                    </span>
                  </button>
                  <button
                    aria-label={`Delete ${session.title}`}
                    className="grid size-7 shrink-0 place-items-center rounded-lg text-slate-400 opacity-0 transition hover:bg-rose-50 hover:text-rose-600 group-hover:opacity-100"
                    onClick={(event) => void removeSession(event, session)}
                    type="button"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            {!isLoadingSessions && !filteredSessions.length && (
              <div className="mx-2 rounded-lg border border-dashed border-slate-300 bg-white/50 p-4 text-center text-sm text-slate-500">
                {historyQuery ? "No matching chats." : "No saved chats yet."}
              </div>
            )}
          </div>

          <footer className="border-t border-slate-200 bg-white/25 px-3 py-2.5">
            <div className="flex items-center gap-2 rounded-lg px-1.5 py-1.5 transition hover:bg-white/80">
              <div className="grid size-9 place-items-center rounded-full bg-white text-slate-600 shadow-sm ring-1 ring-slate-200">
                <UserCircle size={20} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-normal text-slate-800">Guest workspace</p>
                <p className="truncate text-xs text-slate-400">Local profile</p>
              </div>
              <Link
                aria-label="Settings"
                className="grid size-8 place-items-center rounded-lg text-slate-500 transition hover:bg-white hover:text-slate-900"
                title="Settings"
                to="/admin/overview"
              >
                <Settings size={16} />
              </Link>
              <button
                aria-label="Sign in"
                className="grid size-8 place-items-center rounded-lg text-slate-500 transition hover:bg-white hover:text-slate-900"
                title="Sign in"
                type="button"
              >
                <LogIn size={16} />
              </button>
            </div>
          </footer>
        </div>

        <div
          aria-hidden="true"
          className="absolute inset-y-0 right-0 hidden w-1 cursor-col-resize bg-transparent transition hover:bg-slate-300 md:block"
          onPointerDown={startSidebarResize}
        />
      </aside>

      <section className="flex min-w-0 flex-1 flex-col bg-slate-50">
        <header className="flex h-14 shrink-0 items-center border-b border-slate-200 bg-white/80 px-3 backdrop-blur md:px-5">
          <div className="flex min-w-0 items-center gap-2">
            <button
              aria-label="Open chat history"
              className="grid size-9 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 md:hidden"
              onClick={() => setSidebarOpen(true)}
              type="button"
            >
              <Menu size={19} />
            </button>
            <button
              aria-label="Show chat history"
              className="hidden size-9 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 md:grid"
              onClick={() => setSidebarOpen((current) => !current)}
              type="button"
            >
              <PanelLeftClose size={18} />
            </button>
            <div className="min-w-0">
              <p className="truncate text-sm font-normal text-slate-900">
                {activeSession?.title || "New chat"}
              </p>
            </div>
          </div>
        </header>

        <div className="relative min-h-0 flex-1">
          <div
            className="h-full overflow-y-auto px-4 py-6 md:px-8"
            onScroll={handleMessageScroll}
            ref={messageListRef}
          >
            {!hasConversation && !isLoadingSession && (
              <WelcomePanel onSelectSuggestion={selectSuggestion} />
            )}

            <div className="mx-auto flex w-full max-w-[768px] flex-col gap-8 pb-2">
              {error && (
                <div className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  <span className="min-w-0 flex-1">{error}</span>
                  <button
                    aria-label="Dismiss error"
                    className="grid size-7 shrink-0 place-items-center rounded-md text-rose-500 transition hover:bg-rose-100 hover:text-rose-700"
                    onClick={() => onError(null)}
                    type="button"
                  >
                    <X size={15} />
                  </button>
                </div>
              )}

              {isLoadingSession && (
                <div className="space-y-3 py-4">
                  <div className="h-4 w-2/3 animate-pulse rounded-full bg-slate-200" />
                  <div className="h-4 w-1/2 animate-pulse rounded-full bg-slate-200" />
                  <div className="h-4 w-5/6 animate-pulse rounded-full bg-slate-200" />
                </div>
              )}

              {messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  streamPhase={message.model === "streaming" ? streamPhase : null}
                />
              ))}

              {isAsking && !messages.some((message) => message.model === "streaming") && (
                <div className="flex w-full justify-start px-1 py-2">
                  <StreamStatus phase={streamPhase ?? "searching"} />
                </div>
              )}
            </div>
          </div>

          {!isNearBottom && hasConversation && (
            <button
              aria-label="Scroll to latest message"
              className="absolute bottom-4 left-1/2 z-10 grid size-9 -translate-x-1/2 place-items-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-lg transition hover:border-slate-300 hover:text-slate-900"
              onClick={scrollToLatest}
              title="Scroll to latest"
              type="button"
            >
              <ArrowDown size={17} />
            </button>
          )}
        </div>

        <form
          className="shrink-0 bg-slate-50 px-3 pb-4 pt-2 md:px-6"
          onSubmit={(event) => void submitQuestion(event)}
        >
          <div className="mx-auto w-full max-w-[768px]">
            <div className="flex min-h-14 items-end gap-2 rounded-[28px] border border-slate-200 bg-white px-4 py-2 shadow-[0_3px_20px_rgba(15,23,42,0.10)] transition focus-within:border-blue-300 focus-within:shadow-[0_5px_26px_rgba(15,23,42,0.13)]">
              <textarea
                aria-label="Message Docu Search"
                className="block max-h-[200px] !min-h-10 flex-1 !resize-none overflow-hidden !rounded-none !border-0 !bg-transparent !px-0 !py-2 text-[15px] leading-6 text-slate-800 !shadow-none !outline-none placeholder:text-slate-400 focus:!border-transparent focus:!shadow-none focus:!ring-0"
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                placeholder={isAsking ? "Generating response..." : "Message Docu Search"}
                ref={draftInputRef}
                rows={1}
                value={draft}
              />
              <button
                aria-label="Send message"
                className="mb-0.5 grid size-9 shrink-0 place-items-center rounded-full bg-slate-900 text-white transition hover:bg-slate-700 disabled:bg-slate-200 disabled:text-slate-400"
                disabled={!draft.trim() || isAsking}
                type="submit"
              >
                {isAsking ? (
                  <LoaderCircle className="animate-spin" size={17} />
                ) : (
                  <SendHorizontal size={17} />
                )}
              </button>
            </div>
          </div>
        </form>
      </section>
    </section>
  );
}

function WelcomePanel({
  onSelectSuggestion,
}: {
  onSelectSuggestion: (value: string) => void;
}) {
  return (
    <section className="mx-auto flex min-h-full w-full max-w-[720px] flex-col justify-center py-10">
      <div className="mb-8 text-center">
        <div className="mx-auto mb-4 grid size-12 place-items-center rounded-xl border border-blue-100 bg-blue-50 text-blue-700 shadow-sm">
          <FileSearch size={23} />
        </div>
        <h1 className="text-2xl font-normal tracking-normal text-slate-950 md:text-3xl">
          What should we look up?
        </h1>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {SUGGESTIONS.map((suggestion) => (
          <button
            className="group flex min-h-16 items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 text-left text-sm leading-5 text-slate-600 shadow-sm transition hover:border-blue-200 hover:text-slate-900 hover:shadow-md"
            key={suggestion}
            onClick={() => onSelectSuggestion(suggestion)}
            type="button"
          >
            <span className="min-w-0 flex-1">{suggestion}</span>
            <ArrowUpRight
              className="shrink-0 text-slate-300 transition group-hover:text-blue-600"
              size={16}
            />
          </button>
        ))}
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
      <article className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-[22px] bg-slate-900 px-4 py-3 text-[15px] leading-6 text-white shadow-sm md:max-w-[70%]">
          {message.content}
        </div>
      </article>
    );
  }

  const isStreaming = message.model === "streaming";
  const isWaitingForFirstToken = isStreaming && !message.content;

  return (
    <article className="group flex w-full justify-start">
      <div className="min-w-0 flex-1 px-1">
        <div className="text-[15px] leading-7 text-slate-800">
          {isWaitingForFirstToken ? (
            <StreamStatus phase={streamPhase ?? "answering"} />
          ) : (
            <ChatMarkdown text={message.content} sources={message.sources ?? []} />
          )}
        </div>
        {!isStreaming && message.content && (
          <div className="mt-1 flex min-h-8 items-center opacity-100 transition md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100">
            <button
              aria-label={isCopied ? "Response copied" : "Copy response"}
              className="grid size-8 place-items-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
              onClick={() => void copyMessage()}
              title={isCopied ? "Copied" : "Copy response"}
              type="button"
            >
              {isCopied ? <Check size={15} /> : <Copy size={15} />}
            </button>
          </div>
        )}
        {!isStreaming && !!message.sources?.length && (
          <CitationLinks sources={message.sources} />
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
            className="font-normal !text-blue-600 underline decoration-blue-200 underline-offset-4 transition hover:!text-blue-800 hover:decoration-blue-500"
            rel="noreferrer"
            target="_blank"
          >
            {children}
          </a>
        ),
        blockquote: ({ children }) => (
          <blockquote className="my-4 border-l-2 border-slate-300 pl-4 text-slate-600">
            {children}
          </blockquote>
        ),
        code: ({ children }) => (
          <code className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[0.9em] text-slate-700">
            {children}
          </code>
        ),
        h1: ({ children }) => (
          <h1 className="mb-3 mt-6 text-lg font-medium leading-7 text-slate-950 first:mt-0">
            {children}
          </h1>
        ),
        h2: ({ children }) => (
          <h2 className="mb-2 mt-5 text-base font-medium leading-7 text-slate-950 first:mt-0">
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="mb-2 mt-4 text-sm font-medium leading-6 text-slate-900 first:mt-0">
            {children}
          </h3>
        ),
        hr: () => <hr className="my-5 border-0 border-t border-slate-200" />,
        li: ({ children }) => <li className="my-1.5 pl-1">{children}</li>,
        ol: ({ children }) => (
          <ol className="my-3 list-decimal space-y-1 pl-6 marker:font-medium marker:text-slate-500">
            {children}
          </ol>
        ),
        p: ({ children }) => <p className="mb-3 leading-7 last:mb-0">{children}</p>,
        pre: ({ children }) => (
          <pre className="my-4 overflow-x-auto rounded-lg bg-slate-950 p-4 font-mono text-sm leading-6 text-slate-100 [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-inherit">
            {children}
          </pre>
        ),
        strong: ({ children }) => (
          <strong className="font-medium text-slate-950">{children}</strong>
        ),
        table: ({ children }) => (
          <div className="my-4 overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full border-collapse text-left text-sm">{children}</table>
          </div>
        ),
        td: ({ children }) => (
          <td className="border-t border-slate-200 px-3 py-2.5 align-top text-slate-700">
            {children}
          </td>
        ),
        th: ({ children }) => (
          <th className="bg-slate-50 px-3 py-2.5 font-medium text-slate-900">
            {children}
          </th>
        ),
        ul: ({ children }) => (
          <ul className="my-3 list-disc space-y-1 pl-6 marker:text-slate-400">
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

function CitationLinks({ sources }: { sources: RetrievedChunkResponse[] }) {
  const uniqueSources = uniqueDocumentSources(sources);

  return (
    <section className="mt-5 border-t border-blue-100 pt-3.5" aria-label="Source documents">
      <ul className="space-y-2">
        {uniqueSources.map((source) => {
          const href = sourceDocumentUrl(source);
          const fileName = source.file_name ?? "Source document";

          return (
            <li
              className="min-w-0 text-base leading-7"
              id={`source-${source.rank}`}
              key={source.child_chunk_id}
            >
              {href ? (
                <a
                  className="break-words font-medium !text-blue-600 transition hover:!text-blue-800"
                  href={href}
                  rel="noreferrer"
                  target="_blank"
                  title={`Open source - relevance ${scorePercent(source.score)}`}
                >
                  {fileName}
                </a>
              ) : (
                <span
                  className="break-words font-medium text-slate-400"
                  title="This saved source does not include a document id yet."
                >
                  {fileName}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function HistorySkeleton() {
  return (
    <div className="space-y-2 px-2">
      {[0, 1, 2].map((item) => (
        <div className="rounded-xl bg-white/70 p-3" key={item}>
          <div className="h-3 w-4/5 animate-pulse rounded-full bg-slate-200" />
          <div className="mt-2 h-3 w-2/5 animate-pulse rounded-full bg-slate-200" />
        </div>
      ))}
    </div>
  );
}

function StreamStatus({ phase }: { phase: Exclude<StreamPhase, null> }) {
  return (
    <div
      aria-live="polite"
      className="flex min-h-8 items-center gap-2.5 text-sm text-slate-500"
    >
      <LoadingDots />
      <span>{phase === "searching" ? "Searching documents" : "Writing answer"}</span>
    </div>
  );
}

function LoadingDots() {
  return (
    <div className="flex items-center gap-1.5 py-1" aria-hidden="true">
      {[0, 1, 2].map((item) => (
        <span
          className="size-2 animate-bounce rounded-full bg-slate-400"
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

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function closeSidebarOnNarrowViewport(setSidebarOpen: (value: boolean) => void) {
  if (typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches) {
    setSidebarOpen(false);
  }
}
